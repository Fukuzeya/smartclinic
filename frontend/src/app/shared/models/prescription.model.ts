export type PrescriptionStatus = 'pending' | 'dispensed' | 'partially_dispensed' | 'rejected' | 'cancelled';

export interface PrescriptionLine {
  drug_name: string;
  dose: string;
  frequency: string;
  duration_days: number;
  route: string;
  notes?: string;
}

export interface Prescription {
  prescription_id: string;
  encounter_id: string;
  patient_id: string;
  issued_by: string;
  status: PrescriptionStatus;
  lines: PrescriptionLine[];
  received_at: string;
  dispensed_at?: string;
  rejection_reasons?: string[];
}

export interface PrescriptionListResponse {
  items: Prescription[];
  total: number;
  limit: number;
  offset: number;
}
