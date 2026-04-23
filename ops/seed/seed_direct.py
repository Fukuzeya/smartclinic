#!/usr/bin/env python3
"""SmartClinic — direct-DB seed script (bypasses API + Keycloak authentication).

This script inserts demo data directly into each bounded context's database,
completely bypassing the REST APIs and token-based auth. It is the fallback
when the API-based seeder cannot authenticate (issuer mismatch in prod).

It faithfully reproduces the same 7-patient dataset as the original seed.py,
including clinical event-sourcing with correct chain hashes.

Usage (inside Docker network):
  docker compose ... --profile seed run --rm seeder \
    python /seed/seed_direct.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2

# ── Timestamps ────────────────────────────────────────────────────────────
NOW = datetime.now(timezone.utc)
_BASE = (NOW + timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def _slot(offset_minutes: int, duration_minutes: int = 30):
    start = _BASE + timedelta(minutes=offset_minutes)
    end = start + timedelta(minutes=duration_minutes)
    return start, end


def _uuid():
    return str(uuid.uuid4())


# ── DB connections ────────────────────────────────────────────────────────
DB_HOST = os.getenv("PHARMACY_DB_HOST", os.getenv("DB_HOST", "postgres"))
DB_PORT = int(os.getenv("PHARMACY_DB_PORT", os.getenv("DB_PORT", "5432")))


def _conn(dbname, user=None, password=None):
    user = user or dbname
    password = password or dbname
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=dbname, user=user, password=password)


# ── Chain hash (replicates clinical/infrastructure/event_store.py) ────────
GENESIS_HASH = "0" * 64


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_chain_hash(*, prev_hash: str, event_id: str, event_type: str, payload: dict) -> str:
    data = "|".join([prev_hash, event_id, event_type, canonical_json(payload)])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ── Fake doctor UUID (Keycloak assigns at runtime; we use a stable one) ──
# We query Keycloak's DB directly for the real doctor1 user UUID.
def _get_keycloak_user_id(username: str) -> str:
    """Look up a Keycloak user UUID from the keycloak database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname="keycloak",
            user="keycloak", password="keycloak",
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM user_entity WHERE username = %s AND realm_id = ("
            "  SELECT id FROM realm WHERE name = 'smartclinic'"
            ")",
            (username,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return str(row[0])
    except Exception as exc:
        print(f"  WARN: Could not look up {username} in Keycloak DB: {exc}", file=sys.stderr)
    # Fallback: deterministic UUID
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{username}.smartclinic.local"))


# ── Patient Identity ──────────────────────────────────────────────────────
def seed_patient(conn, given, family, dob, sex, national_id, email, phone, registered_by):
    cur = conn.cursor()
    # Idempotent: check if already exists
    cur.execute("SELECT id FROM patients WHERE national_id = %s", (national_id,))
    row = cur.fetchone()
    if row:
        pid = str(row[0])
        print(f"  [patient]      {given} {family} → {pid[:12]}… (existing)")
        cur.close()
        return pid
    pid = _uuid()
    cur.execute("""
        INSERT INTO patients (id, version, given_name, family_name, national_id,
                              date_of_birth, sex, email, phone, registered_at, registered_by,
                              created_at, updated_at)
        VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (pid, given, family, national_id, dob, sex, email, phone, NOW, registered_by, NOW, NOW))
    cur.close()
    print(f"  [patient]      {given} {family} → {pid[:12]}…")
    return pid


def grant_consent(conn, pid, granted_by):
    cur = conn.cursor()
    for purpose in ("treatment", "billing"):
        cur.execute("""
            INSERT INTO patient_consents (id, patient_id, purpose, granted_at, granted_by)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (patient_id, purpose) DO NOTHING
        """, (_uuid(), pid, purpose, NOW, granted_by))
    cur.close()
    print(f"  [consent]      treatment + billing granted")


# ── Scheduling ────────────────────────────────────────────────────────────
def book_appointment(conn, patient_id, doctor_id, start, end, reason, booked_by):
    aid = _uuid()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO appointments (id, version, patient_id, doctor_id, start_at, end_at,
                                  status, reason, booked_by, booked_at, created_at, updated_at)
        VALUES (%s, 1, %s, %s, %s, %s, 'checked_in', %s, %s, %s, %s, %s)
    """, (aid, patient_id, doctor_id, start, end, reason, booked_by, NOW, NOW, NOW))
    cur.close()
    print(f"  [appointment]  {start.strftime('%H:%M')} → {aid[:12]}…")
    return aid


def book_cancelled_appointment(conn, patient_id, doctor_id, start, end, reason, booked_by):
    aid = _uuid()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO appointments (id, version, patient_id, doctor_id, start_at, end_at,
                                  status, reason, booked_by, booked_at, created_at, updated_at)
        VALUES (%s, 1, %s, %s, %s, %s, 'cancelled', %s, %s, %s, %s, %s)
    """, (aid, patient_id, doctor_id, start, end, reason, booked_by, NOW, NOW, NOW))
    cur.close()
    print(f"  [appointment]  cancelled → {aid[:12]}…")
    return aid


def book_booked_appointment(conn, patient_id, doctor_id, start, end, reason, booked_by):
    aid = _uuid()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO appointments (id, version, patient_id, doctor_id, start_at, end_at,
                                  status, reason, booked_by, booked_at, created_at, updated_at)
        VALUES (%s, 1, %s, %s, %s, %s, 'booked', %s, %s, %s, %s, %s)
    """, (aid, patient_id, doctor_id, start, end, reason, booked_by, NOW, NOW, NOW))
    cur.close()
    print(f"  [appointment]  booked → {aid[:12]}…")
    return aid


# ── Clinical (event-sourced) ──────────────────────────────────────────────
class EncounterBuilder:
    """Builds a chain of clinical events for one encounter."""

    def __init__(self, conn, encounter_id, patient_id, doctor_id, appointment_id):
        self.conn = conn
        self.enc_id = encounter_id
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.appointment_id = appointment_id
        self.prev_hash = GENESIS_HASH
        self.seq = 0
        self.has_rx = False
        self.has_lab = False
        self.primary_icd10 = None
        self.rx_id = None
        self.lab_id = None

    def _append(self, event_type, payload):
        self.seq += 1
        eid = _uuid()
        chain_hash = compute_chain_hash(
            prev_hash=self.prev_hash, event_id=eid,
            event_type=event_type, payload=payload,
        )
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO clinical_events (id, aggregate_id, aggregate_type, event_type,
                                         sequence, occurred_at, payload, metadata, chain_hash)
            VALUES (%s, %s, 'Encounter', %s, %s, %s, %s, %s, %s)
        """, (
            eid, self.enc_id, event_type, self.seq, NOW,
            json.dumps(payload, default=str),
            json.dumps({"aggregate_version": self.seq}),
            chain_hash,
        ))
        cur.close()
        self.prev_hash = chain_hash
        return eid

    def start(self, started_by):
        payload = {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "appointment_id": self.appointment_id,
            "started_by": started_by,
        }
        self._append("clinical.encounter.started.v1", payload)
        print(f"  [encounter]    started → {self.enc_id[:12]}…")

    def vitals(self, **kwargs):
        self._append("clinical.encounter.vital_signs_recorded.v1", kwargs)
        print(f"  [vitals]       T={kwargs.get('temperature_celsius')} BP={kwargs.get('systolic_bp_mmhg')}/{kwargs.get('diastolic_bp_mmhg')}")

    def soap(self, s, o, a, p):
        self._append("clinical.encounter.soap_note_added.v1", {
            "subjective": s, "objective": o, "assessment": a, "plan": p,
        })
        print(f"  [SOAP]         recorded")

    def diagnosis(self, code, desc, primary=False):
        self._append("clinical.encounter.diagnosis_recorded.v1", {
            "icd10_code": code, "description": desc, "is_primary": primary,
        })
        if primary:
            self.primary_icd10 = code
        print(f"  [diagnosis]    {code} {desc}")

    def prescribe(self, lines, issued_by):
        self.rx_id = _uuid()
        self.has_rx = True
        payload = {
            "prescription_id": self.rx_id,
            "patient_id": self.patient_id,
            "encounter_id": self.enc_id,
            "lines": lines,
            "issued_by": issued_by,
        }
        self._append("clinical.encounter.prescription_issued.v1", payload)
        print(f"  [rx]           {', '.join(l['drug_name'] for l in lines)}")

    def lab_order(self, tests, ordered_by):
        self.lab_id = _uuid()
        self.has_lab = True
        payload = {
            "lab_order_id": self.lab_id,
            "patient_id": self.patient_id,
            "encounter_id": self.enc_id,
            "tests": tests,
            "ordered_by": ordered_by,
        }
        self._append("clinical.encounter.lab_order_placed.v1", payload)
        print(f"  [lab]          {', '.join(t['test_code'] for t in tests)}")

    def close(self, closed_by):
        payload = {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "primary_icd10": self.primary_icd10,
            "has_prescription": self.has_rx,
            "has_lab_order": self.has_lab,
            "closed_by": closed_by,
        }
        self._append("clinical.encounter.closed.v1", payload)
        print(f"  [encounter]    closed")


# ── Clinical read model (CQRS projection) ─────────────────────────────────
def upsert_encounter_summary(conn, enc: EncounterBuilder, status="closed"):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO encounter_summaries
            (encounter_id, patient_id, doctor_id, appointment_id, status,
             started_at, closed_at, primary_icd10, has_prescription, has_lab_order,
             vital_signs_count, notes_count, diagnoses_count, last_updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (encounter_id) DO UPDATE SET
            status = EXCLUDED.status,
            closed_at = EXCLUDED.closed_at,
            primary_icd10 = EXCLUDED.primary_icd10,
            has_prescription = EXCLUDED.has_prescription,
            has_lab_order = EXCLUDED.has_lab_order,
            last_updated_at = EXCLUDED.last_updated_at
    """, (
        enc.enc_id, enc.patient_id, enc.doctor_id, enc.appointment_id,
        status, NOW, NOW if status == "closed" else None,
        enc.primary_icd10, enc.has_rx, enc.has_lab,
        1, 1, 1, NOW,
    ))
    cur.close()


