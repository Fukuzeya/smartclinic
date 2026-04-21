export type OrderStatus = 'pending' | 'sample_collected' | 'in_progress' | 'completed' | 'cancelled';
export type SampleType = 'blood' | 'urine' | 'stool' | 'sputum' | 'swab' | 'tissue' | 'csf' | 'other';
export type Interpretation = 'normal' | 'low' | 'high' | 'critical_low' | 'critical_high' | 'positive' | 'negative' | 'indeterminate';

export interface LabOrderLine {
  test_code: string;
  urgency: 'routine' | 'urgent' | 'stat';
  notes?: string;
}

export interface LabResult {
  test_code: string;
  test_name: string;
  value: string;
  unit?: string;
  interpretation: Interpretation;
  notes?: string;
  performed_by: string;
}

export interface LabOrder {
  order_id: string;
  patient_id: string;
  encounter_id: string;
  ordered_by: string;
  status: OrderStatus;
  sample_type?: SampleType;
  lines: LabOrderLine[];
  results: LabResult[];
  received_at: string;
  completed_at?: string;
}

export interface RecordResultRequest {
  test_code: string;
  test_name: string;
  value: string;
  unit?: string;
  interpretation: Interpretation;
  notes?: string;
}

export interface LabOrderListResponse {
  items: LabOrder[];
  total: number;
  limit: number;
  offset: number;
}
