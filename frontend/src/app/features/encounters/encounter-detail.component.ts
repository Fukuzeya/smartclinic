import { Component, inject, signal, input, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EncounterService } from '../../shared/api/encounter.service';
import { Encounter } from '../../shared/models/encounter.model';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-encounter-detail',
  standalone: true,
  imports: [RouterLink, ReactiveFormsModule],
  template: `
    @if (loading()) {
      <div class="loading">Loading encounter…</div>
    } @else if (encounter()) {
      <div class="page-header">
        <div>
          <h1 class="page-title">Encounter</h1>
          <code style="font-size:0.85rem;color:#64748b">{{ encounter()!.encounter_id }}</code>
        </div>
        <span class="badge" [class]="'badge-' + encounter()!.status" style="font-size:0.9rem;padding:6px 14px">
          {{ encounter()!.status }}
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

          @if (encounter()!.status === 'open' && auth.isDoctor()) {
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

          @if (encounter()!.status === 'open' && auth.isDoctor()) {
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

          @if (encounter()!.status === 'open' && auth.isDoctor()) {
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
          <div class="action-list">
            <a [routerLink]="['/lab-orders']" [queryParams]="{encounter_id: encounter()!.encounter_id}" class="action-row">
              🧪 View Lab Orders for this encounter
            </a>
            <a [routerLink]="['/invoices']" [queryParams]="{encounter_id: encounter()!.encounter_id}" class="action-row">
              💵 View Invoice
            </a>
            <a [routerLink]="['/visit-tracker']" [queryParams]="{encounter_id: encounter()!.encounter_id}" class="action-row">
              🗺️ Visit Tracker
            </a>
          </div>

          @if (encounter()!.status === 'open' && auth.isDoctor()) {
            <button class="btn-danger" style="margin-top:16px" (click)="closeEncounter()">
              Close & Sign Encounter
            </button>
          }

          @if (chainResult()) {
            <div [class]="chainResult()!.valid ? 'alert-success' : 'alert-error'" style="margin-top:12px">
              {{ chainResult()!.valid ? '✓ Event chain intact — no tampering detected' : '⚠ Chain break at event ' + chainResult()!.tampered_at }}
            </div>
          }
          <button class="btn-secondary btn-sm" style="margin-top:8px" (click)="verifyChain()">🔒 Verify audit chain</button>

          @if (actionError()) { <div class="alert-error" style="margin-top:8px">{{ actionError() }}</div> }
        </div>
      </div>
    }
  `,
  styles: [`
    .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 768px) { .detail-grid { grid-template-columns: 1fr; } }
    .card-title { font-weight: 600; color: #334155; margin-bottom: 12px; font-size: 0.95rem; }
    .kv-list { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; font-size: 0.875rem; }
    .kv-list dt { color: #64748b; font-weight: 500; }
    .kv-list dd { margin: 0; }
    .muted { color: #94a3b8; font-size: 0.875rem; }
    .inline-form { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
    .form-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .form-row .form-control { flex: 1; min-width: 80px; }
    .btn-sm { padding: 6px 14px; font-size: 0.8rem; }
    .dx-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; font-size: 0.875rem; }
    .icd-code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin-right: 8px; }
    .action-list { display: flex; flex-direction: column; gap: 8px; }
    .action-row { color: #6366f1; text-decoration: none; font-size: 0.875rem; padding: 8px; border-radius: 6px; background: #f8fafc; display: block; }
    .action-row:hover { background: #eef2ff; }
  `],
})
export class EncounterDetailComponent implements OnInit {
  id = input.required<string>();
  readonly auth = inject(AuthService);
  private readonly svc = inject(EncounterService);
  private readonly fb = inject(FormBuilder);

  encounter = signal<Encounter | null>(null);
  loading = signal(true);
  actionError = signal('');
  chainResult = signal<{ valid: boolean; tampered_at?: number } | null>(null);

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

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.svc.get(this.id()).subscribe({
      next: e => { this.encounter.set(e); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  saveVitals(): void {
    const v = this.vitalsForm.value;
    this.svc.recordVitals(this.id(), {
      temperature_c: v.temperature_c ?? undefined,
      pulse_bpm: v.pulse_bpm ?? undefined,
      systolic_bp: v.systolic_bp ?? undefined,
      diastolic_bp: v.diastolic_bp ?? undefined,
      oxygen_saturation: v.oxygen_saturation ?? undefined,
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
      error: () => this.actionError.set('Chain verification failed'),
    });
  }
}
