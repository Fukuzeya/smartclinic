import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import {
  Encounter, EncounterSummary,
  StartEncounterRequest, RecordVitalsRequest,
  AddDiagnosisRequest, RecordSOAPRequest,
} from '../models/encounter.model';

@Injectable({ providedIn: 'root' })
export class EncounterService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.clinical;

  start(req: StartEncounterRequest): Observable<{ encounter_id: string }> {
    return this.http.post<{ encounter_id: string }>(`${this.base}/encounters`, req);
  }

  get(encounterId: string): Observable<Encounter> {
    return this.http.get<Encounter>(`${this.base}/encounters/${encounterId}`);
  }

  list(patientId?: string, status?: string, limit = 20, offset = 0): Observable<{ items: EncounterSummary[]; total: number }> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (patientId) params = params.set('patient_id', patientId);
    if (status) params = params.set('status', status);
    return this.http.get<{ items: EncounterSummary[]; total: number }>(`${this.base}/encounters`, { params });
  }

  recordVitals(encounterId: string, req: RecordVitalsRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/vitals`, req);
  }

  addDiagnosis(encounterId: string, req: AddDiagnosisRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/diagnoses`, req);
  }

  recordSOAP(encounterId: string, req: RecordSOAPRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/soap`, req);
  }

  close(encounterId: string): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/close`, {});
  }

  verifyChain(encounterId: string): Observable<{ valid: boolean; tampered_at?: number }> {
    return this.http.get<{ valid: boolean; tampered_at?: number }>(
      `${this.base}/encounters/${encounterId}/audit/chain`
    );
  }
}
