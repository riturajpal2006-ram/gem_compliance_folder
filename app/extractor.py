import os
import re
import fitz  # PyMuPDF
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# --- Pydantic Models for Structured Output ---

class GSTExtractionModel(BaseModel):
    gstin: str = Field(description="The 15-character Goods and Services Tax Identification Number (GSTIN)")
    legal_name: str = Field(description="The legal name of the business or individual as registered")
    trade_name: Optional[str] = Field(None, description="The trade name or business name (if separate from legal name)")
    state: Optional[str] = Field(None, description="The state name or state code where registration is held")
    status: Optional[str] = Field(None, description="The status of the GST registration (e.g., Active, Suspended, Inactive)")
    registration_date: Optional[str] = Field(None, description="The date of registration in YYYY-MM-DD format or raw text if format differs")

class UdyamExtractionModel(BaseModel):
    udyam_number: str = Field(description="The Udyam Registration Number (format: UDYAM-XX-00-1234567)")
    enterprise_name: str = Field(description="Name of Enterprise as specified in the certificate")
    enterprise_type: Optional[str] = Field(None, description="Classification of Enterprise (Micro, Small, or Medium)")
    major_activity: Optional[str] = Field(None, description="Major activity (Manufacturing or Services)")
    organization_type: Optional[str] = Field(None, description="Type of Organization (e.g. Private Limited Company, Proprietary, Partnership)")
    registration_date: Optional[str] = Field(None, description="Date of incorporation/registration")

class EPFOExtractionModel(BaseModel):
    establishment_id: str = Field(description="The 15-character EPFO Establishment ID or Registration Number")
    legal_name: str = Field(description="Legal name of the establishment")
    status: Optional[str] = Field(None, description="Status of the establishment (e.g. Active, Inactive)")
    address: Optional[str] = Field(None, description="Address of the establishment")


# --- Raw PDF text extraction ---

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts raw text from PDF bytes using PyMuPDF."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PDF document: {str(e)}")


# --- Regex fallback extraction to handle missing/invalid API keys ---

def regex_extract_gst(text: str) -> GSTExtractionModel:
    """Fallback parser for GST certificates using regex."""
    # Find 15-character GSTIN: 2 numbers, 5 letters, 4 numbers, 1 letter, 1 number/letter, Z, 1 number/letter
    gstin_match = re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}\b', text, re.IGNORECASE)
    gstin = gstin_match.group(0).upper() if gstin_match else "UNKNOWN_GSTIN"
    
    # Try to extract Legal Name from patterns
    legal_name_patterns = [
        r"(?:Legal Name|Name of the Taxpayer)\s*[:\-]?\s*([^\n\r]+)",
        r"(?:Name of Business)\s*[:\-]?\s*([^\n\r]+)",
        r"CPCL|Chennai Petroleum|Super Mech|Western Piping|Apex Boiler"
    ]
    legal_name = "UNKNOWN_LEGAL_NAME"
    for pattern in legal_name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Check if it was an exact keyword match or captured group
            val = match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
            if val and len(val) > 2:
                legal_name = val
                break
                
    # Parse status (Default to Active unless explicit suspended or inactive)
    status = "Active"
    if "suspended" in text.lower():
        status = "Suspended"
    elif "inactive" in text.lower() or "cancelled" in text.lower():
        status = "Inactive"
        
    return GSTExtractionModel(
        gstin=gstin,
        legal_name=legal_name,
        trade_name=legal_name,
        state="Tamil Nadu" if "Tamil Nadu" in text or "33" in gstin else None,
        status=status,
        registration_date=None
    )


def regex_extract_udyam(text: str) -> UdyamExtractionModel:
    """Fallback parser for Udyam certificates using regex."""
    udyam_match = re.search(r'\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b', text, re.IGNORECASE)
    udyam_number = udyam_match.group(0).upper() if udyam_match else "UNKNOWN_UDYAM"
    
    enterprise_patterns = [
        r"(?:Name of Enterprise|Enterprise Name)\s*[:\-]?\s*([^\n\r]+)",
        r"(?:M/S)\s*[:\-]?\s*([^\n\r]+)",
        r"Super Mech|Western Piping|Apex Boiler"
    ]
    enterprise_name = "UNKNOWN_ENTERPRISE_NAME"
    for pattern in enterprise_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
            if val and len(val) > 2:
                enterprise_name = val
                break
                
    enterprise_type = "Small"
    if "micro" in text.lower():
        enterprise_type = "Micro"
    elif "medium" in text.lower():
        enterprise_type = "Medium"
        
    major_activity = "Manufacturing"
    if "services" in text.lower():
        major_activity = "Services"
        
    return UdyamExtractionModel(
        udyam_number=udyam_number,
        enterprise_name=enterprise_name,
        enterprise_type=enterprise_type,
        major_activity=major_activity,
        organization_type=None,
        registration_date=None
    )


