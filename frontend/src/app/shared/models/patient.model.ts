export interface PatientSummary {
  patient_id: string;
  display_name: string;
  date_of_birth: string;
  sex: 'male' | 'female' | 'unknown';
  has_email: boolean;
  has_phone: boolean;
}

export interface ConsentRecord {
  purpose: string;
  is_active: boolean;
  granted_at: string;
  granted_by: string;
  revoked_at?: string;
  revoked_by?: string;
}

export interface Patient {
  patient_id: string;
  display_name: string;
  given_name: string;
  middle_name?: string;
  family_name: string;
  date_of_birth: string;
  sex: 'male' | 'female' | 'unknown';
  email?: string;
  phone?: string;
  address?: {
    street: string;
    suburb?: string;
    city: string;
    province: string;
    country: string;
  };
  next_of_kin?: {
    display_name: string;
    relationship: string;
    phone: string;
  };
  consents: ConsentRecord[];
  registered_at: string;
  version: number;
}

export interface RegisterPatientRequest {
  given_name: string;
  middle_name?: string;
  family_name: string;
  national_id: string;
  date_of_birth: string;
  sex: 'male' | 'female' | 'unknown';
  email?: string;
  phone?: string;
}

export interface PatientListResponse {
  items: PatientSummary[];
  total: number;
  limit: number;
  offset: number;
}
