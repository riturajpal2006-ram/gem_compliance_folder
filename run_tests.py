import os
import fitz  # PyMuPDF
from fastapi.testclient import TestClient

# Create the test PDFs
def create_test_pdfs():
    print("Generating mock PDF certificates for testing...")
    
    # 1. Valid GST Certificate for Super Mech
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Government of India\nForm GST REG-06\nRegistration Certificate")
    page.insert_text((50, 100), "Registration Number: 33ABCDE1234F1Z5")
    page.insert_text((50, 120), "Legal Name: Super Mech Engineers Chennai Private Limited")
    page.insert_text((50, 140), "Trade Name: Super Mech Engineers")
    page.insert_text((50, 160), "Status: Active")
    page.insert_text((50, 180), "State: Tamil Nadu")
    doc.save("test_super_mech_gst.pdf")
    doc.close()

    # 2. Valid Udyam Certificate for Super Mech
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "UDYAM REGISTRATION CERTIFICATE")
    page.insert_text((50, 100), "UDYAM REGISTRATION NUMBER: UDYAM-TN-01-0012345")
    page.insert_text((50, 120), "NAME OF ENTERPRISE: Super Mech Engineers Chennai Private Limited")
    page.insert_text((50, 140), "MAJOR ACTIVITY: Manufacturing")
    page.insert_text((50, 160), "ENTERPRISE TYPE: Small")
    doc.save("test_super_mech_udyam.pdf")
    doc.close()

    # 3. Valid EPFO Certificate for Super Mech
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "EMPLOYEES' PROVIDENT FUND ORGANISATION")
    page.insert_text((50, 100), "Establishment ID: TNMAS0012345000")
    page.insert_text((50, 120), "Name of Establishment: Super Mech Engineers Chennai Private Limited")
    page.insert_text((50, 140), "Status: Active")
    doc.save("test_super_mech_epfo.pdf")
    doc.close()

    # 4. Inactive GST Certificate (Apex Boiler - Suspended)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Government of India\nForm GST REG-06\nRegistration Certificate")
    page.insert_text((50, 100), "Registration Number: 33EFGHI9012J1Z0")
    page.insert_text((50, 120), "Legal Name: Apex Boiler Services Ltd")
    page.insert_text((50, 140), "Trade Name: Apex Boilers")
    page.insert_text((50, 160), "Status: Suspended")
    doc.save("test_apex_boiler_gst.pdf")
    doc.close()

    print("Mock PDF certificates successfully generated!")


def run_api_tests():
    from app.main import app
    client = TestClient(app)
    
    print("\n--- Running API Integration Tests ---")
    
    # 1. Test Home/Root Endpoint
    print("\n[Test 1] Testing Root Endpoint...")
    res = client.get("/")
    assert res.status_code == 200
    print("Result:", res.json())

    # 2. Test Health Endpoint
    print("\n[Test 2] Testing Health Endpoint...")
    res = client.get("/health")
    assert res.status_code == 200
    print("Result:", res.json())

    # 3. Test GST Verification
    print("\n[Test 3] Testing GST Verification (Valid)...")
    with open("test_super_mech_gst.pdf", "rb") as f:
        res = client.post("/verify/gst", files={"file": ("test_super_mech_gst.pdf", f, "application/pdf")})
    assert res.status_code == 200
    gst_json = res.json()
    print("Result (is_compliant):", gst_json.get("status"))
    assert gst_json.get("status") == "COMPLIANT"

    # 4. Test Udyam Verification
    print("\n[Test 4] Testing Udyam Verification (Valid)...")
    with open("test_super_mech_udyam.pdf", "rb") as f:
        res = client.post("/verify/udyam", files={"file": ("test_super_mech_udyam.pdf", f, "application/pdf")})
    assert res.status_code == 200
    udyam_json = res.json()
    print("Result (is_compliant):", udyam_json.get("status"))
    assert udyam_json.get("status") == "COMPLIANT"

    # 5. Test EPFO Verification
    print("\n[Test 5] Testing EPFO Verification (Valid)...")
    with open("test_super_mech_epfo.pdf", "rb") as f:
        res = client.post("/verify/epfo", files={"file": ("test_super_mech_epfo.pdf", f, "application/pdf")})
    assert res.status_code == 200
    epfo_json = res.json()
    print("Result (is_compliant):", epfo_json.get("status"))
    assert epfo_json.get("status") == "COMPLIANT"

    # 6. Test Inactive GST Verification (Apex Boiler - Suspended)
    print("\n[Test 6] Testing GST Verification (Suspended GST)...")
    with open("test_apex_boiler_gst.pdf", "rb") as f:
        res = client.post("/verify/gst", files={"file": ("test_apex_boiler_gst.pdf", f, "application/pdf")})
    assert res.status_code == 200
    apex_json = res.json()
    print("Result (is_compliant):", apex_json.get("status"))
    assert apex_json.get("status") == "NON_COMPLIANT"
    print("Remarks:", apex_json.get("remarks"))

    # 7. Test Unified Bid Verification (All Valid - COMPLIANT overall)
    print("\n[Test 7] Testing Unified GeM Bid Compliance (All documents valid & matching)...")
    with open("test_super_mech_gst.pdf", "rb") as f_gst, \
         open("test_super_mech_udyam.pdf", "rb") as f_udyam, \
         open("test_super_mech_epfo.pdf", "rb") as f_epfo:
        
        res = client.post(
            "/verify/bid",
            files={
                "gst_file": ("test_super_mech_gst.pdf", f_gst, "application/pdf"),
                "udyam_file": ("test_super_mech_udyam.pdf", f_udyam, "application/pdf"),
                "epfo_file": ("test_super_mech_epfo.pdf", f_epfo, "application/pdf")
            }
        )
    assert res.status_code == 200
    unified_json = res.json()
    print("Overall Status:", unified_json.get("overall_status"))
    print("Reasons/Mismatches:", unified_json.get("reasons"))
    assert unified_json.get("overall_status") == "COMPLIANT"

    # 8. Test Unified Bid Verification (Mismatch - e.g. GST Apex Boiler & Udyam Super Mech)
    print("\n[Test 8] Testing Unified GeM Bid Compliance (Mismatching enterprise names)...")
    with open("test_apex_boiler_gst.pdf", "rb") as f_gst, \
         open("test_super_mech_udyam.pdf", "rb") as f_udyam:
         
        res = client.post(
            "/verify/bid",
            files={
                "gst_file": ("test_apex_boiler_gst.pdf", f_gst, "application/pdf"),
                "udyam_file": ("test_super_mech_udyam.pdf", f_udyam, "application/pdf")
            }
        )
    assert res.status_code == 200
    mismatch_json = res.json()
    print("Overall Status:", mismatch_json.get("overall_status"))
    print("Reasons/Mismatches:", mismatch_json.get("reasons"))
    assert mismatch_json.get("overall_status") == "NON_COMPLIANT"

    print("\nAll integration and compliance checks passed successfully!")


def cleanup_test_pdfs():
    print("\nCleaning up test PDF files...")
    files_to_remove = [
        "test_super_mech_gst.pdf",
        "test_super_mech_udyam.pdf",
        "test_super_mech_epfo.pdf",
        "test_apex_boiler_gst.pdf"
    ]
    for f in files_to_remove:
        if os.path.exists(f):
            os.remove(f)
    print("Cleanup completed.")


if __name__ == "__main__":
    create_test_pdfs()
    try:
        run_api_tests()
    finally:
        cleanup_test_pdfs()
