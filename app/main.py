import os
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import our extractors and verifiers
from app.extractor import (
    extract_gst_details,
    extract_udyam_details,
    extract_epfo_details,
    is_api_key_valid
)
from app.verifier import (
    verify_gst_record,
    verify_udyam_record,
    verify_epfo_record,
    generate_unified_bid_compliance_report,
    load_json_db
)

load_dotenv()

app = FastAPI(
    title="CPCL GeM Bid Compliance Verification Platform",
    description="Automated GSTIN, Udyam, and EPFO verification platform for Chennai Petroleum Corporation Limited procurement.",
    version="1.0.0"
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Welcome/Landing API endpoint."""
    return {
        "platform": "Chennai Petroleum Corporation Limited (CPCL)",
        "system": "GeM Procurement Bid Compliance Verification Platform",
        "status": "Operational",
        "api_key_configured": is_api_key_valid(),
        "endpoints": {
            "individual_verification": [
                "/verify/gst",
                "/verify/udyam",
                "/verify/epfo"
            ],
            "unified_verification": "/verify/bid",
            "mock_database": "/mock-records/{type}"
        }
    }


@app.get("/health")
def health_check():
    """Performs health check on service and API dependencies."""
    return {
        "status": "healthy",
        "gemini_api_active": is_api_key_valid(),
        "storage": {
            "gstn_db_loaded": len(load_json_db("gstn_records.json")) > 0,
            "udyam_db_loaded": len(load_json_db("udyam_records.json")) > 0,
            "epfo_db_loaded": len(load_json_db("epfo_records.json")) > 0
        }
    }


@app.post("/verify/gst")
async def verify_gst_endpoint(file: UploadFile = File(...)):
    """Verifies a single GST Certificate PDF file against the GSTN database."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF certificates are accepted.")
        
    try:
        pdf_bytes = await file.read()
        extracted = extract_gst_details(pdf_bytes)
        verification_report = verify_gst_record(extracted)
        return verification_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process GST Certificate: {str(e)}")


@app.post("/verify/udyam")
async def verify_udyam_endpoint(file: UploadFile = File(...)):
    """Verifies a single Udyam Registration Certificate PDF file against the Udyam database."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF certificates are accepted.")
        
    try:
        pdf_bytes = await file.read()
        extracted = extract_udyam_details(pdf_bytes)
        verification_report = verify_udyam_record(extracted)
        return verification_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process Udyam Certificate: {str(e)}")


@app.post("/verify/epfo")
async def verify_epfo_endpoint(file: UploadFile = File(...)):
    """Verifies a single EPFO Establishment Certificate PDF file against the EPFO database."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF certificates are accepted.")
        
    try:
        pdf_bytes = await file.read()
        extracted = extract_epfo_details(pdf_bytes)
        verification_report = verify_epfo_record(extracted)
        return verification_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process EPFO Certificate: {str(e)}")


@app.post("/verify/bid")
async def verify_unified_bid_endpoint(
    gst_file: Optional[UploadFile] = File(None),
    udyam_file: Optional[UploadFile] = File(None),
    epfo_file: Optional[UploadFile] = File(None)
):
    """
    Unified Endpoint for GeM compliance checks.
    Accepts up to three PDF files (GST, Udyam, EPFO), extracts details from each,
    cross-references names across files, checks statuses against mock databases,
    and returns a definitive compliance certificate.
    """
    gst_res = None
    udyam_res = None
    epfo_res = None
    
    if not gst_file and not udyam_file and not epfo_file:
        raise HTTPException(
            status_code=400, 
            detail="At least one compliance document (GST, Udyam, or EPFO) must be uploaded."
        )

    # 1. Process GST
    if gst_file:
        if not gst_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="GST Certificate must be a PDF file.")
        try:
            pdf_bytes = await gst_file.read()
            extracted = extract_gst_details(pdf_bytes)
            gst_res = verify_gst_record(extracted)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process GST Certificate: {str(e)}")

    # 2. Process Udyam
    if udyam_file:
        if not udyam_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Udyam Certificate must be a PDF file.")
        try:
            pdf_bytes = await udyam_file.read()
            extracted = extract_udyam_details(pdf_bytes)
            udyam_res = verify_udyam_record(extracted)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process Udyam Certificate: {str(e)}")

    # 3. Process EPFO
    if epfo_file:
        if not epfo_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="EPFO Certificate must be a PDF file.")
        try:
            pdf_bytes = await epfo_file.read()
            extracted = extract_epfo_details(pdf_bytes)
            epfo_res = verify_epfo_record(extracted)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process EPFO Certificate: {str(e)}")

    # 4. Generate the unified certificate
    unified_report = generate_unified_bid_compliance_report(gst_res, udyam_res, epfo_res)
    return unified_report


@app.get("/mock-records/{type}")
def get_mock_records(type: str):
    """Retrieve dummy/mock portal records for reference/testing."""
    if type == "gst":
        return load_json_db("gstn_records.json")
    elif type == "udyam":
        return load_json_db("udyam_records.json")
    elif type == "epfo":
        return load_json_db("epfo_records.json")
    else:
        raise HTTPException(
            status_code=404, 
            detail="Invalid record type. Must be one of 'gst', 'udyam', or 'epfo'."
        )
