import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import {
  Patient,
  PatientListResponse,
  RegisterPatientRequest,
} from '../models/patient.model';

@Injectable({ providedIn: 'root' })
export class PatientService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.patientIdentity;

  register(req: RegisterPatientRequest): Observable<{ patient_id: string; display_name: string }> {
    return this.http.post<{ patient_id: string; display_name: string }>(
      `${this.base}/patients`,
      req
    );
  }

  get(patientId: string): Observable<Patient> {
    return this.http.get<Patient>(`${this.base}/patients/${patientId}`);
  }

  search(
    nameFragment: string,
    limit = 20,
    offset = 0
  ): Observable<PatientListResponse> {
    const params = new HttpParams()
      .set('name_fragment', nameFragment)
      .set('limit', limit)
      .set('offset', offset);
    return this.http.get<PatientListResponse>(`${this.base}/patients`, {
      params,
    });
  }

  grantConsent(patientId: string, purpose: string): Observable<void> {
    return this.http.post<void>(
      `${this.base}/patients/${patientId}/consents`,
      { purpose }
    );
  }

  revokeConsent(patientId: string, purpose: string): Observable<void> {
    return this.http.delete<void>(
      `${this.base}/patients/${patientId}/consents/${purpose}`
    );
  }
}
