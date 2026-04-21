export type AppointmentStatus =
  | 'booked'
  | 'checked_in'
  | 'cancelled'
  | 'no_show';

export interface Appointment {
  appointment_id: string;
  patient_id: string;
  doctor_id: string;
  start_at: string;
  end_at: string;
  duration_minutes: number;
  status: AppointmentStatus;
  reason?: string;
  booked_by: string;
  booked_at: string;
  version: number;
}

export interface BookAppointmentRequest {
  patient_id: string;
  doctor_id: string;
  start_at: string;
  end_at: string;
  reason?: string;
}

export interface AppointmentListResponse {
  items: Appointment[];
  total: number;
  limit: number;
  offset: number;
}
