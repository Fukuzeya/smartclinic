import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import { PatientVisitSaga, SagaListResponse } from '../models/saga.model';

@Injectable({ providedIn: 'root' })
export class SagaService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.saga;

  list(patientId?: string, status?: string, limit = 20, offset = 0): Observable<SagaListResponse> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (patientId) params = params.set('patient_id', patientId);
    if (status) params = params.set('status_filter', status);
    return this.http.get<SagaListResponse>(`${this.base}/sagas`, { params });
  }

  get(sagaId: string): Observable<PatientVisitSaga> {
    return this.http.get<PatientVisitSaga>(`${this.base}/sagas/${sagaId}`);
  }

  getByEncounter(encounterId: string): Observable<PatientVisitSaga> {
    return this.http.get<PatientVisitSaga>(`${this.base}/sagas/by-encounter/${encounterId}`);
  }
}
