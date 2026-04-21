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
      <h1>Patient detail</h1>
      <a routerLink="/patients" class="btn btn-secondary">← Patients</a>
    </div>

    @if (loading()) {
      <div class="loading-spinner">Loading…</div>
    } @else if (error()) {
      <div class="alert alert-error">{{ error() }}</div>
    } @else if (patient()) {
      <div class="card">
        <div class="detail-header">
          <div>
            <h2>{{ patient()!.display_name }}</h2>
            <span class="sub">{{ patient()!.sex }} · DOB {{ patient()!.date_of_birth }}</span>
          </div>
          @if (auth.isReceptionist()) {
            <a [routerLink]="['/appointments', 'new']"
               [queryParams]="{ patient_id: patient()!.patient_id }"
               class="btn btn-primary">
              + Book appointment
            </a>
          }
        </div>

        <div class="detail-grid">
          <section>
            <h3>Contact</h3>
            <dl>
              <dt>Email</dt><dd>{{ patient()!.email ?? '—' }}</dd>
              <dt>Phone</dt><dd>{{ patient()!.phone ?? '—' }}</dd>
            </dl>
          </section>

          @if (patient()!.address) {
            <section>
              <h3>Address</h3>
              <dl>
                <dt>Street</dt><dd>{{ patient()!.address!.street }}</dd>
                <dt>City</dt><dd>{{ patient()!.address!.city }}</dd>
                <dt>Province</dt><dd>{{ patient()!.address!.province }}</dd>
              </dl>
            </section>
          }

          @if (patient()!.next_of_kin) {
            <section>
              <h3>Next of kin</h3>
              <dl>
                <dt>Name</dt><dd>{{ patient()!.next_of_kin!.display_name }}</dd>
                <dt>Relationship</dt><dd>{{ patient()!.next_of_kin!.relationship }}</dd>
                <dt>Phone</dt><dd>{{ patient()!.next_of_kin!.phone }}</dd>
              </dl>
            </section>
          }
        </div>
      </div>

      <div class="card">
        <h3>Consents</h3>
        @if (patient()!.consents.length === 0) {
          <p class="no-consents">No consent records.</p>
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
    .detail-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
    }
    .sub { color: #64748b; font-size: 0.9rem; }
    .detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; }
    section h3 { margin-bottom: 10px; font-size: 0.9rem; color: #475569; text-transform: uppercase; letter-spacing: 0.04em; }
    dl { display: grid; grid-template-columns: 120px 1fr; gap: 6px 12px; font-size: 0.9rem; }
    dt { color: #64748b; font-weight: 500; }
    .no-consents { color: #94a3b8; font-size: 0.9rem; margin-top: 8px; }
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
