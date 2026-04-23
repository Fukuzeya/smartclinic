import { Component, inject, signal, input, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators, FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EncounterService, PrescriptionLine, LabTestLine } from '../../shared/api/encounter.service';
import { Encounter } from '../../shared/models/encounter.model';
import { AuthService } from '../../core/auth/auth.service';
import { EncounterTimelineComponent } from './encounter-timeline.component';
import { AiSoapCopilotComponent } from './ai-soap-copilot.component';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';
import { timer } from 'rxjs';

@Component({
  selector: 'app-encounter-detail',
  standalone: true,
  imports: [RouterLink, ReactiveFormsModule, FormsModule, EncounterTimelineComponent, AiSoapCopilotComponent],
  template: `
    @if (loading()) {
      <div class="loading">Loading encounter…</div>
    } @else if (!encounter()) {
      <div class="empty-state">
        <h2>Encounter not found</h2>
        <p style="color:var(--clr-gray-500)">The encounter may still be processing. Try refreshing in a moment.</p>
        <button class="btn-secondary" (click)="reload()">↻ Retry</button>
      </div>
    } @else if (encounter()) {
      <div class="page-header">
        <div>
          <h1 class="page-title">Encounter</h1>
          <div style="font-size:0.9rem;color:var(--clr-gray-700);font-weight:600;margin-top:2px">{{ patientName() || 'Patient' }}</div>
          <code style="font-size:0.85rem;color:var(--clr-gray-500)">{{ encounter()!.encounter_id }}</code>
        </div>
        <span class="badge" [class]="'badge-' + encounter()!.status" style="font-size:0.9rem;padding:6px 14px">
          {{ encounter()!.status.replace('_', ' ') }}
        </span>
      </div>

      <div class="detail-grid">
        <!-- Vitals card -->
        <div class="card">
          <h3 class="card-title">Vital Signs</h3>
          @if (encounter()!.vitals) {
            <dl class="kv-list">
              <dt>Temperature</dt><dd>{{ encounter()!.vitals?.temperature_c ?? '–' }} °C</dd>
              <dt>Pulse</dt><dd>{{ encounter()!.vitals?.pulse_bpm ?? '–' }} bpm</dd>
              <dt>BP</dt><dd>{{ encounter()!.vitals?.systolic_bp ?? '–' }}/{{ encounter()!.vitals?.diastolic_bp ?? '–' }} mmHg</dd>
              <dt>SpO₂</dt><dd>{{ encounter()!.vitals?.oxygen_saturation ?? '–' }} %</dd>
              <dt>Weight</dt><dd>{{ encounter()!.vitals?.weight_kg ?? '–' }} kg</dd>
            </dl>
          } @else {
            <p class="muted">No vitals recorded.</p>
          }

          @if (encounter()!.status === 'in_progress' && auth.isDoctor()) {
            <form [formGroup]="vitalsForm" (ngSubmit)="saveVitals()" class="inline-form">
              <div class="form-row">
                <input class="form-control" type="number" formControlName="temperature_c" placeholder="Temp °C" step="0.1" />
                <input class="form-control" type="number" formControlName="pulse_bpm" placeholder="Pulse bpm" />
                <input class="form-control" type="number" formControlName="systolic_bp" placeholder="Systolic" />
                <input class="form-control" type="number" formControlName="diastolic_bp" placeholder="Diastolic" />
                <input class="form-control" type="number" formControlName="oxygen_saturation" placeholder="SpO₂ %" />
              </div>
              <button type="submit" class="btn-secondary btn-sm">Save Vitals</button>
            </form>
          }
        </div>

        <!-- SOAP card -->
        <div class="card">
          <h3 class="card-title">SOAP Note</h3>
          @if (encounter()!.soap) {
            <dl class="kv-list">
              <dt>Subjective</dt><dd>{{ encounter()!.soap?.subjective }}</dd>
              <dt>Objective</dt><dd>{{ encounter()!.soap?.objective }}</dd>
              <dt>Assessment</dt><dd>{{ encounter()!.soap?.assessment }}</dd>
              <dt>Plan</dt><dd>{{ encounter()!.soap?.plan }}</dd>
            </dl>
          } @else {
            <p class="muted">No SOAP note recorded.</p>
          }

          @if (encounter()!.status === 'in_progress' && auth.isDoctor()) {
            <form [formGroup]="soapForm" (ngSubmit)="saveSOAP()" class="inline-form">
              <textarea class="form-control" formControlName="subjective" placeholder="Subjective…" rows="2"></textarea>
              <textarea class="form-control" formControlName="objective"  placeholder="Objective…"  rows="2"></textarea>
              <textarea class="form-control" formControlName="assessment" placeholder="Assessment…" rows="2"></textarea>
              <textarea class="form-control" formControlName="plan"       placeholder="Plan…"       rows="2"></textarea>
              <button type="submit" class="btn-secondary btn-sm">Save SOAP</button>
            </form>
          }
        </div>

        <!-- Diagnoses card -->
        <div class="card">
          <h3 class="card-title">Diagnoses</h3>
          @if (encounter()!.diagnoses.length) {
            <ul class="dx-list">
              @for (dx of encounter()!.diagnoses; track dx.icd10_code) {
                <li>
                  <code class="icd-code">{{ dx.icd10_code }}</code>
                  {{ dx.description }}
                  @if (dx.is_primary) { <span class="badge badge-booked" style="font-size:0.7rem">Primary</span> }
                </li>
              }
            </ul>
          } @else {
            <p class="muted">No diagnoses recorded.</p>
          }

          @if (encounter()!.status === 'in_progress' && auth.isDoctor()) {
            <form [formGroup]="dxForm" (ngSubmit)="addDx()" class="inline-form">
              <div class="form-row">
                <input class="form-control" formControlName="icd10_code" placeholder="ICD-10 code e.g. J06.9" />
                <input class="form-control" formControlName="description" placeholder="Description" />
              </div>
              <button type="submit" class="btn-secondary btn-sm">Add Diagnosis</button>
            </form>
          }
        </div>

        <!-- Actions card -->
        <div class="card">
          <h3 class="card-title">Actions</h3>

          @if (encounter()!.status === 'in_progress' && auth.isDoctor()) {
            <!-- Issue Prescription -->
            <details class="action-section">
              <summary class="action-toggle">💊 Issue Prescription</summary>
              <div class="rx-lines">
                @for (line of rxLines; track $index) {
                  <div class="rx-line-row">
                    <input class="form-control" [(ngModel)]="line.drug_name" placeholder="Drug name" />
                    <input class="form-control" [(ngModel)]="line.dose" placeholder="Dose e.g. 500mg" />
                    <input class="form-control" [(ngModel)]="line.route" placeholder="Route e.g. PO" />
                    <input class="form-control" [(ngModel)]="line.frequency" placeholder="Freq e.g. TDS" />
                    <input class="form-control" type="number" [(ngModel)]="line.duration_days" placeholder="Days" style="max-width:70px" />
                    <input class="form-control" [(ngModel)]="line.instructions" placeholder="Instructions (optional)" />
                    @if (rxLines.length > 1) {
                      <button type="button" class="btn-icon" (click)="removeRxLine($index)" title="Remove">✕</button>
                    }
                  </div>
                }
                <div class="rx-actions">
                  <button type="button" class="btn-secondary btn-sm" (click)="addRxLine()">+ Add line</button>
                  <button type="button" class="btn-primary btn-sm" (click)="submitPrescription()" [disabled]="!canSubmitRx()">Issue Prescription</button>
                </div>
              </div>
            </details>

            <!-- Place Lab Order -->
            <details class="action-section">
              <summary class="action-toggle">🧪 Place Lab Order</summary>
              <div class="rx-lines">
                @for (test of labLines; track $index) {
                  <div class="rx-line-row">
                    <input class="form-control" [(ngModel)]="test.test_code" placeholder="Test code e.g. FBC, U&E" />
                    <select class="form-control" [(ngModel)]="test.urgency" style="max-width:120px">
                      <option value="routine">Routine</option>
                      <option value="urgent">Urgent</option>
                      <option value="stat">STAT</option>
                    </select>
                    <input class="form-control" [(ngModel)]="test.notes" placeholder="Notes (optional)" />
                    @if (labLines.length > 1) {
                      <button type="button" class="btn-icon" (click)="removeLabLine($index)" title="Remove">✕</button>
                    }
                  </div>
                }
                <div class="rx-actions">
                  <button type="button" class="btn-secondary btn-sm" (click)="addLabLine()">+ Add test</button>
                  <button type="button" class="btn-primary btn-sm" (click)="submitLabOrder()" [disabled]="!canSubmitLab()">Place Lab Order</button>
                </div>
              </div>
            </details>
          }

          <div class="action-list" style="margin-top:12px">
            <a [routerLink]="['/lab-orders']" [queryParams]="{encounter_id: encounter()!.encounter_id}" class="action-row">
              🧪 View Lab Orders for this encounter
            </a>
            <a [routerLink]="['/prescriptions']" [queryParams]="{encounter_id: encounter()!.encounter_id}" class="action-row">
              💊 View Prescriptions for this encounter
            </a>
            <a [routerLink]="['/invoices']" [queryParams]="{encounter_id: encounter()!.encounter_id}" class="action-row">
              💵 View Invoice
            </a>
            <a [routerLink]="['/visit-tracker']" [queryParams]="{encounter_id: encounter()!.encounter_id}" class="action-row">
              🗺️ Visit Tracker
            </a>
          </div>

          @if (encounter()!.status === 'in_progress' && auth.isDoctor()) {
            <button class="btn-danger" style="margin-top:16px" (click)="closeEncounter()">
              Close & Sign Encounter
            </button>
          }

          @if (chainResult()) {
            <div [class]="chainResult()!.is_valid ? 'alert-success' : 'alert-error'" style="margin-top:12px">
              {{ chainResult()!.is_valid ? '✓ Event chain intact — ' + chainResult()!.event_count + ' events verified' : '⚠ Chain broken: ' + chainResult()!.message }}
            </div>
          }
          <button class="btn-secondary btn-sm" style="margin-top:8px" (click)="verifyChain()">🔒 Verify audit chain</button>

          @if (actionError()) { <div class="alert-error" style="margin-top:8px">{{ actionError() }}</div> }
        </div>
      </div>

      <!-- AI Clinical Copilot — SOAP draft (doctors only, in-progress encounters) -->
      @if (encounter()!.status === 'in_progress' && auth.isDoctor()) {
        <div style="margin-top:16px">
          <app-ai-soap-copilot [encounterId]="id()" />
        </div>
      }

      <!-- Event Sourcing timeline — the demo showpiece -->
      <div class="card" style="margin-top:16px">
        <app-encounter-timeline [encounterId]="id()" />
      </div>
    }
  `,
  styles: [`
    .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 768px) { .detail-grid { grid-template-columns: 1fr; } }
    .card-title { font-weight: 600; color: var(--clr-gray-700); margin-bottom: 12px; font-size: 0.95rem; }
    .kv-list { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; font-size: 0.875rem; }
    .kv-list dt { color: var(--clr-gray-500); font-weight: 500; }
    .kv-list dd { margin: 0; color: var(--clr-gray-800); }
    .muted { color: var(--clr-gray-400); font-size: 0.875rem; }
    .inline-form { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
    .form-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .form-row .form-control { flex: 1; min-width: 80px; }
    .btn-sm { padding: 6px 14px; font-size: 0.8rem; }
    .dx-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; font-size: 0.875rem; }
    .icd-code { background: var(--clr-gray-100); padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin-right: 8px; }
    .action-list { display: flex; flex-direction: column; gap: 8px; }
    .action-row { color: var(--clr-accent); text-decoration: none; font-size: 0.875rem; padding: 10px 12px; border-radius: 6px; background: var(--clr-gray-50); display: block; transition: background .15s; }
    .action-row:hover { background: var(--clr-brand-light); }
    .action-section { margin-bottom: 12px; border: 1px solid var(--clr-gray-200); border-radius: 8px; padding: 0; }
    .action-section[open] { padding-bottom: 12px; }
    .action-toggle { cursor: pointer; padding: 10px 14px; font-weight: 600; font-size: 0.9rem; color: var(--clr-accent); list-style: none; }
    .action-toggle::-webkit-details-marker { display: none; }
    .action-toggle::before { content: '▸ '; }
    details[open] > .action-toggle::before { content: '▾ '; }
    .rx-lines { padding: 0 14px; display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
    .rx-line-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .rx-line-row .form-control { flex: 1; min-width: 80px; }
    .rx-actions { display: flex; gap: 8px; margin-top: 4px; }
    .btn-icon { background: none; border: none; cursor: pointer; color: var(--clr-gray-500); font-size: 1.1rem; padding: 2px 6px; }
    .btn-icon:hover { color: var(--clr-danger); }
    .btn-primary { background: var(--clr-accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  `],
})
export class EncounterDetailComponent implements OnInit {
  id = input.required<string>();
  readonly auth = inject(AuthService);
  private readonly svc = inject(EncounterService);
  private readonly fb = inject(FormBuilder);
  private readonly nameCache = inject(PatientNameCache);

