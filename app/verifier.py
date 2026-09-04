import os
import json
import re
from typing import Dict, Any, List, Optional
from app.extractor import GSTExtractionModel, UdyamExtractionModel, EPFOExtractionModel

# --- Loader for Mock Databases ---

def load_json_db(file_name: str) -> List[Dict[str, Any]]:
    """Loads a mock JSON database file."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "mock_portal_data", file_name)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception:
        return []


# --- Robust Name Matching ---

def normalize_name(name: str) -> str:
    """Normalizes names by lowercasing, removing special characters, and stripping common suffixes/prefixes."""
    if not name:
        return ""
    # Lowercase
    name = name.lower()
    # Remove prefix M/S or M/s or MS
    name = re.sub(r'^\bm/s\b|^\bms\b', '', name).strip()
    # Remove punctuation
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    # Remove extra spaces
    name = " ".join(name.split())
    # Suffixes to filter out
    suffixes = {"private", "limited", "pvt", "ltd", "corp", "corporation", "company", "co", "boiler", "boilers", "engineers", "engineering"}
    words = name.split()
    filtered_words = [w for w in words if w not in suffixes]
    return " ".join(filtered_words).strip()


def check_name_match(name1: str, name2: str) -> bool:
    """Compares two names robustly. Returns True if normalized forms match or have significant overlap."""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return False
    # Exact match on normalized forms
    if n1 == n2:
        return True
    # Word overlap matching
    w1 = set(n1.split())
    w2 = set(n2.split())
    if not w1 or not w2:
        return False
    intersection = w1.intersection(w2)
    # If the intersection contains at least 2 words, or is at least 60% of the shorter name's words
    min_length = min(len(w1), len(w2))
    if len(intersection) >= 2 or (len(intersection) / min_length >= 0.6):
        return True
    return False


# --- Individual Verifiers ---

def verify_gst_record(extracted: GSTExtractionModel) -> Dict[str, Any]:
    """Verifies extracted GST against mock portal database records."""
    records = load_json_db("gstn_records.json")
    gstin_input = extracted.gstin.strip().upper()
    
    # Locate record
    db_record = None
    for r in records:
        if r["gstin"].upper() == gstin_input:
            db_record = r
            break
            
    if not db_record:
        return {
            "verified": False,
            "status": "NON_COMPLIANT",
            "reason": f"GSTIN '{gstin_input}' not found in GSTN database.",
            "extracted_details": extracted.model_dump(),
            "portal_details": None,
            "checks": {
                "gstin_exists": False,
                "status_active": False,
                "name_matched": False,
                "state_code_matched": False
            }
        }
        
    # Check matching parameters
    status_active = db_record["status"].lower() == "active"
    name_matched = check_name_match(extracted.legal_name, db_record["legal_name"]) or \
                   (extracted.trade_name and check_name_match(extracted.trade_name, db_record["legal_name"])) or \
                   (extracted.trade_name and check_name_match(extracted.trade_name, db_record["trade_name"]))
                   
    # State code validation (First 2 digits of GSTIN should represent state code)
    state_code_matched = gstin_input.startswith(db_record["state_code"])
    
    is_compliant = status_active and name_matched and state_code_matched
    
    return {
        "verified": True,
        "status": "COMPLIANT" if is_compliant else "NON_COMPLIANT",
        "extracted_details": extracted.model_dump(),
        "portal_details": db_record,
        "checks": {
            "gstin_exists": True,
            "status_active": status_active,
            "name_matched": name_matched,
            "state_code_matched": state_code_matched
        },
        "remarks": [] if is_compliant else [
            f"GST Status is {db_record['status']}" if not status_active else None,
            "Legal/Trade name mismatch between certificate and GSTN portal" if not name_matched else None,
            "GSTIN state prefix does not match registered state code" if not state_code_matched else None
        ]
    }


def verify_udyam_record(extracted: UdyamExtractionModel) -> Dict[str, Any]:
    """Verifies extracted Udyam certificate against mock database."""
    records = load_json_db("udyam_records.json")
    udyam_input = extracted.udyam_number.strip().upper()
    
    db_record = None
    for r in records:
        if r["udyam_number"].upper() == udyam_input:
            db_record = r
            break
            
    if not db_record:
        return {
            "verified": False,
            "status": "NON_COMPLIANT",
            "reason": f"Udyam registration number '{udyam_input}' not found in Udyam portal database.",
            "extracted_details": extracted.model_dump(),
            "portal_details": None,
            "checks": {
                "udyam_exists": False,
                "status_active": False,
                "name_matched": False
            }
        }
        
    status_active = db_record["status"].lower() == "active"
    name_matched = check_name_match(extracted.enterprise_name, db_record["enterprise_name"])
    
    is_compliant = status_active and name_matched
    
    return {
        "verified": True,
        "status": "COMPLIANT" if is_compliant else "NON_COMPLIANT",
        "extracted_details": extracted.model_dump(),
        "portal_details": db_record,
        "checks": {
            "udyam_exists": True,
            "status_active": status_active,
            "name_matched": name_matched
        },
        "remarks": [] if is_compliant else [
            f"Udyam registration is {db_record['status']}" if not status_active else None,
            "Enterprise name mismatch between certificate and Udyam portal" if not name_matched else None
        ]
    }


def verify_epfo_record(extracted: EPFOExtractionModel) -> Dict[str, Any]:
    """Verifies extracted EPFO certificate against mock database."""
    records = load_json_db("epfo_records.json")
    epfo_input = extracted.establishment_id.strip().upper()
    
    db_record = None
    for r in records:
        if r["establishment_id"].upper() == epfo_input:
            db_record = r
            break
            
    if not db_record:
        return {
            "verified": False,
            "status": "NON_COMPLIANT",
            "reason": f"EPFO establishment ID '{epfo_input}' not found in EPFO database.",
            "extracted_details": extracted.model_dump(),
            "portal_details": None,
            "checks": {
                "establishment_exists": False,
                "status_active": False,
                "name_matched": False
            }
        }
        
    status_active = db_record["status"].lower() == "active"
    name_matched = check_name_match(extracted.legal_name, db_record["legal_name"])
    
    is_compliant = status_active and name_matched
    
    return {
        "verified": True,
        "status": "COMPLIANT" if is_compliant else "NON_COMPLIANT",
        "extracted_details": extracted.model_dump(),
        "portal_details": db_record,
        "checks": {
            "establishment_exists": True,
            "status_active": status_active,
            "name_matched": name_matched
        },
        "remarks": [] if is_compliant else [
            f"EPFO establishment is {db_record['status']}" if not status_active else None,
            "Establishment name mismatch between certificate and EPFO portal" if not name_matched else None
        ]
    }


# --- Unified Integrator ---

def generate_unified_bid_compliance_report(
    gst_res: Optional[Dict[str, Any]] = None,
    udyam_res: Optional[Dict[str, Any]] = None,
    epfo_res: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Combines individual results into a unified CPCL GeM Bid Compliance certificate."""
    
    overall_status = "COMPLIANT"
    reasons = []
    
    # Identify cross-document name consistency
    names_to_check = []
    
    # GST Check
    gst_compliance = "NOT_PROVIDED"
    if gst_res:
        gst_compliance = gst_res["status"]
        if gst_compliance == "NON_COMPLIANT":
            overall_status = "NON_COMPLIANT"
            reason = gst_res.get("reason") or "GST verification checks failed."
            reasons.append(f"GST: {reason}")
            
        # Get legal name from portal if found, else extracted
        if gst_res.get("portal_details"):
            names_to_check.append(("GST Portal", gst_res["portal_details"]["legal_name"]))
        else:
            names_to_check.append(("GST Certificate", gst_res["extracted_details"]["legal_name"]))

    # Udyam Check
    udyam_compliance = "NOT_PROVIDED"
    if udyam_res:
        udyam_compliance = udyam_res["status"]
        if udyam_compliance == "NON_COMPLIANT":
            overall_status = "NON_COMPLIANT"
            reason = udyam_res.get("reason") or "Udyam verification checks failed."
            reasons.append(f"Udyam: {reason}")
            
        if udyam_res.get("portal_details"):
            names_to_check.append(("Udyam Portal", udyam_res["portal_details"]["enterprise_name"]))
        else:
            names_to_check.append(("Udyam Certificate", udyam_res["extracted_details"]["enterprise_name"]))

    # EPFO Check
    epfo_compliance = "NOT_PROVIDED"
    if epfo_res:
        epfo_compliance = epfo_res["status"]
        if epfo_compliance == "NON_COMPLIANT":
            overall_status = "NON_COMPLIANT"
            reason = epfo_res.get("reason") or "EPFO verification checks failed."
            reasons.append(f"EPFO: {reason}")
            
        if epfo_res.get("portal_details"):
            names_to_check.append(("EPFO Portal", epfo_res["portal_details"]["legal_name"]))
        else:
            names_to_check.append(("EPFO Certificate", epfo_res["extracted_details"]["legal_name"]))

    # Name Consistency checks across documents
    cross_document_match = True
    name_mismatch_details = []
    if len(names_to_check) > 1:
        base_src, base_name = names_to_check[0]
        for src, name in names_to_check[1:]:
            if not check_name_match(base_name, name):
                cross_document_match = False
                name_mismatch_details.append(f"Name mismatch between {base_src} ('{base_name}') and {src} ('{name}')")
                
        if not cross_document_match:
            overall_status = "NON_COMPLIANT"
            reasons.extend(name_mismatch_details)

    # We require at least one document to proceed with compliance validation
    if not gst_res and not udyam_res and not epfo_res:
        overall_status = "NON_COMPLIANT"
        reasons.append("No verification documents were provided.")

    return {
        "overall_status": overall_status,
        "is_compliant": overall_status == "COMPLIANT",
        "reasons": reasons,
        "document_status": {
            "gst": gst_compliance,
            "udyam": udyam_compliance,
            "epfo": epfo_compliance
        },
        "cross_document_checks": {
            "name_consistency_verified": cross_document_match,
            "mismatch_details": name_mismatch_details
        },
        "details": {
            "gst": gst_res,
            "udyam": udyam_res,
            "epfo": epfo_res
        }
    }
