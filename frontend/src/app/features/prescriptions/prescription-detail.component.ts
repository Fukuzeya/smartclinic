import { Component, inject, signal, input, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, NgClass, SlicePipe } from '@angular/common';
import { PrescriptionService } from '../../shared/api/prescription.service';
import { Prescription } from '../../shared/models/prescription.model';
import { EncounterService, AISuggestionResponse } from '../../shared/api/encounter.service';
import { AuthService } from '../../core/auth/auth.service';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';

@Component({
  selector: 'app-prescription-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, NgClass, SlicePipe],
  template: `
    @if (loading()) {
      <div class="loading">Loading prescription…</div>
    } @else if (!rx()) {
      <div class="empty-state">Prescription not found.</div>
    } @else {
      <div class="page-header">
        <div>
          <h1 class="page-title">Prescription</h1>
          <code style="font-size:0.8rem;color:#64748b">{{ rx()!.prescription_id }}</code>
        </div>
        <span class="badge" [ngClass]="statusClass(rx()!.status)" style="font-size:0.9rem;padding:6px 14px">
          {{ rx()!.status }}
        </span>
      </div>

      <div class="workspace-grid">
        <!-- Left: prescription details -->
        <div class="workspace-main">
          <div class="card">
            <h3 class="card-title">Prescription Details</h3>
            <dl class="kv-list">
              <dt>Patient</dt><dd>{{ patientName() || rx()!.patient_id }}</dd>
              <dt>Encounter</dt>
              <dd>
                <a [routerLink]="['/encounters', rx()!.encounter_id]" class="link">
                  {{ rx()!.encounter_id | slice:0:18 }}…
                </a>
              </dd>
              <dt>Issued by</dt><dd>{{ rx()!.issued_by }}</dd>
              <dt>Received</dt><dd>{{ rx()!.received_at | date:'dd MMM yyyy HH:mm' }}</dd>
              @if (rx()!.dispensed_at) {
                <dt>Dispensed</dt><dd>{{ rx()!.dispensed_at | date:'dd MMM yyyy HH:mm' }}</dd>
              }
            </dl>
          </div>

          <div class="card" style="margin-top:16px">
            <h3 class="card-title">Drug Lines</h3>
            <div class="drug-table">
              <div class="drug-row drug-row-header">
                <span>Drug</span><span>Dose</span><span>Route</span><span>Frequency</span><span>Days</span>
              </div>
              @for (line of rx()!.lines; track line.drug_name) {
                <div class="drug-row">
                  <span class="drug-name">{{ line.drug_name }}</span>
                  <span>{{ line.dose }}</span>
                  <span>{{ line.route }}</span>
                  <span>{{ line.frequency }}</span>
                  <span>{{ line.duration_days }}d</span>
                </div>
                @if (line.notes) {
                  <div class="drug-notes">↳ {{ line.notes }}</div>
                }
              }
            </div>
          </div>
        </div>

        <!-- Right: dispensing action panel -->
        <div class="workspace-sidebar">
          @if (rx()!.status === 'pending' || rx()!.status === 'partially_dispensed') {
            <div class="card action-panel">
              <h3 class="card-title">Dispensing Actions</h3>

              @if (auth.hasRole('pharmacist')) {
              <!-- Result from last dispense attempt -->
              @if (dispenseResult()) {
                @if (dispenseResult()!.outcome === 'rejected') {
                  <div class="alert-error" style="margin-bottom:12px">
                    <strong>Dispensing blocked</strong>
                    <ul class="reasons-list">
                      @for (r of dispenseResult()!.reasons; track r) { <li>{{ r }}</li> }
                    </ul>
                    @if (dispenseResult()!.out_of_stock_drugs?.length) {
                      <div style="margin-top:8px;font-size:0.8rem;color:#7f1d1d">
                        ⚠ Out of stock: {{ dispenseResult()!.out_of_stock_drugs.join(', ') }} —
                        saga compensation triggered; doctor will be notified to substitute.
                      </div>
                    }
                  </div>

                  <!-- AI drug-safety narrative -->
                  @if (!aiNarrative() && !aiLoading()) {
                    <button class="btn-ai-explain" (click)="explainSafety()">
                      🤖 AI: Explain safety concern
                    </button>
                  }
                  @if (aiLoading()) {
                    <div style="font-size:.8rem;color:var(--clr-brand);margin-top:8px">Generating explanation…</div>
                  }
                  @if (aiNarrative()) {
                    <div class="ai-narrative">
                      <div class="ai-narrative-header">🤖 AI Drug Safety Explanation</div>
                      <div class="ai-narrative-disclaimer">{{ aiNarrative()!.disclaimer }}</div>
                      <p class="ai-narrative-text">{{ aiNarrative()!.suggestion_text }}</p>
                      <div class="ai-narrative-meta">Model: <code>{{ aiNarrative()!.model_id }}</code></div>
                      @if (!aiDecision()) {
                        <div style="display:flex;gap:6px;margin-top:8px">
                          <button class="btn-ai-accept" (click)="recordAiDecision('accepted')">✓ Noted</button>
                          <button class="btn-ai-discard" (click)="recordAiDecision('discarded')">✕ Dismiss</button>
                        </div>
                      } @else {
                        <div style="font-size:.75rem;color:#475569;margin-top:6px">
                          {{ aiDecision() === 'accepted' ? '✓ Noted by pharmacist' : '✕ Dismissed' }}
                        </div>
                      }
                    </div>
                  }
                } @else if (dispenseResult()!.warnings?.length) {
                  <div class="alert-warning" style="margin-bottom:12px">
                    <strong>Advisory warnings (non-blocking)</strong>
                    <ul class="reasons-list">
                      @for (w of dispenseResult()!.warnings; track w) { <li>{{ w }}</li> }
                    </ul>
                  </div>
                }
              }

              @if (actionError()) {
                <div class="alert-error" style="margin-bottom:12px">{{ actionError() }}</div>
              }

              <button class="btn-primary" style="width:100%"
                      [disabled]="dispensing()"
                      (click)="dispense()">
                {{ dispensing() ? 'Running specification check…' : '✓ Dispense All (run spec check)' }}
              </button>

              <div class="spec-note">
                AllDrugsInStock ∧ PatientConsent ∧ NoSevereInteraction
              </div>
              } @else {
                <p class="muted">Read-only — dispensing requires pharmacist role.</p>
              }
            </div>
          } @else {
            <div class="card">
              <h3 class="card-title">Status</h3>
              <div class="status-summary" [ngClass]="statusClass(rx()!.status)">
                {{ rx()!.status === 'dispensed'   ? '✓ Fully dispensed' :
                   rx()!.status === 'rejected'    ? '✗ Rejected by specification' :
                   rx()!.status === 'cancelled'   ? 'Cancelled' : rx()!.status }}
              </div>
              @if (rx()!.rejection_reasons?.length) {
                <ul class="reasons-list" style="margin-top:8px">
                  @for (r of rx()!.rejection_reasons!; track r) { <li>{{ r }}</li> }
                </ul>
              }
            </div>
          }

          <!-- Specification chain explainer -->
          <div class="card" style="margin-top:16px">
            <h3 class="card-title">Specification Chain</h3>
            <div class="spec-chain">
              <div class="spec-step">
                <span class="spec-icon">📦</span>
                <div>
                  <div class="spec-name">AllDrugsInStock</div>
                  <div class="spec-desc">All drugs must have ≥ 1 unit on hand</div>
                </div>
              </div>
              <div class="spec-connector">∧</div>
              <div class="spec-step">
                <span class="spec-icon">✅</span>
                <div>
                  <div class="spec-name">PatientConsentGranted</div>
                  <div class="spec-desc">Active TREATMENT consent on file</div>
                </div>
              </div>
              <div class="spec-connector">∧</div>
              <div class="spec-step">
                <span class="spec-icon">⛔</span>
                <div>
                  <div class="spec-name">NoSevereDrugInteraction</div>
                  <div class="spec-desc">No SEVERE drug–drug interactions (via RxNav ACL)</div>
                </div>
              </div>
            </div>
            <div style="font-size:0.7rem;color:#94a3b8;margin-top:8px">
              ADR 0006 — Specification Pattern · ADR 0007 — Anti-Corruption Layer
            </div>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .workspace-grid { display: grid; grid-template-columns: 1fr 340px; gap: 16px; align-items: start; }
    @media (max-width: 900px) { .workspace-grid { grid-template-columns: 1fr; } }
    .workspace-sidebar { position: sticky; top: calc(var(--header-h) + 16px); }
    .card-title { font-weight: 600; color: var(--clr-gray-700); margin-bottom: 12px; font-size: 0.95rem; }
    .kv-list { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; font-size: 0.875rem; }
    .kv-list dt { color: var(--clr-gray-500); font-weight: 500; }
    .kv-list dd { margin: 0; color: var(--clr-gray-800); }
    .link { color: var(--clr-accent); text-decoration: none; }
    .link:hover { text-decoration: underline; }
    .drug-table { font-size: 0.85rem; }
    .drug-row { display: grid; grid-template-columns: 2fr 1fr 1fr 2fr 1fr; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--clr-gray-100); align-items: center; }
    .drug-row-header { font-weight: 600; color: var(--clr-gray-500); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .drug-name { font-weight: 600; color: var(--clr-gray-800); }
    .drug-notes { font-size: 0.8rem; color: var(--clr-gray-500); padding: 2px 0 8px 8px; border-bottom: 1px solid var(--clr-gray-100); }
    .action-panel { border: 2px solid var(--clr-accent); }
    .spec-note { font-size: 0.7rem; color: var(--clr-gray-400); text-align: center; margin-top: 8px; font-family: monospace; }
    .reasons-list { margin: 6px 0 0; padding-left: 16px; font-size: 0.8rem; display: flex; flex-direction: column; gap: 3px; }
    .spec-chain { display: flex; flex-direction: column; gap: 8px; }
    .spec-step { display: flex; gap: 10px; align-items: flex-start; }
    .spec-icon { font-size: 1.1rem; width: 28px; text-align: center; flex-shrink: 0; }
    .spec-name { font-weight: 600; font-size: 0.8rem; color: var(--clr-gray-700); }
    .spec-desc { font-size: 0.75rem; color: var(--clr-gray-500); }
    .spec-connector { text-align: center; color: var(--clr-gray-400); font-weight: 700; font-size: 1rem; padding-left: 14px; }
    .status-summary { font-size: 0.95rem; font-weight: 600; padding: 10px 14px; border-radius: 6px; }
    .badge-dispensed { background: #d1fae5; color: #065f46; }
    .badge-rejected { background: #fee2e2; color: #991b1b; }
    .badge-pending { background: #fef3c7; color: #92400e; }
    .badge-partially_dispensed { background: #dbeafe; color: #1e40af; }
    .badge-cancelled { background: #f1f5f9; color: #475569; }
    .alert-warning { background: #fef3c7; border: 1px solid #fcd34d; color: #92400e; padding: 10px 12px; border-radius: 6px; font-size: 0.85rem; }
    .btn-ai-explain { margin-top: 10px; background: var(--clr-brand-light); color: var(--clr-brand); border: 1px solid #BEDAF7; border-radius: 4px; padding: 6px 12px; font-size: 0.78rem; cursor: pointer; }
    .btn-ai-explain:hover { background: #D1E8F8; }
    .ai-narrative { margin-top: 10px; border: 1px solid #BEDAF7; border-radius: 6px; padding: 12px; background: var(--clr-brand-light); }
    .ai-narrative-header { font-weight: 700; color: var(--clr-brand); font-size: 0.8rem; margin-bottom: 4px; }
    .ai-narrative-disclaimer { font-size: 0.7rem; color: #92400e; background: #fef9c3; padding: 4px 8px; border-radius: 4px; margin-bottom: 8px; }
    .ai-narrative-text { font-size: 0.82rem; color: #1e293b; margin: 0 0 6px; line-height: 1.5; }
    .ai-narrative-meta { font-size: 0.7rem; color: #94a3b8; }
    .btn-ai-accept { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; border-radius: 5px; padding: 4px 10px; font-size: .75rem; cursor: pointer; }
    .btn-ai-discard { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 5px; padding: 4px 10px; font-size: .75rem; cursor: pointer; }
  `],
})
export class PrescriptionDetailComponent implements OnInit {
  id = input.required<string>();
  private readonly svc = inject(PrescriptionService);
  private readonly encSvc = inject(EncounterService);
  readonly auth = inject(AuthService);
  private readonly nameCache = inject(PatientNameCache);

