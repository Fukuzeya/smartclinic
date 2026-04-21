import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import {
  Invoice, InvoiceListResponse, InvoiceSummary,
  AddChargeRequest, RecordPaymentRequest,
} from '../models/invoice.model';

@Injectable({ providedIn: 'root' })
export class InvoiceService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.billing;

  list(patientId?: string, encounterId?: string, status?: string, limit = 20, offset = 0): Observable<InvoiceListResponse> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (patientId) params = params.set('patient_id', patientId);
    if (encounterId) params = params.set('encounter_id', encounterId);
    if (status) params = params.set('status_filter', status);
    return this.http.get<InvoiceListResponse>(`${this.base}/invoices`, { params });
  }

  get(invoiceId: string): Observable<Invoice> {
    return this.http.get<Invoice>(`${this.base}/invoices/${invoiceId}`);
  }

  getSummary(invoiceId: string): Observable<InvoiceSummary> {
    return this.http.get<InvoiceSummary>(`${this.base}/invoices/${invoiceId}/summary`);
  }

  addCharge(invoiceId: string, req: AddChargeRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/invoices/${invoiceId}/add-charge`, req);
  }

  issue(invoiceId: string): Observable<void> {
    return this.http.post<void>(`${this.base}/invoices/${invoiceId}/issue`, {});
  }

  recordPayment(invoiceId: string, req: RecordPaymentRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/invoices/${invoiceId}/record-payment`, req);
  }

  void(invoiceId: string, reason: string): Observable<void> {
    return this.http.post<void>(`${this.base}/invoices/${invoiceId}/void`, { reason });
  }
}
