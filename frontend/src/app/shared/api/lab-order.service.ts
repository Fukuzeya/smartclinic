import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import { LabOrder, LabOrderListResponse, RecordResultRequest } from '../models/lab-order.model';

@Injectable({ providedIn: 'root' })
export class LabOrderService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.laboratory;

  list(patientId?: string, status?: string, encounterId?: string, limit = 20, offset = 0): Observable<LabOrderListResponse> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (patientId) params = params.set('patient_id', patientId);
    if (status) params = params.set('status_filter', status);
    if (encounterId) params = params.set('encounter_id', encounterId);
    return this.http.get<LabOrderListResponse>(`${this.base}/lab-orders`, { params });
  }

  get(orderId: string): Observable<LabOrder> {
    return this.http.get<LabOrder>(`${this.base}/lab-orders/${orderId}`);
  }

  collectSample(orderId: string, sampleType: string): Observable<void> {
    return this.http.post<void>(`${this.base}/lab-orders/${orderId}/collect-sample`, { sample_type: sampleType });
  }

  recordResult(orderId: string, req: RecordResultRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/lab-orders/${orderId}/record-result`, req);
  }

  complete(orderId: string): Observable<void> {
    return this.http.post<void>(`${this.base}/lab-orders/${orderId}/complete`, {});
  }

  cancel(orderId: string, reason: string): Observable<void> {
    return this.http.post<void>(`${this.base}/lab-orders/${orderId}/cancel`, { reason });
  }
}
