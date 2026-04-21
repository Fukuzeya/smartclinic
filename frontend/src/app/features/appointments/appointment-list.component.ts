import {
  Component, inject, signal, OnInit, DestroyRef
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SlicePipe } from '@angular/common';
import { catchError, of } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AppointmentService } from '../../shared/api/appointment.service';
import { Appointment } from '../../shared/models/appointment.model';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-appointment-list',
  standalone: true,
  imports: [RouterLink, FormsModule, SlicePipe],
  template: `
    <div class="page-header">
      <h1>Appointments</h1>
      @if (auth.isReceptionist()) {
        <a routerLink="new" class="btn btn-primary">+ Book appointment</a>
      }
    </div>

    <div class="card filter-bar">
      @if (auth.isReceptionist() || auth.isDoctor()) {
        <div class="form-group">
          <label for="filter-date">Date</label>
          <input id="filter-date" type="date" [(ngModel)]="filterDate"
                 (change)="load()" />
        </div>
      }
    </div>

    @if (loading()) {
      <div class="loading-spinner">Loading…</div>
    } @else if (error()) {
      <div class="alert alert-error">{{ error() }}</div>
    } @else if (appointments().length === 0) {
      <div class="empty-state">
        <strong>No appointments</strong>
        <p>No appointments found for this date.</p>
      </div>
    } @else {
      <div class="card">
        <table class="data-table">
          <thead>
            <tr>
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
                <td>{{ a.start_at | slice:11:16 }}</td>
                <td>{{ a.patient_id }}</td>
                <td>{{ a.doctor_id }}</td>
                <td>
                  <span [class]="'badge badge-' + a.status">{{ a.status }}</span>
                </td>
                <td>{{ a.reason ?? '—' }}</td>
                <td>
                  <a [routerLink]="a.appointment_id" class="btn btn-secondary btn-sm">View</a>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
  `,
  styles: [`
    .filter-bar { display: flex; gap: 16px; align-items: flex-end; margin-bottom: 16px; }
    .filter-bar .form-group { margin-bottom: 0; }
  `],
})
export class AppointmentListComponent implements OnInit {
  private readonly svc = inject(AppointmentService);
  readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  readonly appointments = signal<Appointment[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  filterDate: string = new Date().toISOString().slice(0, 10);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);

    // For doctors: own schedule filtered by date.
    // For receptionists: show by date using their subject as a pass-through (backend
    // returns all appointments on that date regardless of role via the receptionist scope).
    const subject = this.auth.profile()?.subject ?? '';
    this.svc.listForDoctorOnDate(subject, this.filterDate)
      .pipe(
        catchError(() => {
          this.error.set('Failed to load appointments.');
          return of({ items: [], total: 0, limit: 20, offset: 0 });
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(resp => {
        this.appointments.set(resp.items);
        this.loading.set(false);
      });
  }
}
