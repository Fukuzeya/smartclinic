import {
  Component, inject, signal, OnInit, DestroyRef
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SlicePipe } from '@angular/common';
import { catchError, of } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AppointmentService } from '../../shared/api/appointment.service';
import { Appointment, AppointmentStatus } from '../../shared/models/appointment.model';
import { AuthService } from '../../core/auth/auth.service';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';
import { DoctorNameCache } from '../../shared/services/doctor-name-cache.service';

type StatusFilter = '' | AppointmentStatus;

@Component({
  selector: 'app-appointment-list',
  standalone: true,
  imports: [RouterLink, FormsModule, SlicePipe],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Appointments</h1>
        <p class="page-subtitle">Schedule and manage patient consultations</p>
      </div>
      @if (auth.isReceptionist()) {
        <a routerLink="new" class="btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Book Appointment
        </a>
      }
    </div>

    <div class="filter-bar">
      <!-- Date filter -->
      <div class="filter-group">
        <label class="filter-label" for="filter-date">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          Date
        </label>
        <div class="date-wrap">
          <input id="filter-date" type="date" class="form-control filter-date-input"
                 [(ngModel)]="filterDate" (change)="load()" />
          @if (filterDate) {
            <button type="button" class="clear-date-btn" (click)="clearDate()" title="Show all dates">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          }
        </div>
      </div>

      <!-- Status chips -->
      <div class="status-chips">
        @for (s of statusOptions; track s.value) {
          <button type="button"
                  [class]="'chip' + (filterStatus === s.value ? ' chip-active chip-' + (s.value || 'all') : '')"
                  (click)="setStatus(s.value)">
            {{ s.label }}
          </button>
        }
      </div>

      <!-- Result count -->
      @if (!loading()) {
        <span class="result-count">{{ appointments().length }} result{{ appointments().length !== 1 ? 's' : '' }}</span>
      }
    </div>

    @if (loading()) {
      <div class="loading">Loading…</div>
    } @else if (error()) {
      <div class="alert-error">{{ error() }}</div>
    } @else if (appointments().length === 0) {
      <div class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:var(--clr-gray-300)"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <strong>No appointments found</strong>
        <p>Try changing the date or status filter.</p>
      </div>
    } @else {
      <div class="card">
        <table class="data-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Time</th>
              <th>Patient</th>
              <th>Doctor</th>
              <th>Status</th>
              <th>Reason</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (a of appointments(); track a.appointment_id) {
              <tr>
                <td class="date-cell">{{ a.start_at | slice:0:10 }}</td>
                <td class="time-cell">{{ a.start_at | slice:11:16 }}</td>
                <td class="name-cell" title="{{ a.patient_id }}">{{ patientNames()[a.patient_id] || '…' }}</td>
                <td class="name-cell" title="{{ a.doctor_id }}">{{ doctorNames()[a.doctor_id] || '…' }}</td>
                <td>
                  <span [class]="'badge badge-' + a.status">{{ statusLabel(a.status) }}</span>
                </td>
                <td class="reason-cell">{{ a.reason ?? '—' }}</td>
                <td>
                  <a [routerLink]="a.appointment_id" class="btn-secondary btn-sm">View</a>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
  `,
  styles: [`
    .filter-bar {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    .filter-group {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .filter-label {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: .8rem;
      font-weight: 600;
      color: var(--clr-gray-600);
      white-space: nowrap;
    }
    .date-wrap { position: relative; display: flex; align-items: center; }
    .filter-date-input { width: 160px; }
    .clear-date-btn {
      position: absolute; right: 8px;
      background: none; border: none; cursor: pointer;
      color: var(--clr-gray-400); display: flex; align-items: center;
      padding: 0;
      &:hover { color: var(--clr-gray-700); }
    }
    .status-chips {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .chip {
      padding: 4px 12px;
      border-radius: 20px;
      border: 1px solid var(--clr-gray-200);
      background: var(--clr-surface);
      font-size: .78rem;
      font-weight: 500;
      color: var(--clr-gray-600);
      cursor: pointer;
      transition: all .15s;
      &:hover { border-color: var(--clr-brand); color: var(--clr-brand); }
    }
    .chip-active { font-weight: 700; }
    .chip-all    { border-color: var(--clr-brand); color: var(--clr-brand); background: var(--clr-brand-light); }
    .chip-booked      { border-color: var(--clr-info); color: var(--clr-info); background: var(--clr-info-bg, #eff6ff); }
    .chip-checked_in  { border-color: var(--clr-success); color: var(--clr-success); background: var(--clr-success-bg); }
    .chip-cancelled   { border-color: var(--clr-danger); color: var(--clr-danger); background: var(--clr-danger-bg, #fef2f2); }
    .chip-no_show     { border-color: var(--clr-warning, #d97706); color: var(--clr-warning, #d97706); background: #fffbeb; }

    .result-count {
      margin-left: auto;
      font-size: .78rem;
      color: var(--clr-gray-400);
    }
    .date-cell { white-space: nowrap; font-size: .85rem; }
    .time-cell { white-space: nowrap; font-weight: 600; }
    .id-cell   { font-family: monospace; font-size: .8rem; color: var(--clr-gray-500); }
    .reason-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  `],
})
export class AppointmentListComponent implements OnInit {
  private readonly svc = inject(AppointmentService);
  readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly nameCache = inject(PatientNameCache);
  private readonly doctorCache = inject(DoctorNameCache);

  readonly appointments = signal<Appointment[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly patientNames = signal<Record<string, string>>({});
  readonly doctorNames = signal<Record<string, string>>({});

  filterDate = '';
  filterStatus: StatusFilter = '';

  readonly statusOptions: { value: StatusFilter; label: string }[] = [
    { value: '',           label: 'All' },
    { value: 'booked',     label: 'Booked' },
    { value: 'checked_in', label: 'Checked-in' },
    { value: 'cancelled',  label: 'Cancelled' },
    { value: 'no_show',    label: 'No-show' },
  ];

  ngOnInit(): void { this.load(); }

  clearDate(): void { this.filterDate = ''; this.load(); }
  setStatus(s: StatusFilter): void { this.filterStatus = s; this.load(); }

  statusLabel(s: string): string {
    return { booked: 'Booked', checked_in: 'Checked-in', cancelled: 'Cancelled', no_show: 'No-show' }[s] ?? s;
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.svc.list(
      undefined,
      this.filterDate || undefined,
      this.filterStatus || undefined,
    ).pipe(
      catchError(() => {
        this.error.set('Failed to load appointments.');
        return of({ items: [], total: 0, limit: 50, offset: 0 });
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(resp => {
      this.appointments.set(resp.items);
      this.loading.set(false);
      const pIds = resp.items.map(a => a.patient_id);
      if (pIds.length) this.nameCache.resolveMany(pIds).subscribe(m => this.patientNames.set(m));
      const dIds = resp.items.map(a => a.doctor_id);
      if (dIds.length) this.doctorCache.resolveMany(dIds).subscribe(m => this.doctorNames.set(m));
    });
  }
}