  encounter = signal<Encounter | null>(null);
  loading = signal(true);
  actionError = signal('');
  patientName = signal('');
  chainResult = signal<{ is_valid: boolean; message: string; event_count: number; first_broken_sequence?: number } | null>(null);

  vitalsForm = this.fb.group({
    temperature_c: [null as number | null],
    pulse_bpm: [null as number | null],
    systolic_bp: [null as number | null],
    diastolic_bp: [null as number | null],
    oxygen_saturation: [null as number | null],
  });

  soapForm = this.fb.group({
    subjective: ['', Validators.required],
    objective: ['', Validators.required],
    assessment: ['', Validators.required],
    plan: ['', Validators.required],
  });

  dxForm = this.fb.group({
    icd10_code: ['', Validators.required],
    description: ['', Validators.required],
  });

  // Prescription lines (ngModel-bound)
  rxLines: PrescriptionLine[] = [{ drug_name: '', dose: '', route: '', frequency: '', duration_days: 0 }];

  // Lab order lines (ngModel-bound)
  labLines: LabTestLine[] = [{ test_code: '', urgency: 'routine' }];

  ngOnInit(): void { this.reload(); }

  private retryCount = 0;
  private readonly MAX_RETRIES = 5;

  reload(): void {
    this.svc.get(this.id()).subscribe({
      next: e => {
        this.retryCount = 0;
        this.encounter.set(e);
        this.loading.set(false);
        this.nameCache.resolve(e.patient_id).subscribe(n => this.patientName.set(n));
      },
      error: (err) => {
        if (err.status === 404 && this.retryCount < this.MAX_RETRIES) {
          this.retryCount++;
          timer(1000).subscribe(() => this.reload());
        } else {
          this.retryCount = 0;
          this.loading.set(false);
        }
      },
    });
  }