# ── Pharmacy ──────────────────────────────────────────────────────────────
def seed_stock(conn):
    cur = conn.cursor()
    drugs = [
        ("Amoxicillin", 200, "tablets"), ("Paracetamol", 500, "tablets"),
        ("Metformin", 300, "tablets"), ("Atorvastatin", 150, "tablets"),
        ("Amlodipine", 150, "tablets"), ("Lisinopril", 150, "tablets"),
        ("Salbutamol Inhaler", 50, "inhalers"), ("Prednisolone", 120, "tablets"),
        ("Cotrimoxazole", 200, "tablets"), ("Ibuprofen", 300, "tablets"),
        ("Omeprazole", 80, "capsules"), ("Aspirin", 80, "tablets"),
        ("Ciprofloxacin", 100, "tablets"), ("Doxycycline", 100, "tablets"),
        ("Ferrous Sulphate", 200, "tablets"),
    ]
    for name, qty, unit in drugs:
        cur.execute("""
            INSERT INTO drug_stock (id, drug_name, quantity_on_hand, unit, reorder_threshold)
            VALUES (gen_random_uuid(), %s, %s, %s, 20)
            ON CONFLICT (drug_name) DO UPDATE SET quantity_on_hand = EXCLUDED.quantity_on_hand
        """, (name, qty, unit))
        print(f"  [stock]        {name} × {qty} {unit}")
    cur.close()


