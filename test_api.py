#!/usr/bin/env python3
"""Comprehensive API endpoint smoke test for SmartClinic."""
import requests, json, sys, time

BASE = "http://localhost:4200"
KC = "http://localhost:8080/realms/smartclinic/protocol/openid-connect/token"

USERS = {
    "recep1": "recep1",
    "doctor1": "doctor1",
    "pharm1": "pharm1",
    "lab1": "lab1",
    "acct1": "acct1",
}

tokens = {}
results = []

def ok(test, detail=""):
    results.append(("PASS", test, detail))
    print(f"  PASS  {test} {detail}")

def fail(test, detail=""):
    results.append(("FAIL", test, detail))
    print(f"  FAIL  {test} {detail}")

def get_token(user):
    if user in tokens:
        return tokens[user]
    r = requests.post(KC, data={
        "grant_type": "password",
        "client_id": "smartclinic-web",
        "username": user,
        "password": USERS[user],
        "scope": "openid",
    })
    if r.status_code == 200:
        tokens[user] = r.json()["access_token"]
        return tokens[user]
    else:
        print(f"  AUTH FAIL {user}: {r.status_code}")
        return None

def auth(user):
    t = get_token(user)
    return {"Authorization": f"Bearer {t}"} if t else {}

def test(method, url, user, expected_status, name, body=None):
    try:
        h = auth(user)
        h["Content-Type"] = "application/json"
        r = requests.request(method, f"{BASE}{url}", headers=h,
                             json=body, timeout=10)
        if r.status_code == expected_status:
            ok(name, f"[{r.status_code}]")
            return r
        else:
            detail = r.text[:200] if r.text else ""
            fail(name, f"[expected {expected_status}, got {r.status_code}] {detail}")
            return r
    except Exception as e:
        fail(name, str(e))
        return None

print("\n" + "="*70)
print("SmartClinic API Smoke Test")
print("="*70)

# ── 1. Authentication ────────────────────────────────────────────────
print("\n── Authentication ──")
for user in USERS:
    t = get_token(user)
    if t:
        ok(f"Token for {user}")
    else:
        fail(f"Token for {user}")

# ── 2. Patient Identity Service ──────────────────────────────────────
print("\n── Patient Identity (/api/patients) ──")
test("GET", "/api/patients/patients?limit=5", "recep1", 200, "List patients (recep1)")
test("GET", "/api/patients/patients?limit=5", "doctor1", 200, "List patients (doctor1)")

# Register a test patient
r = test("POST", "/api/patients/patients", "recep1", 201, "Register patient (recep1)",
    {"given_name": "Test", "family_name": "SmokeTest", "date_of_birth": "1990-01-01",
     "sex": "male", "national_id": f"63-{int(time.time())%1000000}S-63",
     "phone": "+263771000000"})
patient_id = r.json().get("patient_id") if r and r.status_code == 201 else None
if patient_id:
    ok(f"Patient created: {patient_id[:20]}...")
    # Get patient detail
    test("GET", f"/api/patients/patients/{patient_id}", "recep1", 200, "Get patient detail")
else:
    fail("Patient creation - no ID returned")
    # Try to use an existing patient
    r2 = requests.get(f"{BASE}/api/patients/patients?limit=1", headers=auth("recep1"))
    if r2.status_code == 200 and r2.json().get("items"):
        patient_id = r2.json()["items"][0]["patient_id"]
        ok(f"Using existing patient: {patient_id[:20]}...")

# ── 3. Scheduling Service ────────────────────────────────────────────
print("\n── Scheduling (/api/scheduling) ──")
test("GET", "/api/scheduling/appointments?limit=5", "recep1", 200, "List appointments (recep1)")
test("GET", "/api/scheduling/appointments?limit=5", "doctor1", 200, "List appointments (doctor1)")

# Book an appointment
if patient_id:
    r = test("POST", "/api/scheduling/appointments", "recep1", 201, "Book appointment",
        {"patient_id": patient_id, "doctor_id": "570cc378-c53a-4a9a-826b-ee9e10760638",
         "start_at": "2026-04-23T10:00:00Z", "end_at": "2026-04-23T10:30:00Z",
         "reason": "Smoke test visit"})
    appt_id = r.json().get("appointment_id") if r and r.status_code == 201 else None
    if appt_id:
        ok(f"Appointment created: {appt_id[:20]}...")
        test("GET", f"/api/scheduling/appointments/{appt_id}", "recep1", 200, "Get appointment detail")
        # Check in
        test("POST", f"/api/scheduling/appointments/{appt_id}/check-in", "recep1", 204, "Check in appointment")

# ── 4. Clinical Service ──────────────────────────────────────────────
print("\n── Clinical (/api/clinical) ──")
test("GET", "/api/clinical/encounters?limit=5", "doctor1", 200, "List encounters (doctor1)")

