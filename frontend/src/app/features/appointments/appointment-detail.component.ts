import {
  Component, inject, signal, OnInit, input
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { AppointmentService } from '../../shared/api/appointment.service';
import { Appointment } from '../../shared/models/appointment.model';
import { AuthService } from '../../core/auth/auth.service';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';
import { DoctorNameCache } from '../../shared/services/doctor-name-cache.service';

@Component({
  selector: 'app-appointment-detail',
  standalone: true,
  imports: [RouterLink, DatePipe],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Appointment</h1>
        <p class="page-subtitle">Appointment details and actions</p>
      </div>
      <a routerLink="/appointments" class="btn-secondary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        Appointments
      </a>
    </div>

    @if (loading()) {
      <div class="loading">Loading…</div>
    } @else if (error()) {
      <div class="alert-error">{{ error() }}</div>
    } @else if (appt()) {
      @if (actionError()) {
        <div class="alert-error" style="margin-bottom:12px">{{ actionError() }}</div>
      }
      @if (actionSuccess()) {
        <div class="alert-success" style="margin-bottom:12px">{{ actionSuccess() }}</div>
      }

      <div class="card">
        <div class="appt-header">
          <div>
            <span [class]="'badge badge-' + appt()!.status">{{ appt()!.status }}</span>
            <h2 class="appt-time">{{ appt()!.start_at | date:'dd MMM yyyy HH:mm' }}</h2>
            <p class="appt-meta">
              Duration: {{ appt()!.duration_minutes }} min ·
              Doctor: {{ doctorName() || appt()!.doctor_id }}
            </p>
          </div>
          <div class="appt-actions">
            @if (appt()!.status === 'booked') {
              @if (auth.isReceptionist()) {
                <button class="btn-primary" [disabled]="acting()" (click)="checkIn()">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  Check In
                </button>
                <button class="btn-danger" [disabled]="acting()" (click)="cancel()">
                  Cancel
                </button>
              }
              @if (auth.isDoctor()) {
                <button class="btn-secondary" [disabled]="acting()" (click)="noShow()">
                  No Show
                </button>
              }
            }
            @if (appt()!.status === 'checked_in' && auth.isDoctor()) {
              <a class="btn-primary"
                 [routerLink]="['/encounters/new']"
                 [queryParams]="{ patient_id: appt()!.patient_id, appointment_id: appt()!.appointment_id }">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Start Encounter
              </a>
            }
          </div>
        </div>

        <dl class="detail-dl">
          <dt>Patient</dt><dd>{{ patientName() || appt()!.patient_id }}</dd>
          <dt>Reason</dt><dd>{{ appt()!.reason ?? '—' }}</dd>
          <dt>Booked by</dt><dd>{{ appt()!.booked_by }}</dd>
          <dt>Booked at</dt><dd>{{ appt()!.booked_at | date:'dd MMM yyyy HH:mm' }}</dd>
        </dl>
      </div>
    }
  `,
  styles: [`
    .appt-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
    .appt-time { margin: 8px 0 4px; font-size: 1.25rem; font-weight: 700; color: var(--clr-gray-800); }
    .appt-meta { color: var(--clr-gray-500); font-size: 0.875rem; margin: 0; }
    .appt-actions { display: flex; gap: 8px; flex-shrink: 0; }
    .detail-dl {
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: 8px 16px;
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid var(--clr-gray-100);
      font-size: 0.875rem;
    }
    dt { color: var(--clr-gray-500); font-weight: 500; }
    dd { margin: 0; color: var(--clr-gray-800); }
  `],
})
export class AppointmentDetailComponent implements OnInit {
  readonly id = input.required<string>();

  private readonly svc = inject(AppointmentService);
  readonly auth = inject(AuthService);
  private readonly nameCache = inject(PatientNameCache);
  private readonly doctorCache = inject(DoctorNameCache);

  readonly appt = signal<Appointment | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly acting = signal(false);
  readonly actionError = signal<string | null>(null);
  readonly actionSuccess = signal<string | null>(null);
  readonly patientName = signal('');
  readonly doctorName = signal('');

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.svc.get(this.id()).subscribe({
      next: a => {
        this.appt.set(a);
        this.loading.set(false);
        this.nameCache.resolve(a.patient_id).subscribe(n => this.patientName.set(n));
        this.doctorCache.resolve(a.doctor_id).subscribe(n => this.doctorName.set(n));
      },
      error: () => { this.error.set('Appointment not found.'); this.loading.set(false); },
    });
  }

  checkIn(): void {
    this.acting.set(true);
    this.actionError.set(null);
    this.svc.checkIn(this.id()).subscribe({
      next: () => { this.actionSuccess.set('Patient checked in.'); this.acting.set(false); this.reload(); },
      error: err => { this.actionError.set(err?.error?.detail ?? 'Check-in failed.'); this.acting.set(false); },
    });
  }

  cancel(): void {
    const reason = prompt('Cancellation reason (required):');
    if (!reason) return;
    this.acting.set(true);
    this.actionError.set(null);
    this.svc.cancel(this.id(), reason).subscribe({
      next: () => { this.actionSuccess.set('Appointment cancelled.'); this.acting.set(false); this.reload(); },
      error: err => { this.actionError.set(err?.error?.detail ?? 'Cancel failed.'); this.acting.set(false); },
    });
  }

  noShow(): void {
    this.acting.set(true);
    this.actionError.set(null);
    this.svc.markNoShow(this.id()).subscribe({
      next: () => { this.actionSuccess.set('Marked as no-show.'); this.acting.set(false); this.reload(); },
      error: err => { this.actionError.set(err?.error?.detail ?? 'Failed.'); this.acting.set(false); },
    });
  }
}
