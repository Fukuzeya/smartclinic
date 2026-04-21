import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import {
  Appointment,
  AppointmentListResponse,
  BookAppointmentRequest,
} from '../models/appointment.model';

@Injectable({ providedIn: 'root' })
export class AppointmentService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.scheduling;

  book(req: BookAppointmentRequest): Observable<{ appointment_id: string }> {
    return this.http.post<{ appointment_id: string }>(
      `${this.base}/appointments`,
      req
    );
  }

  get(appointmentId: string): Observable<Appointment> {
    return this.http.get<Appointment>(
      `${this.base}/appointments/${appointmentId}`
    );
  }

  listForPatient(
    patientId: string,
    limit = 20,
    offset = 0
  ): Observable<AppointmentListResponse> {
    const params = new HttpParams()
      .set('patient_id', patientId)
      .set('limit', limit)
      .set('offset', offset);
    return this.http.get<AppointmentListResponse>(
      `${this.base}/appointments`,
      { params }
    );
  }

  listForDoctorOnDate(
    doctorId: string,
    date: string
  ): Observable<AppointmentListResponse> {
    const params = new HttpParams()
      .set('doctor_id', doctorId)
      .set('on_date', date);
    return this.http.get<AppointmentListResponse>(
      `${this.base}/appointments`,
      { params }
    );
  }

  checkIn(appointmentId: string): Observable<void> {
    return this.http.post<void>(
      `${this.base}/appointments/${appointmentId}/check-in`,
      {}
    );
  }

  cancel(appointmentId: string, reason: string): Observable<void> {
    return this.http.post<void>(
      `${this.base}/appointments/${appointmentId}/cancel`,
      { reason }
    );
  }

  markNoShow(appointmentId: string): Observable<void> {
    return this.http.post<void>(
      `${this.base}/appointments/${appointmentId}/no-show`,
      {}
    );
  }

  list(
    patientId?: string,
    onDate?: string,
    status?: string,
    limit = 20,
    offset = 0
  ): Observable<AppointmentListResponse> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (patientId) params = params.set('patient_id', patientId);
    if (onDate) params = params.set('on_date', onDate);
    if (status) params = params.set('status', status);
    return this.http.get<AppointmentListResponse>(`${this.base}/appointments`, { params });
  }
}