  saveVitals(): void {
    const v = this.vitalsForm.value;
    this.svc.recordVitals(this.id(), {
      temperature_celsius: v.temperature_c ?? undefined,
      pulse_bpm: v.pulse_bpm ?? undefined,
      systolic_bp_mmhg: v.systolic_bp ?? undefined,
      diastolic_bp_mmhg: v.diastolic_bp ?? undefined,
      oxygen_saturation_pct: v.oxygen_saturation ?? undefined,
    }).subscribe({ next: () => this.reload(), error: e => this.actionError.set(e.error?.detail ?? 'Error') });
  }

  saveSOAP(): void {
    if (this.soapForm.invalid) return;
    const v = this.soapForm.value as any;
    this.svc.recordSOAP(this.id(), v).subscribe({ next: () => this.reload(), error: e => this.actionError.set(e.error?.detail ?? 'Error') });
  }

  addDx(): void {
    if (this.dxForm.invalid) return;
    const { icd10_code, description } = this.dxForm.value as any;
    this.svc.addDiagnosis(this.id(), { icd10_code, description, is_primary: this.encounter()!.diagnoses.length === 0 })
      .subscribe({ next: () => { this.dxForm.reset(); this.reload(); }, error: e => this.actionError.set(e.error?.detail ?? 'Error') });
  }