def insert_prescription(conn, rx_id, encounter_id, patient_id, issued_by, lines, status="dispensed"):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO prescriptions (prescription_id, encounter_id, patient_id, issued_by,
                                   lines, status, received_at, dispensed_at, version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
        ON CONFLICT (prescription_id) DO NOTHING
    """, (
        rx_id, encounter_id, patient_id, issued_by,
        json.dumps(lines), status, NOW,
        NOW if status == "dispensed" else None,
    ))
    cur.close()
    print(f"  [pharmacy rx]  {status}")


def insert_consent_projection(conn, patient_id):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO patient_consent_projection (patient_id, has_treatment_consent, last_updated_at)
        VALUES (%s, true, %s)
        ON CONFLICT (patient_id) DO UPDATE SET has_treatment_consent = true
    """, (patient_id, NOW))
    cur.close()


# ── Laboratory ────────────────────────────────────────────────────────────
def insert_lab_order(conn, order_id, encounter_id, patient_id, ordered_by, lines,
                     results=None, status="completed"):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO lab_orders (order_id, patient_id, encounter_id, ordered_by,
                                lines, results, status, sample_type, received_at,
                                completed_at, version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
        ON CONFLICT (order_id) DO NOTHING
    """, (
        order_id, patient_id, encounter_id, ordered_by,
        json.dumps(lines), json.dumps(results or []),
        status, "blood" if results else None, NOW,
        NOW if status == "completed" else None,
    ))
    cur.close()
    print(f"  [lab order]    {status} — {len(lines)} test(s)")


# ── Billing ───────────────────────────────────────────────────────────────
def insert_invoice(conn, encounter_id, patient_id, lines, status="paid",
                   amount="20.00", method="cash", reference="CASH"):
    inv_id = _uuid()
    payments = []
    if status == "paid":
        payments = [{"amount": amount, "currency": "USD", "method": method,
                     "reference": reference, "paid_at": NOW.isoformat()}]
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO invoices (invoice_id, patient_id, encounter_id, currency,
                              status, lines, payments, created_at, issued_at, paid_at, version)
        VALUES (%s, %s, %s, 'USD', %s, %s, %s, %s, %s, %s, 1)
        ON CONFLICT (invoice_id) DO NOTHING
    """, (
        inv_id, patient_id, encounter_id, status,
        json.dumps(lines), json.dumps(payments), NOW,
        NOW if status in ("issued", "paid") else None,
        NOW if status == "paid" else None,
    ))
    cur.close()
    print(f"  [invoice]      {status}" + (f" ${amount} via {method}" if status == "paid" else ""))


