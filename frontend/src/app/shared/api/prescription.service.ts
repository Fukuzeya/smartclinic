import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import { Prescription, PrescriptionListResponse } from '../models/prescription.model';

@Injectable({ providedIn: 'root' })
export class PrescriptionService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.pharmacy;

  list(patientId?: string, status?: string, limit = 20, offset = 0): Observable<PrescriptionListResponse> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (patientId) params = params.set('patient_id', patientId);
    if (status) params = params.set('status_filter', status);
    return this.http.get<PrescriptionListResponse>(`${this.base}/prescriptions`, { params });
  }

  get(prescriptionId: string): Observable<Prescription> {
    return this.http.get<Prescription>(`${this.base}/prescriptions/${prescriptionId}`);
  }

  dispense(prescriptionId: string): Observable<{ outcome: string; reasons: string[]; out_of_stock_drugs: string[]; warnings: string[] }> {
    return this.http.post<{ outcome: string; reasons: string[]; out_of_stock_drugs: string[]; warnings: string[] }>(
      `${this.base}/prescriptions/${prescriptionId}/dispense`, {}
    );
  }

  dispensePartial(prescriptionId: string, drugNames: string[]): Observable<void> {
    return this.http.post<void>(
      `${this.base}/prescriptions/${prescriptionId}/dispense-partial`,
      { drug_names: drugNames }
    );
  }

  reject(prescriptionId: string, reasons: string[]): Observable<void> {
    return this.http.post<void>(`${this.base}/prescriptions/${prescriptionId}/reject`, { reasons });
  }
}