  closeEncounter(): void {
    if (!confirm('Close and sign this encounter? This cannot be undone.')) return;
    this.svc.close(this.id()).subscribe({ next: () => this.reload(), error: e => this.actionError.set(e.error?.detail ?? 'Error') });
  }

  verifyChain(): void {
    this.svc.verifyChain(this.id()).subscribe({
      next: r => this.chainResult.set(r),
      error: () => this.actionError.set('Chain verification failed — check network or permissions'),
    });
  }

  // ── Prescription helpers ──
  addRxLine(): void { this.rxLines.push({ drug_name: '', dose: '', route: '', frequency: '', duration_days: 0 }); }
  removeRxLine(i: number): void { this.rxLines.splice(i, 1); }
  canSubmitRx(): boolean { return this.rxLines.every(l => l.drug_name && l.dose && l.route && l.frequency && l.duration_days > 0); }

  submitPrescription(): void {
    if (!this.canSubmitRx()) return;
    this.svc.issuePrescription(this.id(), { lines: this.rxLines }).subscribe({
      next: () => {
        this.rxLines = [{ drug_name: '', dose: '', route: '', frequency: '', duration_days: 0 }];
        this.actionError.set('');
        this.reload();
      },
      error: e => this.actionError.set(e.error?.detail ?? 'Failed to issue prescription'),
    });
  }

  // ── Lab order helpers ──
  addLabLine(): void { this.labLines.push({ test_code: '', urgency: 'routine' }); }
  removeLabLine(i: number): void { this.labLines.splice(i, 1); }
  canSubmitLab(): boolean { return this.labLines.every(t => t.test_code?.trim()); }

  submitLabOrder(): void {
    if (!this.canSubmitLab()) return;
    this.svc.placeLabOrder(this.id(), { tests: this.labLines }).subscribe({
      next: () => {
        this.labLines = [{ test_code: '', urgency: 'routine' }];
        this.actionError.set('');
        this.reload();
      },
      error: e => this.actionError.set(e.error?.detail ?? 'Failed to place lab order'),
    });
  }
}
