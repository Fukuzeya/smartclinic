export type InvoiceStatus = 'draft' | 'issued' | 'partially_paid' | 'paid' | 'void';
export type PaymentMethod = 'cash' | 'ecocash' | 'zipit' | 'insurance' | 'bank_transfer' | 'other';

export interface ChargeLine {
  category: string;
  description: string;
  unit_price: { amount: string; currency: string };
  quantity: number;
  reference_id?: string;
}

export interface PaymentRecord {
  amount: { amount: string; currency: string };
  method: PaymentMethod;
  reference: string;
  recorded_by: string;
}

export interface Invoice {
  invoice_id: string;
  patient_id: string;
  encounter_id: string;
  currency: string;
  status: InvoiceStatus;
  lines: ChargeLine[];
  payments: PaymentRecord[];
  created_at: string;
  issued_at?: string;
  paid_at?: string;
}

export interface InvoiceSummary {
  invoice_id: string;
  patient_id: string;
  encounter_id: string;
  currency: string;
  status: InvoiceStatus;
  total_due: string;
  total_paid: string;
  balance: string;
}

export interface InvoiceListResponse {
  items: Invoice[];
  total: number;
  limit: number;
  offset: number;
}

export interface AddChargeRequest {
  category: string;
  description: string;
  unit_price_amount: string;
  unit_price_currency?: string;
  quantity?: number;
}

export interface RecordPaymentRequest {
  amount: string;
  currency?: string;
  method: PaymentMethod;
  reference: string;
}