  rx = signal<Prescription | null>(null);
  loading = signal(true);
  dispensing = signal(false);
  actionError = signal('');
  patientName = signal('');
  dispenseResult = signal<{ outcome: string; reasons: string[]; out_of_stock_drugs: string[]; warnings: string[] } | null>(null);
  aiNarrative = signal<AISuggestionResponse | null>(null);
  aiLoading = signal(false);
  aiDecision = signal<'accepted' | 'discarded' | null>(null);

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.svc.get(this.id()).subscribe({
      next: r => {
        this.rx.set(r);
        this.loading.set(false);
        this.nameCache.resolve(r.patient_id).subscribe(n => this.patientName.set(n));
      },
      error: () => this.loading.set(false),
    });
  }

  dispense(): void {
    this.dispensing.set(true);
    this.actionError.set('');
    this.dispenseResult.set(null);
    this.svc.dispense(this.id()).subscribe({
      next: result => {
        this.dispenseResult.set(result);
        this.dispensing.set(false);
        if (result.outcome === 'dispensed') this.reload();
      },
      error: err => {
        const detail = err.error?.detail;
        if (detail && typeof detail === 'object') {
          this.dispenseResult.set({
            outcome: 'rejected',
            reasons: detail.reasons ?? [],
            out_of_stock_drugs: detail.out_of_stock_drugs ?? [],
            warnings: [],
          });
        } else {
          this.actionError.set(detail ?? 'Dispense failed');
        }
        this.dispensing.set(false);
      },
    });
  }

  explainSafety(): void {
    const result = this.dispenseResult();
    const rx = this.rx();
    if (!result || !rx) return;
    this.aiLoading.set(true);
    this.encSvc.explainDrugSafety(
      rx.encounter_id,
      rx.lines.map(l => l.drug_name),
      result.reasons,
    ).subscribe({
      next: r => { this.aiNarrative.set(r); this.aiLoading.set(false); },
      error: () => this.aiLoading.set(false),
    });
  }

  recordAiDecision(d: 'accepted' | 'discarded'): void {
    const n = this.aiNarrative();
    if (!n) return;
    this.encSvc.recordAIDecision(n.suggestion_id, d).subscribe();
    this.aiDecision.set(d);
  }

  statusClass(status: string): string {
    return `badge-${status}`;
  }
}
