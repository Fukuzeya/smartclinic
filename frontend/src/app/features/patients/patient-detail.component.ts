import {
  Component, inject, signal, OnInit, input
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { SlicePipe } from '@angular/common';
import { PatientService } from '../../shared/api/patient.service';
import { Patient } from '../../shared/models/patient.model';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-patient-detail',
  standalone: true,
  imports: [RouterLink, SlicePipe],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Patient</h1>
        <p class="page-subtitle">Demographic record and consents</p>
      </div>
      <a routerLink="/patients" class="btn-secondary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        Patients
      </a>
    </div>

    @if (loading()) {
      <div class="loading">Loading…</div>
    } @else if (error()) {
      <div class="alert-error">{{ error() }}</div>
    } @else if (patient()) {
      <div class="card patient-hero">
        <div class="patient-avatar-lg">{{ patient()!.display_name[0] }}</div>
        <div class="patient-hero-info">
          <h2 class="patient-name">{{ patient()!.display_name }}</h2>
          <p class="patient-meta">{{ patient()!.sex }} · DOB {{ patient()!.date_of_birth }}</p>
          <code class="patient-id">{{ patient()!.patient_id }}</code>
        </div>
        @if (auth.isReceptionist()) {
          <a [routerLink]="['/appointments', 'new']"
             [queryParams]="{ patient_id: patient()!.patient_id }"
             class="btn-primary">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Book Appointment
          </a>
        }
      </div>

      <div class="detail-grid" style="margin-top:16px">
        <section class="card">
          <h3 class="section-heading">Contact</h3>
          <dl class="kv-list">
            <dt>Email</dt><dd>{{ patient()!.email ?? '—' }}</dd>
            <dt>Phone</dt><dd>{{ patient()!.phone ?? '—' }}</dd>
          </dl>
        </section>

        @if (patient()!.address) {
          <section class="card">
            <h3 class="section-heading">Address</h3>
            <dl class="kv-list">
              <dt>Street</dt><dd>{{ patient()!.address!.street }}</dd>
              <dt>City</dt><dd>{{ patient()!.address!.city }}</dd>
              <dt>Province</dt><dd>{{ patient()!.address!.province }}</dd>
            </dl>
          </section>
        }

        @if (patient()!.next_of_kin) {
          <section class="card">
            <h3 class="section-heading">Next of Kin</h3>
            <dl class="kv-list">
              <dt>Name</dt><dd>{{ patient()!.next_of_kin!.display_name }}</dd>
              <dt>Relationship</dt><dd>{{ patient()!.next_of_kin!.relationship }}</dd>
              <dt>Phone</dt><dd>{{ patient()!.next_of_kin!.phone }}</dd>
            </dl>
          </section>
        }
      </div>

      <div class="card" style="margin-top:16px">
        <h3 class="section-heading">Consents</h3>
        @if (patient()!.consents.length === 0) {
          <p class="muted">No consent records.</p>
        } @else {
          <table class="data-table">
            <thead>
              <tr><th>Purpose</th><th>Status</th><th>Granted</th><th>Revoked</th></tr>
            </thead>
            <tbody>
              @for (c of patient()!.consents; track c.purpose) {
                <tr>
                  <td>{{ c.purpose }}</td>
                  <td>
                    <span [class]="'badge badge-' + (c.is_active ? 'checked_in' : 'cancelled')">
                      {{ c.is_active ? 'Active' : 'Revoked' }}
                    </span>
                  </td>
                  <td>{{ c.granted_at | slice:0:10 }}</td>
                  <td>{{ c.revoked_at ? (c.revoked_at | slice:0:10) : '—' }}</td>
                </tr>
              }
            </tbody>
          </table>
        }
      </div>
    }
  `,
  styles: [`
    .patient-hero {
      display: flex; align-items: center; gap: 20px; padding: 24px;
    }
    .patient-avatar-lg {
      width: 60px; height: 60px; border-radius: 50%;
      background: var(--clr-brand); color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.5rem; font-weight: 700; flex-shrink: 0;
    }
    .patient-hero-info { flex: 1; }
    .patient-name { font-size: 1.25rem; font-weight: 700; color: var(--clr-gray-800); margin: 0 0 2px; }
    .patient-meta { color: var(--clr-gray-500); font-size: 0.875rem; margin: 0 0 4px; }
    .patient-id { font-size: 0.75rem; color: var(--clr-gray-400); }
    .detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .section-heading { font-size: 0.75rem; font-weight: 700; color: var(--clr-gray-400); text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 12px; }
    .kv-list { display: grid; grid-template-columns: 110px 1fr; gap: 6px 12px; font-size: 0.875rem; }
    .kv-list dt { color: var(--clr-gray-500); font-weight: 500; }
    .kv-list dd { margin: 0; color: var(--clr-gray-800); }
    .muted { color: var(--clr-gray-400); font-size: 0.875rem; }
  `],
})
export class PatientDetailComponent implements OnInit {
  readonly id = input.required<string>();

  private readonly svc = inject(PatientService);
  readonly auth = inject(AuthService);

  readonly patient = signal<Patient | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.svc.get(this.id()).subscribe({
      next: p => { this.patient.set(p); this.loading.set(false); },
      error: () => { this.error.set('Patient not found.'); this.loading.set(false); },
    });
  }
}
