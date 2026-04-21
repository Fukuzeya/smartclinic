export type ClinicalStatus = 'open' | 'closed' | 'cancelled';

export interface VitalSigns {
  temperature_c?: number;
  pulse_bpm?: number;
  respiratory_rate?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  oxygen_saturation?: number;
  weight_kg?: number;
  height_cm?: number;
}

export interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface Diagnosis {
  icd10_code: string;
  description: string;
  is_primary: boolean;
}

export interface EncounterSummary {
  encounter_id: string;
  patient_id: string;
  appointment_id?: string;
  doctor_id: string;
  status: ClinicalStatus;
  started_at: string;
  closed_at?: string;
}

export interface Encounter {
  encounter_id: string;
  patient_id: string;
  appointment_id?: string;
  doctor_id: string;
  status: ClinicalStatus;
  vitals?: VitalSigns;
  soap?: SOAPNote;
  diagnoses: Diagnosis[];
  started_at: string;
  closed_at?: string;
}

export interface StartEncounterRequest {
  patient_id: string;
  appointment_id?: string;
}

export interface RecordVitalsRequest {
  temperature_c?: number;
  pulse_bpm?: number;
  respiratory_rate?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  oxygen_saturation?: number;
  weight_kg?: number;
  height_cm?: number;
}

export interface AddDiagnosisRequest {
  icd10_code: string;
  description: string;
  is_primary?: boolean;
}

export interface RecordSOAPRequest {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}