# Start an encounter
encounter_id = None
if patient_id:
    r = test("POST", "/api/clinical/encounters", "doctor1", 201, "Start encounter",
        {"patient_id": patient_id, "doctor_id": "doctor1"})
    if r and r.status_code == 201:
        encounter_id = r.json().get("encounter_id")
        ok(f"Encounter created: {encounter_id[:20]}...")

        # Wait for CQRS projection (event sourcing → read model)
        time.sleep(3)

        # Get encounter detail (the bug we fixed)
        test("GET", f"/api/clinical/encounters/{encounter_id}", "doctor1", 200,
             "Get encounter detail (with enc_ prefix)")

        # Record vitals
        test("POST", f"/api/clinical/encounters/{encounter_id}/vital-signs", "doctor1", 204,
             "Record vitals",
             {"temperature_celsius": 37.2, "pulse_bpm": 78, "systolic_bp_mmhg": 120,
              "diastolic_bp_mmhg": 80, "oxygen_saturation_pct": 98})

        # Record SOAP
        test("POST", f"/api/clinical/encounters/{encounter_id}/soap-notes", "doctor1", 204,
             "Record SOAP note",
             {"subjective": "Headache for 2 days", "objective": "Alert, oriented",
              "assessment": "Tension headache", "plan": "Paracetamol 500mg"})

        # Add diagnosis
        test("POST", f"/api/clinical/encounters/{encounter_id}/diagnoses", "doctor1", 204,
             "Add diagnosis",
             {"icd10_code": "G44.1", "description": "Tension-type headache", "is_primary": True})

        # Verify encounter now has data
        time.sleep(1)
        r2 = test("GET", f"/api/clinical/encounters/{encounter_id}", "doctor1", 200,
                   "Get encounter after recording data")
        if r2 and r2.status_code == 200:
            data = r2.json()
            status = data.get("status")
            if status == "in_progress":
                ok("Encounter status is 'in_progress'")
            else:
                fail(f"Encounter status is '{status}' (expected 'in_progress')")

        # Event stream
        test("GET", f"/api/clinical/encounters/{encounter_id}/events", "doctor1", 200,
             "Get event stream")

        # Verify audit chain (hash-chained event store)
        test("GET", f"/api/clinical/encounters/{encounter_id}/audit", "doctor1", 200,
             "Verify audit chain")

# ── 5. Pharmacy Service ──────────────────────────────────────────────
print("\n── Pharmacy (/api/pharmacy) ──")
test("GET", "/api/pharmacy/prescriptions?limit=5", "pharm1", 200, "List prescriptions (pharm1)")
test("GET", "/api/pharmacy/prescriptions?limit=5&status=pending", "pharm1", 200,
     "List pending prescriptions")

# Drug stock endpoints
test("GET", "/api/pharmacy/drug-stock", "pharm1", 200, "List drug stock (pharm1)")
test("GET", "/api/pharmacy/drug-stock?low_stock_only=true", "pharm1", 200, "List low stock drugs")

# ── 6. Laboratory Service ────────────────────────────────────────────
print("\n── Laboratory (/api/laboratory) ──")
test("GET", "/api/laboratory/lab-orders?limit=5", "lab1", 200, "List lab orders (lab1)")
test("GET", "/api/laboratory/lab-orders?limit=5&status=pending", "lab1", 200, "List pending lab orders")
test("GET", "/api/laboratory/lab-orders?limit=5", "doctor1", 200, "List lab orders (doctor1)")

# ── 7. Billing Service ───────────────────────────────────────────────
print("\n── Billing (/api/billing) ──")
test("GET", "/api/billing/invoices?limit=5", "acct1", 200, "List invoices (acct1)")
test("GET", "/api/billing/invoices?limit=5", "doctor1", 200, "List invoices (doctor1)")

# ── 8. RBAC Tests ────────────────────────────────────────────────────
print("\n── RBAC Access Control ──")
# Receptionist should NOT be able to start encounters
test("POST", "/api/clinical/encounters", "recep1", 403, "Recep1 cannot start encounter",
     {"patient_id": patient_id or "dummy", "doctor_id": "doctor1"})

# Lab tech should NOT be able to view prescriptions (requires doctor or pharmacist)
test("GET", "/api/pharmacy/prescriptions?limit=5", "lab1", 403, "Lab1 cannot view prescriptions")

# ── 9. Frontend Pages ────────────────────────────────────────────────
print("\n── Frontend Pages (HTTP 200 check) ──")
for path in ["/", "/index.html"]:
    r = requests.get(f"{BASE}{path}", timeout=5)
    if r.status_code == 200 and "SmartClinic" in r.text:
        ok(f"Frontend serves {path}")
    else:
        fail(f"Frontend {path}", f"[{r.status_code}]")

# ── 10. Keycloak Proxy ───────────────────────────────────────────────
print("\n── Keycloak User Proxy ──")
test("GET", "/api/scheduling/staff/doctors?q=", "recep1", 200,
     "Search doctors (via scheduling staff endpoint)")

# ── Summary ──────────────────────────────────────────────────────────
print("\n" + "="*70)
passes = sum(1 for s, _, _ in results if s == "PASS")
fails = sum(1 for s, _, _ in results if s == "FAIL")
print(f"TOTAL: {passes} passed, {fails} failed, {len(results)} total")
if fails:
    print("\nFailed tests:")
    for s, name, detail in results:
        if s == "FAIL":
            print(f"  ✗ {name} {detail}")
print("="*70)
sys.exit(1 if fails else 0)