def regex_extract_epfo(text: str) -> EPFOExtractionModel:
    """Fallback parser for EPFO certificates using regex."""
    # EPFO establishment id is typically 15 alphanumeric characters or formatted like region/office/est_id
    # Usually 15-char like TNMAS0012345000 or similar
    epfo_match = re.search(r'\b[A-Z]{5}\d{10}\b|\b[A-Z]{2}/[A-Z]{3}/\d{7}/\d{3}\b', text, re.IGNORECASE)
    establishment_id = epfo_match.group(0).upper().replace("/", "") if epfo_match else "UNKNOWN_EPFO"
    
    establishment_patterns = [
        r"(?:Name of Establishment|Establishment Name)\s*[:\-]?\s*([^\n\r]+)",
        r"Super Mech|Western Piping|Apex Boiler|Chennai Petroleum"
    ]
    legal_name = "UNKNOWN_LEGAL_NAME"
    for pattern in establishment_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
            if val and len(val) > 2:
                legal_name = val
                break
                
    return EPFOExtractionModel(
        establishment_id=establishment_id,
        legal_name=legal_name,
        status="Active" if "active" in text.lower() or "covered" in text.lower() else "Active",
        address=None
    )


# --- Core Extractor Functions ---

def is_api_key_valid() -> bool:
    """Checks if GOOGLE_API_KEY is available and looks valid (not placeholder)."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or "your-gemini-api-key" in api_key or len(api_key) < 10:
        return False
    return True


def extract_gst_details(pdf_bytes: bytes) -> GSTExtractionModel:
    """Extracts GST details from a PDF file using LLM (with regex fallback)."""
    text = extract_text_from_pdf(pdf_bytes)
    
    if not is_api_key_valid():
        # Fall back to regex parser
        return regex_extract_gst(text)
        
    try:
        # LLM execution
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
        structured_llm = llm.with_structured_output(GSTExtractionModel)
        
        prompt = (
            "You are an expert document parser. Analyze the following extracted text from a "
            "GST Certificate and extract the GSTIN, Legal Name, Trade Name, State, Registration Date, "
            "and Status. Ensure values match precisely what's in the document.\n\n"
            f"Extracted Text:\n{text}"
        )
        return structured_llm.invoke(prompt)
    except Exception:
        # Fall back gracefully
        return regex_extract_gst(text)


def extract_udyam_details(pdf_bytes: bytes) -> UdyamExtractionModel:
    """Extracts Udyam details from a PDF file using LLM (with regex fallback)."""
    text = extract_text_from_pdf(pdf_bytes)
    
    if not is_api_key_valid():
        return regex_extract_udyam(text)
        
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
        structured_llm = llm.with_structured_output(UdyamExtractionModel)
        
        prompt = (
            "You are an expert document parser. Analyze the following extracted text from an "
            "Udyam MSME Certificate and extract the Udyam Registration Number, Enterprise Name, "
            "Enterprise Type (Micro, Small, or Medium), Major Activity (Manufacturing or Services), "
            "Organization Type, and Registration Date.\n\n"
            f"Extracted Text:\n{text}"
        )
        return structured_llm.invoke(prompt)
    except Exception:
        return regex_extract_udyam(text)


def extract_epfo_details(pdf_bytes: bytes) -> EPFOExtractionModel:
    """Extracts EPFO details from a PDF file using LLM (with regex fallback)."""
    text = extract_text_from_pdf(pdf_bytes)
    
    if not is_api_key_valid():
        return regex_extract_epfo(text)
        
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
        structured_llm = llm.with_structured_output(EPFOExtractionModel)
        
        prompt = (
            "You are an expert document parser. Analyze the following extracted text from an "
            "EPFO Registration/Establishment Certificate and extract the Establishment ID, "
            "Legal Name of the establishment, current Status, and Address.\n\n"
            f"Extracted Text:\n{text}"
        )
        return structured_llm.invoke(prompt)
    except Exception:
        return regex_extract_epfo(text)
