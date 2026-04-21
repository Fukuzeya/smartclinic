import {
  Component, inject, signal, OnInit, input
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { AppointmentService } from '../../shared/api/appointment.service';
import { Appointment } from '../../shared/models/appointment.model';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-appointment-detail',
  standalone: true,
  imports: [RouterLink, DatePipe],
  template: `
    <div class="page-header">
      <h1>Appointment detail</h1>
      <a routerLink="/appointments" class="btn btn-secondary">← Appointments</a>
    </div>

    @if (loading()) {
      <div class="loading-spinner">Loading…</div>
    } @else if (error()) {
      <div class="alert alert-error">{{ error() }}</div>
    } @else if (appt()) {
      @if (actionError()) {
        <div class="alert alert-error">{{ actionError() }}</div>
      }
      @if (actionSuccess()) {
        <div class="alert alert-success">{{ actionSuccess() }}</div>
      }

      <div class="card">
        <div class="appt-header">
          <div>
            <span [class]="'badge badge-' + appt()!.status">{{ appt()!.status }}</span>
            <h2 class="appt-time">{{ appt()!.start_at | date:'dd MMM yyyy HH:mm' }}</h2>
            <p class="appt-meta">
              Duration: {{ appt()!.duration_minutes }} min ·
              Doctor: {{ appt()!.doctor_id }}
            </p>
          </div>
          <div class="appt-actions">
            @if (appt()!.status === 'booked') {
              @if (auth.isReceptionist()) {
                <button class="btn btn-primary" [disabled]="acting()" (click)="checkIn()">
                  Check in
                </button>
                <button class="btn btn-danger" [disabled]="acting()" (click)="cancel()">
                  Cancel
                </button>
              }
              @if (auth.isDoctor()) {
                <button class="btn btn-secondary" [disabled]="acting()" (click)="noShow()">
                  No show
                </button>
              }
            }
          </div>
        </div>

        <dl class="detail-dl">
          <dt>Patient ID</dt><dd>{{ appt()!.patient_id }}</dd>
          <dt>Reason</dt><dd>{{ appt()!.reason ?? '—' }}</dd>
          <dt>Booked by</dt><dd>{{ appt()!.booked_by }}</dd>
          <dt>Booked at</dt><dd>{{ appt()!.booked_at | date:'dd MMM yyyy HH:mm' }}</dd>
        </dl>
      </div>
    }
  `,
  styles: [`
    .appt-header { display: flex; justify-content: space-between; align-items: flex-start; }
    .appt-time { margin: 8px 0 4px; }
    .appt-meta { color: #64748b; font-size: 0.875rem; }
    .appt-actions { display: flex; gap: 8px; }
    .detail-dl {
      display: grid;
      grid-template-columns: 120px 1fr;
      gap: 8px 16px;
      margin-top: 20px;
      font-size: 0.9rem;
    }
    dt { color: #64748b; font-weight: 500; }
  `],
})
export class AppointmentDetailComponent implements OnInit {
  readonly id = input.required<string>();

  private readonly svc = inject(AppointmentService);
  readonly auth = inject(AuthService);

  readonly appt = signal<Appointment | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly acting = signal(false);
  readonly actionError = signal<string | null>(null);
  readonly actionSuccess = signal<string | null>(null);

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.svc.get(this.id()).subscribe({
      next: a => { this.appt.set(a); this.loading.set(false); },
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
