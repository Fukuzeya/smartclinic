import { Component, inject, signal, input, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { PrescriptionService } from '../../shared/api/prescription.service';
import { Prescription } from '../../shared/models/prescription.model';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-prescription-detail',
  standalone: true,
  imports: [DatePipe],
  template: `
    @if (loading()) {
      <div class="loading">Loading…</div>
    } @else if (rx()) {
      <div class="page-header">
        <div>
          <h1 class="page-title">Prescription</h1>
          <code style="font-size:.85rem;color:#64748b">{{ rx()!.prescription_id }}</code>
        </div>
        <span class="badge" [class]="statusClass(rx()!.status)" style="font-size:.9rem;padding:6px 14px">
          {{ rx()!.status.replace('_', ' ') }}
        </span>
      </div>

      <div class="detail-grid">
        <!-- Prescription info -->
        <div class="card">
          <h3 class="card-title">Prescription Details</h3>
          <dl class="kv-list">
            <dt>Patient</dt><dd><code>{{ rx()!.patient_id }}</code></dd>
            <dt>Encounter</dt><dd><code>{{ rx()!.encounter_id }}</code></dd>
            <dt>Issued by</dt><dd>{{ rx()!.issued_by }}</dd>
            <dt>Received</dt><dd>{{ rx()!.received_at | date:'dd MMM yyyy HH:mm' }}</dd>
            @if (rx()!.dispensed_at) {
              <dt>Dispensed</dt><dd>{{ rx()!.dispensed_at | date:'dd MMM yyyy HH:mm' }}</dd>
            }
          </dl>

          @if (rx()!.rejection_reasons?.length) {
            <div class="alert-error" style="margin-top:12px">
              <strong>Rejection reasons:</strong>
              <ul style="margin:6px 0 0;padding-left:20px">
                @for (r of rx()!.rejection_reasons!; track r) {
                  <li>{{ r }}</li>
                }
              </ul>
            </div>
          }
        </div>

        <!-- Drug lines -->
        <div class="card">
          <h3 class="card-title">Medications</h3>
          <div class="drug-list">
            @for (ln of rx()!.lines; track ln.drug_name) {
              <div class="drug-card">
                <div class="drug-name">{{ ln.drug_name }}</div>
                <div class="drug-details">
                  <span>{{ ln.dose }}</span>
                  <span class="sep">·</span>
                  <span>{{ ln.frequency }}</span>
                  <span class="sep">·</span>
                  <span>{{ ln.duration_days }} days</span>
                  <span class="sep">·</span>
                  <span>{{ ln.route }}</span>
                </div>
                @if (ln.notes) {
                  <div class="drug-notes">{{ ln.notes }}</div>
                }
              </div>
            }
          </div>
        </div>

        <!-- Actions -->
        @if (auth.hasRole('pharmacist') && (rx()!.status === 'pending')) {
          <div class="card">
            <h3 class="card-title">Actions</h3>

            <button class="btn-primary" (click)="dispense()" [disabled]="acting()">
              💊 Dispense All Medications
            </button>

            <button class="btn-danger" style="margin-top:8px" (click)="reject()" [disabled]="acting()">
              Reject Prescription
            </button>

            @if (dispenseWarnings().length) {
              <div class="alert-warning" style="margin-top:12px">
                <strong>Warnings:</strong>
                <ul style="margin:6px 0 0;padding-left:20px">
                  @for (w of dispenseWarnings(); track w) { <li>{{ w }}</li> }
                </ul>
              </div>
            }

            @if (actionError()) { <div class="alert-error" style="margin-top:8px">{{ actionError() }}</div> }
            @if (actionSuccess()) { <div class="alert-success" style="margin-top:8px">{{ actionSuccess() }}</div> }
          </div>
        }
      </div>
    }
  `,
  styles: [`
    .detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    @media(max-width:768px){.detail-grid{grid-template-columns:1fr}}
    .card-title{font-weight:600;color:#334155;margin-bottom:12px;font-size:.95rem}
    .kv-list{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:.875rem}
    .kv-list dt{color:#64748b;font-weight:500}
    .kv-list dd{margin:0}
    .drug-list{display:flex;flex-direction:column;gap:8px}
    .drug-card{border:1px solid #e2e8f0;border-radius:8px;padding:12px}
    .drug-name{font-weight:600;color:#1e293b;font-size:.9rem}
    .drug-details{font-size:.8rem;color:#64748b;margin-top:4px}
    .sep{margin:0 4px;color:#cbd5e1}
    .drug-notes{font-size:.8rem;color:#94a3b8;margin-top:4px;font-style:italic}
    .alert-warning{background:#fffbeb;border:1px solid #f59e0b;color:#92400e;border-radius:6px;padding:10px 12px;font-size:.85rem}
  `],
})
export class PrescriptionDetailComponent implements OnInit {
  id = input.required<string>();
  readonly auth = inject(AuthService);
  private readonly svc = inject(PrescriptionService);

  rx = signal<Prescription | null>(null);
  loading = signal(true);
  acting = signal(false);
  actionError = signal('');
  actionSuccess = signal('');
  dispenseWarnings = signal<string[]>([]);

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.svc.get(this.id()).subscribe({
      next: r => { this.rx.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  dispense(): void {
    this.acting.set(true);
    this.svc.dispense(this.id()).subscribe({
      next: result => {
        this.acting.set(false);
        if (result.outcome === 'dispensed') {
          this.actionSuccess.set('Prescription dispensed successfully.');
          this.dispenseWarnings.set(result.warnings ?? []);
        } else {
          this.actionError.set('Dispensing rejected: ' + (result.reasons ?? []).join('; '));
        }
        this.reload();
      },
      error: e => { this.acting.set(false); this.actionError.set(e.error?.detail ?? 'Error'); },
    });
  }

  reject(): void {
    const reason = prompt('Enter rejection reason(s), comma-separated:');
    if (!reason?.trim()) return;
    this.acting.set(true);
    this.svc.reject(this.id(), reason.split(',').map(r => r.trim())).subscribe({
      next: () => { this.acting.set(false); this.actionSuccess.set('Prescription rejected.'); this.reload(); },
      error: e => { this.acting.set(false); this.actionError.set(e.error?.detail ?? 'Error'); },
    });
  }

  statusClass(s: string): string {
    return {
      pending: 'badge-booked',
      dispensed: 'badge-checked_in',
      partially_dispensed: 'badge-checked_in',
      rejected: 'badge-cancelled',
      cancelled: 'badge-cancelled',
    }[s] ?? '';
  }
}