# ── Saga ──────────────────────────────────────────────────────────────────
def insert_saga(conn, encounter_id, patient_id, step="completed", status="completed"):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO patient_visit_sagas (saga_id, patient_id, encounter_id,
                                         step, status, context, started_at, completed_at, version)
        VALUES (%s, %s, %s, %s, %s, '{}', %s, %s, 1)
        ON CONFLICT DO NOTHING
    """, (_uuid(), patient_id, encounter_id, step, status, NOW, NOW if status == "completed" else None))
    cur.close()


# ═════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  SmartClinic Direct-DB Seed  —  7 Patients")
    print("=" * 60)

    # ── Resolve Keycloak user IDs ─────────────────────────────
    print("\n[1/8] Resolving Keycloak user IDs…")
    DOCTOR_ID = _get_keycloak_user_id("doctor1")
    RECEP_ID = _get_keycloak_user_id("recep1")
    print(f"  Doctor UUID:       {DOCTOR_ID}")
    print(f"  Receptionist UUID: {RECEP_ID}")

    # ── Open DB connections ───────────────────────────────────
    pi_conn = _conn("patient_identity")
    pi_conn.autocommit = True
    sched_conn = _conn("scheduling")
    sched_conn.autocommit = True
    cw_conn = _conn("clinical_write", "clinical", "clinical")
    cw_conn.autocommit = True
    cr_conn = cw_conn  # read model lives in clinical_write (no separate read DB)
    pharm_conn = _conn("pharmacy")
    pharm_conn.autocommit = True
    lab_conn = _conn("laboratory")
    lab_conn.autocommit = True
    bill_conn = _conn("billing")
    bill_conn.autocommit = True
    saga_conn = _conn("saga")
    saga_conn.autocommit = True

    # ── Seed pharmacy stock ───────────────────────────────────
    print("\n[2/8] Seeding pharmacy stock…")
    seed_stock(pharm_conn)

    # ═════════════════════════════════════════════════════════
    # PATIENT 1: Chipo Moyo — full happy path
    # ═════════════════════════════════════════════════════════
    print("\n[3/8] Patient 1: Chipo Moyo — happy path")
    p1 = seed_patient(pi_conn, "Chipo", "Moyo", "1985-04-12", "female",
                      "63-123456A-75", "chipo.moyo@demo.zw", "+263771234567", RECEP_ID)
    grant_consent(pi_conn, p1, RECEP_ID)
    s1, e1_end = _slot(0)
    a1 = book_appointment(sched_conn, p1, DOCTOR_ID, s1, e1_end,
                          "Chest tightness and cough for 4 days", RECEP_ID)

    enc1 = EncounterBuilder(cw_conn, _uuid(), p1, DOCTOR_ID, a1)
    enc1.start(DOCTOR_ID)
    enc1.vitals(temperature_celsius=37.4, systolic_bp_mmhg=128, diastolic_bp_mmhg=82,
                pulse_bpm=88, respiratory_rate_rpm=16, oxygen_saturation_pct=97.0,
                weight_kg=65.0, height_cm=162.0)
    enc1.soap(
        s="Mild chest tightness, productive cough and low-grade fever × 4 days.",
        o="Mild wheeze bilaterally. No accessory muscle use. SpO2 97%.",
        a="Acute bronchitis with mild bronchospasm. Viral aetiology most likely.",
        p="Bronchodilator inhaler PRN, paracetamol for fever. Review in 5 days.",
    )
    enc1.diagnosis("J20.9", "Acute bronchitis, unspecified", primary=True)
    enc1.diagnosis("J45.20", "Mild intermittent asthma, uncomplicated")
    rx1_lines = [
        {"drug_name": "Salbutamol Inhaler", "dose": "2 puffs", "route": "inhaled",
         "frequency": "QDS PRN", "duration_days": 10, "instructions": "Shake well before use"},
        {"drug_name": "Paracetamol", "dose": "1g", "route": "oral",
         "frequency": "QDS", "duration_days": 5, "instructions": "As needed for fever"},
    ]
    enc1.prescribe(rx1_lines, DOCTOR_ID)
    lab1_tests = [
        {"test_code": "FBC", "urgency": "routine", "notes": "Full blood count"},
        {"test_code": "CRP", "urgency": "routine", "notes": "C-reactive protein"},
    ]
    enc1.lab_order(lab1_tests, DOCTOR_ID)
    enc1.close(DOCTOR_ID)
    upsert_encounter_summary(cr_conn, enc1)
    insert_consent_projection(pharm_conn, p1)
    insert_prescription(pharm_conn, enc1.rx_id, enc1.enc_id, p1, DOCTOR_ID, rx1_lines, "dispensed")
    insert_lab_order(lab_conn, enc1.lab_id, enc1.enc_id, p1, DOCTOR_ID, lab1_tests, results=[
        {"test_code": "FBC", "test_name": "Full Blood Count",
         "value": "Hb 13.2, WBC 8.4, Plt 245", "unit": "mixed",
         "interpretation": "normal", "notes": "No neutrophilia — viral pattern"},
        {"test_code": "CRP", "test_name": "C-Reactive Protein",
         "value": "12", "unit": "mg/L", "reference_range_lower": "0",
         "reference_range_upper": "10", "reference_range_unit": "mg/L",
         "interpretation": "high", "notes": "Mildly elevated"},
    ], status="completed")
    insert_invoice(bill_conn, enc1.enc_id, p1,
                   [{"description": "Consultation + bronchitis treatment", "amount": "18.00"}],
                   status="paid", amount="18.00", method="cash", reference="REC-CH001")
    insert_saga(saga_conn, enc1.enc_id, p1)
    print("  → Complete.")

    # ═════════════════════════════════════════════════════════
    # PATIENT 2: Tendai Dube — OOS saga compensation
    # ═════════════════════════════════════════════════════════
    print("\n[4/8] Patient 2: Tendai Dube — OOS saga compensation")
    p2 = seed_patient(pi_conn, "Tendai", "Dube", "1962-11-30", "male",
                      "48-654321B-32", "tendai.dube@demo.zw", "+263772345678", RECEP_ID)
    grant_consent(pi_conn, p2, RECEP_ID)
    s2, e2_end = _slot(60)
    a2 = book_appointment(sched_conn, p2, DOCTOR_ID, s2, e2_end,
                          "AF anticoagulation clinic review", RECEP_ID)

    enc2 = EncounterBuilder(cw_conn, _uuid(), p2, DOCTOR_ID, a2)
    enc2.start(DOCTOR_ID)
    enc2.vitals(temperature_celsius=36.8, systolic_bp_mmhg=138, diastolic_bp_mmhg=88,
                pulse_bpm=92, respiratory_rate_rpm=16, oxygen_saturation_pct=96.5,
                weight_kg=82.0, height_cm=175.0)
    enc2.soap(
        s="Known AF on anticoagulation. Routine INR review. No bleeding.",
        o="Irregularly irregular pulse 92bpm. BP 138/88. Chest clear.",
        a="Persistent AF — INR subtherapeutic. Anticoagulation adjustment required.",
        p="Continue Warfarin at adjusted dose. Recheck INR in 1 week.",
    )
    enc2.diagnosis("I48.11", "Longstanding persistent atrial fibrillation", primary=True)
    rx2_lines = [
        {"drug_name": "Warfarin", "dose": "5mg", "route": "oral",
         "frequency": "OD", "duration_days": 30,
         "instructions": "Take at same time daily. Avoid NSAIDs."},
    ]
    enc2.prescribe(rx2_lines, DOCTOR_ID)
    enc2.close(DOCTOR_ID)
    upsert_encounter_summary(cr_conn, enc2)
    insert_consent_projection(pharm_conn, p2)
    insert_prescription(pharm_conn, enc2.rx_id, enc2.enc_id, p2, DOCTOR_ID, rx2_lines, "pending")
    insert_invoice(bill_conn, enc2.enc_id, p2,
                   [{"description": "AF review consultation", "amount": "20.00"}],
                   status="draft")
    insert_saga(saga_conn, enc2.enc_id, p2, step="pharmacy_pending", status="in_progress")
    print("  → Warfarin NOT in stock — pending dispensing (OOS demo).")

    # ═════════════════════════════════════════════════════════
    # PATIENT 3: Rudo Nhamo — DM review, lab complete
    # ═════════════════════════════════════════════════════════
    print("\n[5/8] Patient 3: Rudo Nhamo — DM review, lab complete")
    p3 = seed_patient(pi_conn, "Rudo", "Nhamo", "1990-07-20", "female",
                      "90-789012C-50", "rudo.nhamo@demo.zw", "+263773456789", RECEP_ID)
    grant_consent(pi_conn, p3, RECEP_ID)
    s3, e3_end = _slot(120)
    a3 = book_appointment(sched_conn, p3, DOCTOR_ID, s3, e3_end,
                          "Annual diabetic review — HbA1c monitoring", RECEP_ID)

    enc3 = EncounterBuilder(cw_conn, _uuid(), p3, DOCTOR_ID, a3)
    enc3.start(DOCTOR_ID)
    enc3.vitals(temperature_celsius=36.9, systolic_bp_mmhg=132, diastolic_bp_mmhg=84,
                pulse_bpm=78, respiratory_rate_rpm=16, oxygen_saturation_pct=99.0,
                weight_kg=72.0, height_cm=168.0)
    enc3.soap(
        s="Known T2DM × 6 years. On Metformin. Occasional polyuria. No hypos.",
        o="BMI 25.5. BP 132/84. No neuropathy. Pedal pulses intact.",
        a="T2DM — glycaemic control suboptimal. Annual review.",
        p="Continue Metformin 500mg BD. Dietary counselling. Review HbA1c.",
    )
    enc3.diagnosis("E11.9", "Type 2 diabetes mellitus without complications", primary=True)
    enc3.diagnosis("I10", "Essential (primary) hypertension")
    rx3_lines = [
        {"drug_name": "Metformin", "dose": "500mg", "route": "oral",
         "frequency": "BD", "duration_days": 90, "instructions": "Take with meals"},
        {"drug_name": "Lisinopril", "dose": "10mg", "route": "oral",
         "frequency": "OD", "duration_days": 90, "instructions": "Monitor BP and renal function"},
    ]
    enc3.prescribe(rx3_lines, DOCTOR_ID)
    lab3_tests = [
        {"test_code": "HBA1C", "urgency": "routine", "notes": "Glycated haemoglobin"},
        {"test_code": "U&E", "urgency": "routine", "notes": "Urea & electrolytes"},
        {"test_code": "LFT", "urgency": "routine", "notes": "Liver function"},
        {"test_code": "LIPIDS", "urgency": "routine", "notes": "Fasting lipid profile"},
    ]
    enc3.lab_order(lab3_tests, DOCTOR_ID)
    enc3.close(DOCTOR_ID)
    upsert_encounter_summary(cr_conn, enc3)
    insert_consent_projection(pharm_conn, p3)
    insert_prescription(pharm_conn, enc3.rx_id, enc3.enc_id, p3, DOCTOR_ID, rx3_lines, "dispensed")
    insert_lab_order(lab_conn, enc3.lab_id, enc3.enc_id, p3, DOCTOR_ID, lab3_tests, results=[
        {"test_code": "HBA1C", "test_name": "HbA1c", "value": "8.4", "unit": "%",
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
    ], status="completed")
    insert_invoice(bill_conn, enc3.enc_id, p3,
                   [{"description": "DM annual review + lab", "amount": "32.00"}],
                   status="paid", amount="32.00", method="insurance", reference="PSMAS-2026-0441")
    insert_saga(saga_conn, enc3.enc_id, p3)
    print("  → Complete.")

    # ═════════════════════════════════════════════════════════
    # PATIENT 4: Farai Mutasa — drug interaction demo
    # ═════════════════════════════════════════════════════════
    print("\n[6/8] Patient 4: Farai Mutasa — drug interaction demo")
    p4 = seed_patient(pi_conn, "Farai", "Mutasa", "1978-03-05", "male",
                      "78-321654D-44", "farai.mutasa@demo.zw", "+263774567890", RECEP_ID)
    grant_consent(pi_conn, p4, RECEP_ID)
    s4, e4_end = _slot(150)
    a4 = book_appointment(sched_conn, p4, DOCTOR_ID, s4, e4_end,
                          "Chest pain and hypertension evaluation", RECEP_ID)

    enc4 = EncounterBuilder(cw_conn, _uuid(), p4, DOCTOR_ID, a4)
    enc4.start(DOCTOR_ID)
    enc4.vitals(temperature_celsius=36.7, systolic_bp_mmhg=145, diastolic_bp_mmhg=92,
                pulse_bpm=84, respiratory_rate_rpm=16, oxygen_saturation_pct=98.0,
                weight_kg=90.0, height_cm=180.0)
    enc4.soap(
        s="Exertional chest tightness and palpitations. Already on Aspirin.",
        o="BP 145/92. Mild tachycardia. No S3/S4. ECG: sinus rhythm.",
        a="Hypertensive heart disease. Chest pain likely musculoskeletal.",
        p="Add Amlodipine for BP. Continue Aspirin. Avoid NSAIDs. Cardiology referral if not improving.",
    )
    enc4.diagnosis("I11.9", "Hypertensive heart disease without heart failure", primary=True)
    rx4_lines = [
        {"drug_name": "Amlodipine", "dose": "5mg", "route": "oral",
         "frequency": "OD", "duration_days": 30, "instructions": "Morning dose"},
        {"drug_name": "Aspirin", "dose": "75mg", "route": "oral",
         "frequency": "OD", "duration_days": 30, "instructions": "With food"},
        {"drug_name": "Ibuprofen", "dose": "400mg", "route": "oral",
         "frequency": "TDS", "duration_days": 7, "instructions": "For musculoskeletal pain"},
    ]
    enc4.prescribe(rx4_lines, DOCTOR_ID)
    enc4.close(DOCTOR_ID)
    upsert_encounter_summary(cr_conn, enc4)
    insert_consent_projection(pharm_conn, p4)
    insert_prescription(pharm_conn, enc4.rx_id, enc4.enc_id, p4, DOCTOR_ID, rx4_lines, "pending")
    insert_invoice(bill_conn, enc4.enc_id, p4,
                   [{"description": "Hypertension evaluation", "amount": "25.00"}],
                   status="issued", amount="25.00")
    insert_saga(saga_conn, enc4.enc_id, p4, step="pharmacy_pending", status="in_progress")
    print("  → Aspirin + Ibuprofen interaction — pending dispense demo.")

    # ═════════════════════════════════════════════════════════
    # PATIENT 5: Nyasha Chirwa — UTI, dispensed
    # ═════════════════════════════════════════════════════════
    print("\n[7/8] Patient 5: Nyasha Chirwa — UTI")
    p5 = seed_patient(pi_conn, "Nyasha", "Chirwa", "1995-09-14", "female",
                      "95-852963E-55", "nyasha.chirwa@demo.zw", "+263775678901", RECEP_ID)
    grant_consent(pi_conn, p5, RECEP_ID)
    s5, e5_end = _slot(240)
    a5 = book_appointment(sched_conn, p5, DOCTOR_ID, s5, e5_end,
                          "Dysuria and urinary frequency × 2 days", RECEP_ID)

    enc5 = EncounterBuilder(cw_conn, _uuid(), p5, DOCTOR_ID, a5)
    enc5.start(DOCTOR_ID)
    enc5.vitals(temperature_celsius=37.8, systolic_bp_mmhg=110, diastolic_bp_mmhg=70,
                pulse_bpm=92, respiratory_rate_rpm=16, oxygen_saturation_pct=99.0,
                weight_kg=58.0, height_cm=158.0)
    enc5.soap(
        s="2-day dysuria, frequency and suprapubic discomfort. No haematuria.",
        o="T 37.8°C. Suprapubic tenderness. Dipstick: nitrites++, leucocytes++.",
        a="Uncomplicated lower UTI. Empirical antibiotic initiated.",
        p="Ciprofloxacin 500mg BD × 7 days. Increase fluids. Urine M/C/S sent.",
    )
    enc5.diagnosis("N39.0", "Urinary tract infection, site not specified", primary=True)
    rx5_lines = [
        {"drug_name": "Ciprofloxacin", "dose": "500mg", "route": "oral",
         "frequency": "BD", "duration_days": 7, "instructions": "Complete full course. Empty stomach."},
        {"drug_name": "Ibuprofen", "dose": "400mg", "route": "oral",
         "frequency": "TDS PRN", "duration_days": 3, "instructions": "For pain. With food."},
    ]
    enc5.prescribe(rx5_lines, DOCTOR_ID)
    lab5_tests = [{"test_code": "UMCS", "urgency": "routine", "notes": "Urine M/C/S"}]
    enc5.lab_order(lab5_tests, DOCTOR_ID)
    enc5.close(DOCTOR_ID)
    upsert_encounter_summary(cr_conn, enc5)
    insert_consent_projection(pharm_conn, p5)
    insert_prescription(pharm_conn, enc5.rx_id, enc5.enc_id, p5, DOCTOR_ID, rx5_lines, "dispensed")
    insert_lab_order(lab_conn, enc5.lab_id, enc5.enc_id, p5, DOCTOR_ID, lab5_tests, results=[
        {"test_code": "UMCS", "test_name": "Urine M/C/S",
         "value": "E. coli >10^5 CFU/mL, sensitive to Ciprofloxacin",
         "unit": "", "interpretation": "positive",
         "notes": "Confirms UTI — antibiotic appropriate"},
    ], status="completed")
    insert_invoice(bill_conn, enc5.enc_id, p5,
                   [{"description": "UTI consultation + treatment", "amount": "15.00"}],
                   status="paid", amount="15.00", method="cash", reference="REC-NC005")
    insert_saga(saga_conn, enc5.enc_id, p5)
    print("  → Complete.")

    # ═════════════════════════════════════════════════════════
    # PATIENT 6: Tatenda Banda — cancelled + rebooked
    # ═════════════════════════════════════════════════════════
    print("\n[8a/8] Patient 6: Tatenda Banda — cancelled appointment")
    p6 = seed_patient(pi_conn, "Tatenda", "Banda", "2000-12-25", "male",
                      "00-147258F-66", "tatenda.banda@demo.zw", "+263776789012", RECEP_ID)
    grant_consent(pi_conn, p6, RECEP_ID)
    s6, e6_end = _slot(300)
    book_cancelled_appointment(sched_conn, p6, DOCTOR_ID, s6, e6_end,
                               "Follow-up post-malaria treatment", RECEP_ID)
    s6b, e6b_end = _slot(60 * 24 + 30)
    a6b = book_booked_appointment(sched_conn, p6, DOCTOR_ID, s6b, e6b_end,
                                  "Follow-up post-malaria treatment (rebooked)", RECEP_ID)
    print(f"  → Cancelled + rebooked tomorrow ({a6b[:12]}…)")

    # ═════════════════════════════════════════════════════════
    # PATIENT 7: Simba Ncube — paediatric pneumonia
    # ═════════════════════════════════════════════════════════
    print("\n[8b/8] Patient 7: Simba Ncube — paediatric pneumonia")
    p7 = seed_patient(pi_conn, "Simba", "Ncube", "2018-06-10", "male",
                      "63-9999999P-42", "guardian.ncube@demo.zw", "+263777890123", RECEP_ID)
    grant_consent(pi_conn, p7, RECEP_ID)
    s7, e7_end = _slot(330)
    a7 = book_appointment(sched_conn, p7, DOCTOR_ID, s7, e7_end,
                          "Cough, fever and fast breathing × 3 days", RECEP_ID)

    enc7 = EncounterBuilder(cw_conn, _uuid(), p7, DOCTOR_ID, a7)
    enc7.start(DOCTOR_ID)
    enc7.vitals(temperature_celsius=38.3, systolic_bp_mmhg=95, diastolic_bp_mmhg=60,
                pulse_bpm=110, respiratory_rate_rpm=24, oxygen_saturation_pct=97.5,
                weight_kg=20.0, height_cm=112.0)
    enc7.soap(
        s="Mother: 3 days cough, nasal discharge, fever to 38.5°C. Eating less.",
        o="T 38.3 HR 110 RR 24. Nasal flaring. Bilateral basal crackles. No wheeze.",
        a="Community-acquired pneumonia — mild to moderate. No danger signs.",
        p="Amoxicillin oral × 7 days. Paracetamol for fever. Review 48 hrs.",
    )
    enc7.diagnosis("J18.9", "Pneumonia, unspecified organism", primary=True)
    enc7.diagnosis("J06.9", "Acute upper respiratory infection, unspecified")
    rx7_lines = [
        {"drug_name": "Amoxicillin", "dose": "250mg", "route": "oral",
         "frequency": "TDS", "duration_days": 7, "instructions": "Complete full course"},
        {"drug_name": "Paracetamol", "dose": "240mg", "route": "oral",
         "frequency": "QDS PRN", "duration_days": 5, "instructions": "For fever above 38°C"},
    ]
    enc7.prescribe(rx7_lines, DOCTOR_ID)
    lab7_tests = [
        {"test_code": "FBC", "urgency": "urgent", "notes": "Full blood count — severity"},
        {"test_code": "CXR", "urgency": "urgent", "notes": "Chest X-ray — confirm pneumonia"},
    ]
    enc7.lab_order(lab7_tests, DOCTOR_ID)
    enc7.close(DOCTOR_ID)
    upsert_encounter_summary(cr_conn, enc7)
    insert_consent_projection(pharm_conn, p7)
    insert_prescription(pharm_conn, enc7.rx_id, enc7.enc_id, p7, DOCTOR_ID, rx7_lines, "dispensed")
    insert_lab_order(lab_conn, enc7.lab_id, enc7.enc_id, p7, DOCTOR_ID, lab7_tests, results=[
        {"test_code": "FBC", "test_name": "Full Blood Count",
         "value": "Hb 11.8 WBC 18.2 (Neuts 78%) Plt 310", "unit": "mixed",
         "interpretation": "high", "notes": "Neutrophilia — bacterial infection"},
        {"test_code": "CXR", "test_name": "Chest X-Ray",
         "value": "Right lower lobe consolidation. No effusion.",
         "unit": "", "interpretation": "positive",
         "notes": "CAP confirmed — antibiotic appropriate"},
    ], status="completed")
    insert_invoice(bill_conn, enc7.enc_id, p7,
                   [{"description": "Paediatric pneumonia consultation", "amount": "22.00"}],
                   status="paid", amount="22.00", method="insurance", reference="ZESA-2026-0089")
    insert_saga(saga_conn, enc7.enc_id, p7)
    print("  → Complete.")

    # ── Cleanup ───────────────────────────────────────────────
    for c in (pi_conn, sched_conn, cw_conn, pharm_conn, lab_conn, bill_conn, saga_conn):
        c.close()

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SEED COMPLETE")
    print("=" * 60)
    print(f"""
  P1 Chipo Moyo     enc={enc1.enc_id[:12]}…  (happy path, paid)
  P2 Tendai Dube    enc={enc2.enc_id[:12]}…  (OOS Warfarin — dispense to demo saga)
  P3 Rudo Nhamo     enc={enc3.enc_id[:12]}…  (DM, lab complete, paid)
  P4 Farai Mutasa   enc={enc4.enc_id[:12]}…  (drug interaction — dispense to demo)
  P5 Nyasha Chirwa  enc={enc5.enc_id[:12]}…  (UTI, dispensed, paid)
  P6 Tatenda Banda  (cancelled + rebooked appt)
  P7 Simba Ncube    enc={enc7.enc_id[:12]}…  (paediatric, paid)

  Login → http://172.236.3.27
    recep1  / recep1       (receptionist)
    doctor1 / doctor1      (doctor)
    pharm1  / pharm1       (pharmacist)
    lab1    / lab1         (lab technician)
    acct1   / acct1        (accounts)
""")


if __name__ == "__main__":
    main()
