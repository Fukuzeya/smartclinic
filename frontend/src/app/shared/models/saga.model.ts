export type SagaStep =
  | 'awaiting_encounter'
  | 'encounter_open'
  | 'awaiting_lab'
  | 'substitution_required'
  | 'awaiting_payment'
  | 'completed'
  | 'cancelled';

export type SagaStatus = 'active' | 'completed' | 'cancelled';

export interface SagaContext {
  appointment_id?: string;
  encounter_id?: string;
  invoice_id?: string;
  lab_order_ids: string[];
  lab_orders_completed: string[];
  encounter_closed: boolean;
  blocked_prescription_id?: string;
  out_of_stock_drugs: string[];
}

export interface PatientVisitSaga {
  saga_id: string;
  patient_id: string;
  encounter_id: string;
  step: SagaStep;
  status: SagaStatus;
  context: SagaContext;
  started_at: string;
  completed_at?: string;
}

export interface SagaListResponse {
  items: PatientVisitSaga[];
  total: number;
  limit: number;
  offset: number;
}
