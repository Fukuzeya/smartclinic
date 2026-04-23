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
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/vital-signs`, req);
  }

  addDiagnosis(encounterId: string, req: AddDiagnosisRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/diagnoses`, req);
  }

  recordSOAP(encounterId: string, req: RecordSOAPRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/soap-notes`, req);
  }

  close(encounterId: string): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/close`, {});
  }

  verifyChain(encounterId: string): Observable<{ is_valid: boolean; message: string; event_count: number; first_broken_sequence?: number }> {
    return this.http.get<{ is_valid: boolean; message: string; event_count: number; first_broken_sequence?: number }>(
      `${this.base}/encounters/${encounterId}/audit`
    );
  }

  getEventStream(encounterId: string): Observable<EncounterEventStream> {
    return this.http.get<EncounterEventStream>(
      `${this.base}/encounters/${encounterId}/events`
    );
  }

  draftSoapNote(encounterId: string): Observable<AISuggestionResponse> {
    return this.http.post<AISuggestionResponse>(
      `${this.base}/encounters/${encounterId}/ai/soap-draft`, {}
    );
  }

  explainDrugSafety(
    encounterId: string,
    drugNames: string[],
    specFailureReasons: string[],
  ): Observable<AISuggestionResponse> {
    return this.http.post<AISuggestionResponse>(
      `${this.base}/encounters/${encounterId}/ai/drug-safety`,
      { drug_names: drugNames, spec_failure_reasons: specFailureReasons }
    );
  }

  recordAIDecision(suggestionId: string, decision: 'accepted' | 'discarded'): Observable<void> {
    return this.http.post<void>(
      `${this.base}/encounters/ai/suggestions/${suggestionId}/decision`,
      { decision }
    );
  }

  issuePrescription(encounterId: string, body: IssuePrescriptionRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/prescriptions`, body);
  }

  placeLabOrder(encounterId: string, body: PlaceLabOrderRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/encounters/${encounterId}/lab-orders`, body);
  }
}

export interface PrescriptionLine {
  drug_name: string;
  dose: string;
  route: string;
  frequency: string;
  duration_days: number;
  instructions?: string;
}

export interface IssuePrescriptionRequest {
  lines: PrescriptionLine[];
}

export interface LabTestLine {
  test_code: string;
  urgency?: 'routine' | 'urgent' | 'stat';
  notes?: string;
}

export interface PlaceLabOrderRequest {
  tests: LabTestLine[];
}

export interface AISuggestionResponse {
  suggestion_id: string;
  suggestion_text: string;
  model_id: string;
  generated_at: string;
  disclaimer: string;
}

export interface EncounterEventRecord {
  sequence: number;
  event_id: string;
  event_type: string;
  occurred_at: string;
  payload: Record<string, unknown>;
  chain_hash_prefix: string;
}

export interface EncounterEventStream {
  encounter_id: string;
  event_count: number;
  chain_valid: boolean;
  chain_message: string;
  events: EncounterEventRecord[];
}
