#!/usr/bin/env python3
"""SmartClinic demo seed script — 7 Zimbabwean patients, all scenario paths.

API field reference (verified against service DTOs):
  POST /patients          → given_name, family_name, national_id, date_of_birth, sex, email, phone
  POST /patients/{id}/consents → purpose  ("treatment" | "billing" | ...)
  POST /appointments      → patient_id (UUID), doctor_id (UUID), start_at, end_at, reason
  POST /encounters        → patient_id (str), appointment_id (str|None)
  POST /encounters/{id}/vital-signs → temperature_celsius, systolic_bp_mmhg, diastolic_bp_mmhg,
                                      pulse_bpm, respiratory_rate_rpm, oxygen_saturation_pct,
                                      weight_kg, height_cm
  POST /encounters/{id}/soap-notes  → subjective, objective, assessment, plan
  POST /encounters/{id}/diagnoses   → icd10_code, description, is_primary
  POST /encounters/{id}/prescriptions → lines[{drug_name, dose, route, frequency,
                                               duration_days, instructions}]
  POST /encounters/{id}/lab-orders  → tests[{test_code, urgency, notes}]
  POST /encounters/{id}/close       → (no body)
  POST /lab-orders/{id}/collect-sample  → sample_type
  POST /lab-orders/{id}/record-result   → test_code, test_name, value, unit,
                                          reference_range_lower, reference_range_upper,
                                          reference_range_unit, interpretation, notes
  POST /lab-orders/{id}/complete    → (no body)
  GET  /lab-orders?patient_id=&status_filter=
  GET  /prescriptions?patient_id=&status_filter=
  POST /prescriptions/{id}/dispense → (no body)
  GET  /invoices?patient_id=&status_filter=
  POST /invoices/{id}/issue         → (no body)
  POST /invoices/{id}/record-payment → amount, currency, method, reference

Keycloak: client_id=smartclinic-api, client_secret=smartclinic-api-secret
Users: doctor1/doctor1, recep1/recep1, pharm1/pharm1, lab1/lab1, acct1/acct1

Usage:
  docker compose --profile seed up seeder   # inside Docker (recommended)
  pip install httpx && python ops/seed/seed.py   # locally
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

# Wall-clock baseline for appointment slots. We pin all demo appointments to a
# single "clinic day" that starts 10 minutes from seeder launch so every run
# books strictly-future slots — the scheduling aggregate rejects past starts.
_BASE = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(
    minute=0, second=0, microsecond=0
) + timedelta(hours=1)


def _slot(offset_minutes: int, duration_minutes: int = 30) -> tuple[str, str]:
    """Return (start_iso, end_iso) for a slot ``offset_minutes`` after the base."""
    start = _BASE + timedelta(minutes=offset_minutes)
    end = start + timedelta(minutes=duration_minutes)
    return start.isoformat(), end.isoformat()

BASE         = os.getenv("BASE_URL", "http://localhost")
KEYCLOAK     = os.getenv("KEYCLOAK_URL",  f"{BASE}:8080")
PATIENT_API  = os.getenv("PATIENT_API",  f"{BASE}:8001")
SCHEDULE_API = os.getenv("SCHEDULE_API", f"{BASE}:8002")
CLINICAL_API = os.getenv("CLINICAL_API", f"{BASE}:8003")
PHARMACY_API = os.getenv("PHARMACY_API", f"{BASE}:8004")
LAB_API      = os.getenv("LAB_API",      f"{BASE}:8005")
BILLING_API  = os.getenv("BILLING_API",  f"{BASE}:8006")

REALM         = "smartclinic"
CLIENT_ID     = "smartclinic-api"
CLIENT_SECRET = "smartclinic-api-secret"
TIMEOUT       = httpx.Timeout(30.0)


# ---------------------------------------------------------------------------
# HTTP helpers

def _token(username: str, password: str) -> str:
    url = f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token"
    resp = httpx.post(url, data={
        "grant_type":    "password",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username":      username,
        "password":      password,
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _post(url: str, body: dict, token: str) -> dict:
    resp = httpx.post(url, json=body, headers=_h(token), timeout=TIMEOUT)
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code} {url}: {resp.text[:400]}", file=sys.stderr)
        resp.raise_for_status()
    return resp.json() if resp.content else {}


def _get(url: str, token: str, params: dict | None = None) -> dict:
    resp = httpx.get(url, headers=_h(token), params=params or {}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _wait(ms: int = 500) -> None:
    time.sleep(ms / 1000)


def _seed_stock() -> None:
    """Insert pharmacy drug stock directly into postgres — bypasses the API
    since the pharmacy service has no stock-management endpoint."""
    import psycopg2
    drugs = [
        ("Amoxicillin",        200, "tablets"),
        ("Paracetamol",        500, "tablets"),
        ("Metformin",          300, "tablets"),
        ("Atorvastatin",       150, "tablets"),
        ("Amlodipine",         150, "tablets"),
        ("Lisinopril",         150, "tablets"),
        ("Salbutamol Inhaler",  50, "inhalers"),
        ("Prednisolone",       120, "tablets"),
        ("Cotrimoxazole",      200, "tablets"),
        ("Ibuprofen",          300, "tablets"),
        ("Omeprazole",          80, "capsules"),
        ("Aspirin",             80, "tablets"),
        ("Ciprofloxacin",      100, "tablets"),
        ("Doxycycline",        100, "tablets"),
        ("Ferrous Sulphate",   200, "tablets"),
        # Warfarin intentionally NOT stocked — triggers OOS saga demo
    ]
    conn = psycopg2.connect(
        host=os.getenv("PHARMACY_DB_HOST", "localhost"),
        port=int(os.getenv("PHARMACY_DB_PORT", "5432")),
        dbname=os.getenv("PHARMACY_DB_NAME", "pharmacy"),
        user=os.getenv("PHARMACY_DB_USER", "pharmacy"),
        password=os.getenv("PHARMACY_DB_PASS", "pharmacy"),
    )
    conn.autocommit = True
    cur = conn.cursor()
    for name, qty, unit in drugs:
        cur.execute("""
            INSERT INTO drug_stock (id, drug_name, quantity_on_hand, unit, reorder_threshold)
            VALUES (gen_random_uuid(), %s, %s, %s, 20)
            ON CONFLICT (drug_name) DO UPDATE
              SET quantity_on_hand = EXCLUDED.quantity_on_hand
        """, (name, qty, unit))
        print(f"  [stock]        {name} × {qty} {unit}")
    cur.close()
    conn.close()


# ---------------------------------------------------------------------------
# Domain helpers

def _lookup_patient_by_national_id(national_id: str) -> str | None:
    """Direct-DB lookup of a patient ID by national ID (used for idempotent re-runs)."""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=os.getenv("PATIENT_DB_HOST", os.getenv("PHARMACY_DB_HOST", "postgres")),
            port=int(os.getenv("PATIENT_DB_PORT", os.getenv("PHARMACY_DB_PORT", "5432"))),
            dbname=os.getenv("PATIENT_DB_NAME", "patient_identity"),
            user=os.getenv("PATIENT_DB_USER", "patient_identity"),
            password=os.getenv("PATIENT_DB_PASS", "patient_identity"),
        )
        cur = conn.cursor()
        cur.execute("SELECT id FROM patients WHERE national_id = %s LIMIT 1", (national_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return str(row[0]) if row else None
    except Exception:
        return None


def seed_patient(tok: str, given: str, family: str, dob: str, sex: str,
                 national_id: str, email: str, phone: str) -> str:
    # Idempotent: if a patient with this national_id already exists from a
    # prior run, reuse it instead of failing.
    existing = _lookup_patient_by_national_id(national_id)
    if existing:
        print(f"  [patient]      {given} {family} → {existing[:12]}… (existing)")
        return existing
    r = _post(f"{PATIENT_API}/patients", {
        "given_name":  given,
        "family_name": family,
        "date_of_birth": dob,
        "sex":         sex,
        "national_id": national_id,
        "email":       email,
        "phone":       phone,
    }, tok)
    pid = str(r["patient_id"])
    print(f"  [patient]      {given} {family} → {pid[:12]}…")
    return pid


def grant_consent(tok: str, pid: str) -> None:
    # Consent grant is idempotent at the domain level; silently ignore 4xx
    # from the service if a purpose is already granted.
    for purpose in ("treatment", "billing"):
        try:
            _post(f"{PATIENT_API}/patients/{pid}/consents", {"purpose": purpose}, tok)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 422:
                raise
    print(f"  [consent]      treatment + billing granted")


def book_appointment(tok: str, patient_id: str, doctor_id: str,
                     start: str, end: str, reason: str = "Consultation") -> str:
    r = _post(f"{SCHEDULE_API}/appointments", {
        "patient_id": patient_id,
        "doctor_id":  doctor_id,
        "start_at":   start,
        "end_at":     end,
        "reason":     reason,
    }, tok)
    appt_id = str(r["appointment_id"])
    print(f"  [appointment]  {start[11:16]} → {appt_id[:12]}…")
    return appt_id


def check_in(tok: str, appt_id: str) -> None:
    _post(f"{SCHEDULE_API}/appointments/{appt_id}/check-in", {}, tok)
    print(f"  [check-in]     done")


def cancel_appointment(tok: str, appt_id: str) -> None:
    _post(f"{SCHEDULE_API}/appointments/{appt_id}/cancel",
          {"reason": "patient_request"}, tok)
    print(f"  [cancel]       appointment cancelled")


def start_encounter(tok: str, patient_id: str, appt_id: str,
                    doctor_id: str) -> str:
    r = _post(f"{CLINICAL_API}/encounters", {
        "patient_id":     patient_id,
        "doctor_id":      doctor_id,
        "appointment_id": appt_id,
    }, tok)
    enc = str(r["encounter_id"])
    print(f"  [encounter]    started → {enc[:12]}…")
    return enc


def record_vitals(tok: str, enc: str, temp=37.1, sbp=122, dbp=78,
                  hr=76, rr=16, spo2=98.5, wt=68.0, ht=165.0) -> None:
    _post(f"{CLINICAL_API}/encounters/{enc}/vital-signs", {
        "temperature_celsius":    temp,
        "systolic_bp_mmhg":       sbp,
        "diastolic_bp_mmhg":      dbp,
        "pulse_bpm":              hr,
        "respiratory_rate_rpm":   rr,
        "oxygen_saturation_pct":  spo2,
        "weight_kg":              wt,
        "height_cm":              ht,
    }, tok)
    print(f"  [vitals]       T={temp} BP={sbp}/{dbp} HR={hr}")


def add_soap(tok: str, enc: str, s: str, o: str, a: str, p: str) -> None:
    _post(f"{CLINICAL_API}/encounters/{enc}/soap-notes",
          {"subjective": s, "objective": o, "assessment": a, "plan": p}, tok)
    print(f"  [SOAP]         recorded")


def add_dx(tok: str, enc: str, code: str, desc: str, primary=False) -> None:
    _post(f"{CLINICAL_API}/encounters/{enc}/diagnoses",
          {"icd10_code": code, "description": desc, "is_primary": primary}, tok)
    print(f"  [diagnosis]    {code} {desc}")


def prescribe(tok: str, enc: str, lines: list[dict]) -> None:
    _post(f"{CLINICAL_API}/encounters/{enc}/prescriptions", {"lines": lines}, tok)
    print(f"  [rx]           {', '.join(l['drug_name'] for l in lines)}")


def lab_order(tok: str, enc: str, tests: list[dict]) -> None:
    _post(f"{CLINICAL_API}/encounters/{enc}/lab-orders", {"tests": tests}, tok)
    print(f"  [lab]          {', '.join(t['test_code'] for t in tests)}")


def close_enc(tok: str, enc: str) -> None:
    _post(f"{CLINICAL_API}/encounters/{enc}/close", {}, tok)
    print(f"  [encounter]    closed")




def _poll_items(url: str, tok: str, params: dict, attempts: int = 8, delay_ms: int = 500) -> list:
    """Poll a list endpoint until it returns items (async event handler timing)."""
    for _ in range(attempts):
        r = _get(url, tok, params)
        items = r.get("items", [])
        if items:
            return items
        _wait(delay_ms)
    return []


def dispense(pharm_tok: str, patient_id: str) -> None:
    try:
        items = _poll_items(
            f"{PHARMACY_API}/prescriptions", pharm_tok,
            {"patient_id": patient_id, "status_filter": "pending", "limit": "1"},
        )
        if not items:
            print(f"  WARN: no pending rx for patient")
            return
        rx_id = items[0]["prescription_id"]
        res = _post(f"{PHARMACY_API}/prescriptions/{rx_id}/dispense", {}, pharm_tok)
        print(f"  [dispense]     outcome={res.get('outcome','dispensed')}")
    except Exception as e:
        print(f"  WARN: dispense failed ({e})")


def complete_lab(lab_tok: str, patient_id: str, results: list[dict]) -> None:
    try:
        items = _poll_items(
            f"{LAB_API}/lab-orders", lab_tok,
            {"patient_id": patient_id, "status_filter": "pending", "limit": "1"},
        )
        if not items:
            print(f"  WARN: no pending lab order for patient")
            return
        oid = items[0]["order_id"]
        _post(f"{LAB_API}/lab-orders/{oid}/collect-sample", {"sample_type": "blood"}, lab_tok)
        for res in results:
            _post(f"{LAB_API}/lab-orders/{oid}/record-result", res, lab_tok)
        _post(f"{LAB_API}/lab-orders/{oid}/complete", {}, lab_tok)
        print(f"  [lab]          completed — {len(results)} result(s)")
    except Exception as e:
        print(f"  WARN: lab completion failed ({e})")


def issue_and_pay(acc_tok: str, patient_id: str,
                  amount: str = "20.00", method: str = "cash", ref: str = "CASH") -> None:
    _wait(1000)
    try:
        r = _get(f"{BILLING_API}/invoices", acc_tok,
                 {"patient_id": patient_id, "status_filter": "draft", "limit": "1"})
        items = r.get("items", [])
        if not items:
            print(f"  WARN: no draft invoice for patient")
            return
        inv_id = items[0]["invoice_id"]
        _post(f"{BILLING_API}/invoices/{inv_id}/issue", {}, acc_tok)
        _post(f"{BILLING_API}/invoices/{inv_id}/record-payment",
              {"amount": amount, "currency": "USD", "method": method, "reference": ref}, acc_tok)
        print(f"  [invoice]      issued + paid ${amount} via {method}")
    except Exception as e:
        print(f"  WARN: invoice/payment failed ({e})")


def issue_only(acc_tok: str, patient_id: str) -> None:
    _wait(1000)
    try:
        r = _get(f"{BILLING_API}/invoices", acc_tok,
                 {"patient_id": patient_id, "status_filter": "draft", "limit": "1"})
        items = r.get("items", [])
        if not items:
            print(f"  WARN: no draft invoice for patient")
            return
        inv_id = items[0]["invoice_id"]
        _post(f"{BILLING_API}/invoices/{inv_id}/issue", {}, acc_tok)
        print(f"  [invoice]      issued (payment pending)")
    except Exception as e:
        print(f"  WARN: invoice issue failed ({e})")


# ---------------------------------------------------------------------------
# Main

def main() -> None:
    print("=" * 60)
    print("  SmartClinic Demo Seed  —  7 Patients")
    print("=" * 60)

    # ── Authenticate ──────────────────────────────────────────
    print("\n[1/8] Authenticating…")
    try:
        rec  = _token("recep1",  "recep1")
        doc  = _token("doctor1", "doctor1")
        pharm = _token("pharm1", "pharm1")
        lab  = _token("lab1",    "lab1")
        acc  = _token("acct1",   "acct1")
    except Exception as exc:
        print(f"\n  AUTH FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
    print("  All tokens acquired.")

    # ── Get doctor UUID ───────────────────────────────────────
    # doctor1's UUID is the Keycloak subject; fetch it from the token
    import base64, json as _json
    def _sub(token: str) -> str:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return _json.loads(base64.b64decode(payload))["sub"]
    DOCTOR_ID = _sub(doc)
    print(f"  Doctor UUID: {DOCTOR_ID}")

    # ── Seed pharmacy stock directly into postgres ────────────
    print("\n[2/8] Seeding pharmacy stock (direct DB insert)…")
    _seed_stock()

    # =================================================================
    # PATIENT 1: Chipo Moyo — full happy path
    # =================================================================
    print("\n[3/8] Patient 1: Chipo Moyo — happy path")
    p1 = seed_patient(rec, "Chipo", "Moyo", "1985-04-12", "female",
                      "63-123456A-75", "chipo.moyo@demo.zw", "+263771234567")
    grant_consent(rec, p1)
    s1, e1_end = _slot(0)
    a1 = book_appointment(rec, p1, DOCTOR_ID, s1, e1_end,
                          "Chest tightness and cough for 4 days")
    check_in(rec, a1)
    e1 = start_encounter(doc, p1, a1, DOCTOR_ID)
    record_vitals(doc, e1, temp=37.4, sbp=128, dbp=82, hr=88, spo2=97.0, wt=65.0, ht=162.0)
    add_soap(doc, e1,
             s="Mild chest tightness, productive cough and low-grade fever × 4 days.",
             o="Mild wheeze bilaterally. No accessory muscle use. SpO2 97%.",
             a="Acute bronchitis with mild bronchospasm. Viral aetiology most likely.",
             p="Bronchodilator inhaler PRN, paracetamol for fever. Review in 5 days.")
    add_dx(doc, e1, "J20.9", "Acute bronchitis, unspecified", primary=True)
    add_dx(doc, e1, "J45.20", "Mild intermittent asthma, uncomplicated")
    prescribe(doc, e1, [
        {"drug_name": "Salbutamol Inhaler", "dose": "2 puffs", "route": "inhaled",
         "frequency": "QDS PRN", "duration_days": 10, "instructions": "Shake well before use"},
        {"drug_name": "Paracetamol", "dose": "1g", "route": "oral",
         "frequency": "QDS", "duration_days": 5, "instructions": "As needed for fever"},
    ])
    lab_order(doc, e1, [
        {"test_code": "FBC",  "urgency": "routine", "notes": "Full blood count"},
        {"test_code": "CRP",  "urgency": "routine", "notes": "C-reactive protein"},
    ])
    close_enc(doc, e1)
    dispense(pharm, p1)
    complete_lab(lab, p1, [
        {"test_code": "FBC", "test_name": "Full Blood Count",
         "value": "Hb 13.2, WBC 8.4, Plt 245", "unit": "mixed",
         "interpretation": "normal", "notes": "No neutrophilia — viral pattern"},
        {"test_code": "CRP", "test_name": "C-Reactive Protein",
         "value": "12", "unit": "mg/L",
         "reference_range_lower": "0", "reference_range_upper": "10",
         "reference_range_unit": "mg/L", "interpretation": "high",
         "notes": "Mildly elevated"},
    ])
    issue_and_pay(acc, p1, "18.00", "cash", "REC-CH001")
    print("  → Complete.")

    # =================================================================
    # PATIENT 2: Tendai Dube — OOS saga compensation
    # =================================================================
    print("\n[4/8] Patient 2: Tendai Dube — OOS saga compensation")
    p2 = seed_patient(rec, "Tendai", "Dube", "1962-11-30", "male",
                      "48-654321B-32", "tendai.dube@demo.zw", "+263772345678")
    grant_consent(rec, p2)
    s2, e2_end = _slot(60)
    a2 = book_appointment(rec, p2, DOCTOR_ID, s2, e2_end,
                          "AF anticoagulation clinic review")
    check_in(rec, a2)
    e2 = start_encounter(doc, p2, a2, DOCTOR_ID)
    record_vitals(doc, e2, temp=36.8, sbp=138, dbp=88, hr=92, spo2=96.5, wt=82.0, ht=175.0)
    add_soap(doc, e2,
             s="Known AF on anticoagulation. Routine INR review. No bleeding.",
             o="Irregularly irregular pulse 92bpm. BP 138/88. Chest clear.",
             a="Persistent AF — INR subtherapeutic. Anticoagulation adjustment required.",
             p="Continue Warfarin at adjusted dose. Recheck INR in 1 week.")
    add_dx(doc, e2, "I48.11", "Longstanding persistent atrial fibrillation", primary=True)
    prescribe(doc, e2, [
        {"drug_name": "Warfarin", "dose": "5mg", "route": "oral",
         "frequency": "OD", "duration_days": 30, "instructions": "Take at same time daily. Avoid NSAIDs."},
    ])
    close_enc(doc, e2)
    print("  → Warfarin NOT in stock. Pharmacist dispense will trigger OOS spec + saga compensation.")

    # =================================================================
    # PATIENT 3: Rudo Nhamo — completed lab results
    # =================================================================
    print("\n[5/8] Patient 3: Rudo Nhamo — DM review, lab complete")
    p3 = seed_patient(rec, "Rudo", "Nhamo", "1990-07-20", "female",
                      "90-789012C-50", "rudo.nhamo@demo.zw", "+263773456789")
    grant_consent(rec, p3)
    s3, e3_end = _slot(120)
    a3 = book_appointment(rec, p3, DOCTOR_ID, s3, e3_end,
                          "Annual diabetic review — HbA1c monitoring")
    check_in(rec, a3)
    e3 = start_encounter(doc, p3, a3, DOCTOR_ID)
    record_vitals(doc, e3, temp=36.9, sbp=132, dbp=84, hr=78, spo2=99.0, wt=72.0, ht=168.0)
    add_soap(doc, e3,
             s="Known T2DM × 6 years. On Metformin. Occasional polyuria. No hypos.",
             o="BMI 25.5. BP 132/84. No neuropathy. Pedal pulses intact.",
             a="T2DM — glycaemic control suboptimal. Annual review.",
             p="Continue Metformin 500mg BD. Dietary counselling. Review HbA1c.")
    add_dx(doc, e3, "E11.9", "Type 2 diabetes mellitus without complications", primary=True)
    add_dx(doc, e3, "I10",   "Essential (primary) hypertension")
    prescribe(doc, e3, [
        {"drug_name": "Metformin",  "dose": "500mg", "route": "oral",
         "frequency": "BD", "duration_days": 90, "instructions": "Take with meals"},
        {"drug_name": "Lisinopril", "dose": "10mg",  "route": "oral",
         "frequency": "OD", "duration_days": 90, "instructions": "Monitor BP and renal function"},
    ])
    lab_order(doc, e3, [
        {"test_code": "HBA1C",  "urgency": "routine", "notes": "Glycated haemoglobin"},
        {"test_code": "U&E",    "urgency": "routine", "notes": "Urea & electrolytes"},
        {"test_code": "LFT",    "urgency": "routine", "notes": "Liver function"},
        {"test_code": "LIPIDS", "urgency": "routine", "notes": "Fasting lipid profile"},
    ])
    close_enc(doc, e3)
    dispense(pharm, p3)
    complete_lab(lab, p3, [
        {"test_code": "HBA1C", "test_name": "HbA1c",
         "value": "8.4", "unit": "%",
         "reference_range_lower": "4.0", "reference_range_upper": "6.5",
         "reference_range_unit": "%", "interpretation": "high",
         "notes": "Above target — glycaemic control not achieved"},
        {"test_code": "U&E", "test_name": "Urea & Electrolytes",
         "value": "Na 140 K 4.1 Urea 5.2 Creat 82", "unit": "mmol/L",
         "interpretation": "normal"},
        {"test_code": "LFT", "test_name": "Liver Function Tests",
         "value": "ALT 28 AST 24 ALP 65 Bili 12", "unit": "IU/L",
         "interpretation": "normal"},
        {"test_code": "LIPIDS", "test_name": "Fasting Lipid Profile",
         "value": "TC 5.8 LDL 3.6 HDL 1.1 TG 2.1", "unit": "mmol/L",
         "interpretation": "high", "notes": "Elevated LDL — consider statin"},
    ])
    issue_and_pay(acc, p3, "32.00", "insurance", "PSMAS-2026-0441")
    print("  → Complete.")

    # =================================================================
    # PATIENT 4: Farai Mutasa — drug interaction scenario
    # =================================================================
    print("\n[6/8] Patient 4: Farai Mutasa — drug interaction demo")
    p4 = seed_patient(rec, "Farai", "Mutasa", "1978-03-05", "male",
                      "78-321654D-44", "farai.mutasa@demo.zw", "+263774567890")
    grant_consent(rec, p4)
    s4, e4_end = _slot(150)
    a4 = book_appointment(rec, p4, DOCTOR_ID, s4, e4_end,
                          "Chest pain and hypertension evaluation")
    check_in(rec, a4)
    e4 = start_encounter(doc, p4, a4, DOCTOR_ID)
    record_vitals(doc, e4, temp=36.7, sbp=145, dbp=92, hr=84, spo2=98.0, wt=90.0, ht=180.0)
    add_soap(doc, e4,
             s="Exertional chest tightness and palpitations. Already on Aspirin.",
             o="BP 145/92. Mild tachycardia. No S3/S4. ECG: sinus rhythm.",
             a="Hypertensive heart disease. Chest pain likely musculoskeletal.",
             p="Add Amlodipine for BP. Continue Aspirin. Avoid NSAIDs. Cardiology referral if not improving.")
    add_dx(doc, e4, "I11.9", "Hypertensive heart disease without heart failure", primary=True)
    prescribe(doc, e4, [
        {"drug_name": "Amlodipine", "dose": "5mg",  "route": "oral",
         "frequency": "OD", "duration_days": 30, "instructions": "Morning dose"},
        {"drug_name": "Aspirin",    "dose": "75mg", "route": "oral",
         "frequency": "OD", "duration_days": 30, "instructions": "With food"},
        {"drug_name": "Ibuprofen",  "dose": "400mg","route": "oral",
         "frequency": "TDS", "duration_days": 7, "instructions": "For musculoskeletal pain"},
    ])
    close_enc(doc, e4)
    print("  → Aspirin + Ibuprofen interaction risk. Pharmacist dispense will query RxNav ACL.")
    issue_only(acc, p4)

    # =================================================================
    # PATIENT 5: Nyasha Chirwa — UTI, dispensed
    # =================================================================
    print("\n[7/8] Patient 5: Nyasha Chirwa — UTI")
    p5 = seed_patient(rec, "Nyasha", "Chirwa", "1995-09-14", "female",
                      "95-852963E-55", "nyasha.chirwa@demo.zw", "+263775678901")
    grant_consent(rec, p5)
    s5, e5_end = _slot(240)
    a5 = book_appointment(rec, p5, DOCTOR_ID, s5, e5_end,
                          "Dysuria and urinary frequency × 2 days")
    check_in(rec, a5)
    e5 = start_encounter(doc, p5, a5, DOCTOR_ID)
    record_vitals(doc, e5, temp=37.8, sbp=110, dbp=70, hr=92, spo2=99.0, wt=58.0, ht=158.0)
    add_soap(doc, e5,
             s="2-day dysuria, frequency and suprapubic discomfort. No haematuria.",
             o="T 37.8°C. Suprapubic tenderness. Dipstick: nitrites++, leucocytes++.",
             a="Uncomplicated lower UTI. Empirical antibiotic initiated.",
             p="Ciprofloxacin 500mg BD × 7 days. Increase fluids. Urine M/C/S sent.")
    add_dx(doc, e5, "N39.0", "Urinary tract infection, site not specified", primary=True)
    prescribe(doc, e5, [
        {"drug_name": "Ciprofloxacin", "dose": "500mg", "route": "oral",
         "frequency": "BD", "duration_days": 7, "instructions": "Complete full course. Empty stomach."},
        {"drug_name": "Ibuprofen",     "dose": "400mg", "route": "oral",
         "frequency": "TDS PRN", "duration_days": 3, "instructions": "For pain. With food."},
    ])
    lab_order(doc, e5, [
        {"test_code": "UMCS", "urgency": "routine", "notes": "Urine M/C/S"},
    ])
    close_enc(doc, e5)
    dispense(pharm, p5)
    issue_and_pay(acc, p5, "15.00", "cash", "REC-NC005")
    print("  → Complete.")

    # =================================================================
    # PATIENT 6: Tatenda Banda — cancelled + rebooked
    # =================================================================
    print("\n[8a/8] Patient 6: Tatenda Banda — cancelled appointment")
    p6 = seed_patient(rec, "Tatenda", "Banda", "2000-12-25", "male",
                      "00-147258F-66", "tatenda.banda@demo.zw", "+263776789012")
    grant_consent(rec, p6)
    s6, e6_end = _slot(300)
    a6 = book_appointment(rec, p6, DOCTOR_ID, s6, e6_end,
                          "Follow-up post-malaria treatment")
    cancel_appointment(rec, a6)
    s6b, e6b_end = _slot(60 * 24 + 30)
    a6b = book_appointment(rec, p6, DOCTOR_ID, s6b, e6b_end,
                           "Follow-up post-malaria treatment (rebooked)")
    print(f"  → Cancelled + rebooked tomorrow ({a6b[:12]}…)")

    # =================================================================
    # PATIENT 7: Simba Ncube — paediatric, full journey
    # =================================================================
    print("\n[8b/8] Patient 7: Simba Ncube — paediatric pneumonia")
    p7 = seed_patient(rec, "Simba", "Ncube", "2018-06-10", "male",
                      "63-9999999P-42", "guardian.ncube@demo.zw", "+263777890123")
    grant_consent(rec, p7)
    s7, e7_end = _slot(330)
    a7 = book_appointment(rec, p7, DOCTOR_ID, s7, e7_end,
                          "Cough, fever and fast breathing × 3 days")
    check_in(rec, a7)
    e7 = start_encounter(doc, p7, a7, DOCTOR_ID)
    record_vitals(doc, e7, temp=38.3, sbp=95, dbp=60, hr=110, rr=24, spo2=97.5, wt=20.0, ht=112.0)
    add_soap(doc, e7,
             s="Mother: 3 days cough, nasal discharge, fever to 38.5°C. Eating less.",
             o="T 38.3 HR 110 RR 24. Nasal flaring. Bilateral basal crackles. No wheeze.",
             a="Community-acquired pneumonia — mild to moderate. No danger signs.",
             p="Amoxicillin oral × 7 days. Paracetamol for fever. Review 48 hrs.")
    add_dx(doc, e7, "J18.9", "Pneumonia, unspecified organism", primary=True)
    add_dx(doc, e7, "J06.9", "Acute upper respiratory infection, unspecified")
    prescribe(doc, e7, [
        {"drug_name": "Amoxicillin",  "dose": "250mg", "route": "oral",
         "frequency": "TDS", "duration_days": 7, "instructions": "Complete full course"},
        {"drug_name": "Paracetamol",  "dose": "240mg", "route": "oral",
         "frequency": "QDS PRN", "duration_days": 5, "instructions": "For fever above 38°C"},
    ])
    lab_order(doc, e7, [
        {"test_code": "FBC", "urgency": "urgent", "notes": "Full blood count — severity"},
        {"test_code": "CXR", "urgency": "urgent", "notes": "Chest X-ray — confirm pneumonia"},
    ])
    close_enc(doc, e7)
    dispense(pharm, p7)
    complete_lab(lab, p7, [
        {"test_code": "FBC", "test_name": "Full Blood Count",
         "value": "Hb 11.8 WBC 18.2 (Neuts 78%) Plt 310", "unit": "mixed",
         "interpretation": "high", "notes": "Neutrophilia — bacterial infection"},
        {"test_code": "CXR", "test_name": "Chest X-Ray",
         "value": "Right lower lobe consolidation. No effusion.",
         "unit": "", "interpretation": "positive",
         "notes": "CAP confirmed — antibiotic appropriate"},
    ])
    issue_and_pay(acc, p7, "22.00", "insurance", "ZESA-2026-0089")
    print("  → Complete.")

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SEED COMPLETE")
    print("=" * 60)
    print(f"""
  P1 Chipo Moyo     enc={e1[:12]}…  (happy path, paid)
  P2 Tendai Dube    enc={e2[:12]}…  (OOS Warfarin — dispense to demo saga)
  P3 Rudo Nhamo     enc={e3[:12]}…  (DM, lab complete, paid)
  P4 Farai Mutasa   enc={e4[:12]}…  (drug interaction — dispense to demo)
  P5 Nyasha Chirwa  enc={e5[:12]}…  (UTI, dispensed, paid)
  P6 Tatenda Banda  (cancelled + rebooked appt)
  P7 Simba Ncube    enc={e7[:12]}…  (paediatric, paid)

  Login → http://localhost:4200
    recep1  / recep1       (receptionist)
    doctor1 / doctor1      (doctor)
    pharm1  / pharm1       (pharmacist)
    lab1    / lab1         (lab technician)
    acct1   / acct1        (accounts)
""")


if __name__ == "__main__":
    main()
