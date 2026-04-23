import { Component, inject, signal, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, NgTemplateOutlet, SlicePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SagaService } from '../../shared/api/saga.service';
import { PatientVisitSaga, SagaStep } from '../../shared/models/saga.model';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';

const STEPS: { key: SagaStep; label: string; icon: string }[] = [
  { key: 'awaiting_encounter',    label: 'Checked In',          icon: '📋' },
  { key: 'encounter_open',        label: 'In Consultation',     icon: '🩺' },
  { key: 'awaiting_lab',          label: 'Lab Processing',      icon: '🧪' },
  { key: 'substitution_required', label: 'Substitution Needed', icon: '⚠️' },
  { key: 'awaiting_payment',      label: 'Awaiting Payment',    icon: '💵' },
  { key: 'completed',             label: 'Visit Complete',      icon: '✅' },
];

const STEP_ORDER = STEPS.map(s => s.key);

@Component({
  selector: 'app-visit-tracker',
  standalone: true,
  imports: [RouterLink, DatePipe, NgTemplateOutlet, SlicePipe, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Visit Tracker</h1>
        <p class="page-subtitle">Real-time patient journey across all departments</p>
      </div>
      @if (!encounterId()) {
        <div class="header-meta">{{ sagas().length }} visit{{ sagas().length !== 1 ? 's' : '' }}</div>
      }
    </div>

    @if (encounterId()) {
      <!-- Single saga detail view via encounter_id query param -->
      @if (loadingSingle()) {
        <div class="loading">Loading visit…</div>
      } @else if (singleSaga()) {
        <ng-container *ngTemplateOutlet="sagaDetail; context: { saga: singleSaga() }" />
      } @else {
        <div class="empty-state">No visit found for this encounter.</div>
      }
    } @else {
      <!-- List view with filters -->
      <div class="filter-bar">
        <div class="filter-group">
          <label class="filter-label" for="status-filter">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 3H2l8 9.46V19l4 2V12.46L22 3z"/></svg>
            Status
          </label>
          <select id="status-filter" class="form-control filter-select"
                  [(ngModel)]="statusFilter" (ngModelChange)="loadList()">
            <option value="active">Active visits</option>
            <option value="">All visits</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div class="status-chips">
          @for (step of STEPS; track step.key) {
            <button type="button"
                    [class]="'chip' + (stepFilter === step.key ? ' chip-active' : '')"
                    (click)="toggleStepFilter(step.key)">
              {{ step.icon }} {{ step.label }}
            </button>
          }
        </div>
      </div>

      @if (loading()) {
        <div class="loading">Loading visits…</div>
      } @else if (filteredSagas().length === 0) {
        <div class="empty-state">
          <strong>No patient visits found</strong>
          <p>Try adjusting the filters above.</p>
        </div>
      } @else {
        @for (saga of filteredSagas(); track saga.saga_id) {
          <div class="saga-card">
            <div class="saga-header">
              <div class="saga-identity">
                <div class="saga-patient">
                  Patient <strong>{{ patientNames()[saga.patient_id] || '…' }}</strong>
                </div>
                <div class="saga-meta">
                  <span>Started {{ saga.started_at | date:'dd MMM HH:mm' }}</span>
                  @if (saga.completed_at) {
                    <span>· Ended {{ saga.completed_at | date:'dd MMM HH:mm' }}</span>
                  }
                </div>
              </div>
              <div class="saga-badges">
                <span class="badge" [class]="sagaStatusClass(saga.status)">{{ sagaStatusLabel(saga.status) }}</span>
                <span class="step-badge">{{ currentStepLabel(saga) }}</span>
              </div>
            </div>

            <ng-container *ngTemplateOutlet="stepperRow; context: { saga: saga }" />

            <div class="saga-footer">
              @if (saga.context.encounter_id) {
                <a [routerLink]="['/encounters', saga.context.encounter_id]" class="saga-link">
                  View Encounter →
                </a>
              }
              @if (saga.context.invoice_id) {
                <a [routerLink]="['/invoices', saga.context.invoice_id]" class="saga-link">
                  View Invoice →
                </a>
              }
              @if ((saga.context.lab_order_ids ?? []).length > 0) {
                <span class="saga-link">
                  Lab: {{ (saga.context.lab_orders_completed ?? []).length }}/{{ saga.context.lab_order_ids.length }} done
                </span>
              }
            </div>
          </div>
        }
      }
    }

    <!-- Stepper row template -->
    <ng-template #stepperRow let-saga="saga">
      <div class="stepper">
        @for (step of STEPS; track step.key; let last = $last) {
          <div class="step"
               [class.active]="isActiveStep(saga, step.key)"
               [class.done]="isStepDone(saga, step.key)"
               [class.cancelled]="saga.status === 'cancelled' && isActiveStep(saga, step.key)">
            <div class="step-icon-wrap">
              <div class="step-circle">{{ step.icon }}</div>
              @if (!last) { <div class="step-line" [class.done-line]="isStepDone(saga, step.key)"></div> }
            </div>
            <div class="step-label">{{ step.label }}</div>
            @if (isActiveStep(saga, step.key) && saga.status === 'active') {
              <div class="step-pulse"></div>
            }
          </div>
        }
      </div>
    </ng-template>

    <!-- Full detail template -->
    <ng-template #sagaDetail let-saga="saga">
      <div class="saga-card">
        <div class="saga-header">
          <div>
            <h2 class="detail-title">Patient Visit</h2>
            <code class="saga-id-code">{{ saga.saga_id }}</code>
          </div>
          <span class="badge" [class]="sagaStatusClass(saga.status)" style="font-size:.85rem;padding:6px 14px">
            {{ sagaStatusLabel(saga.status) }}
          </span>
        </div>

        <ng-container *ngTemplateOutlet="stepperRow; context: { saga: saga }" />

        <div class="context-grid">
          <div class="context-item">
            <div class="context-label">Patient</div>
            <span>{{ patientNames()[saga.patient_id] || saga.patient_id }}</span>
          </div>
          @if (saga.context.encounter_id) {
            <div class="context-item">
              <div class="context-label">Encounter</div>
              <a [routerLink]="['/encounters', saga.context.encounter_id]" class="saga-link">
                {{ saga.context.encounter_id | slice:0:16 }}… →
              </a>
            </div>
          }
          @if (saga.context.invoice_id) {
            <div class="context-item">
              <div class="context-label">Invoice</div>
              <a [routerLink]="['/invoices', saga.context.invoice_id]" class="saga-link">
                {{ saga.context.invoice_id | slice:0:16 }}… →
              </a>
            </div>
          }
          @if ((saga.context.lab_order_ids ?? []).length > 0) {
            <div class="context-item">
              <div class="context-label">Lab Orders</div>
              <span>{{ (saga.context.lab_orders_completed ?? []).length }} / {{ saga.context.lab_order_ids.length }} completed</span>
              <div class="lab-progress">
                <div class="lab-bar"
                     [style.width.%]="((saga.context.lab_orders_completed ?? []).length / saga.context.lab_order_ids.length) * 100">
                </div>
              </div>
            </div>
          }
          <div class="context-item">
            <div class="context-label">Started</div>
            <span>{{ saga.started_at | date:'dd MMM yyyy HH:mm' }}</span>
          </div>
          @if (saga.completed_at) {
            <div class="context-item">
              <div class="context-label">Closed</div>
              <span>{{ saga.completed_at | date:'dd MMM yyyy HH:mm' }}</span>
            </div>
          }
        </div>
      </div>
    </ng-template>
  `,
  styles: [`
    .page-subtitle { color: var(--clr-gray-500); margin: 0; font-size: .9rem; }
    .header-meta { font-size: .8rem; color: var(--clr-gray-400); }

    /* Filter bar */
    .filter-bar {
      display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 20px;
    }
    .filter-group { display: flex; align-items: center; gap: 8px; }
    .filter-label {
      display: flex; align-items: center; gap: 5px;
      font-size: .8rem; font-weight: 600; color: var(--clr-gray-600); white-space: nowrap;
    }
    .filter-select { width: 160px; }
    .status-chips { display: flex; gap: 6px; flex-wrap: wrap; }
    .chip {
      padding: 3px 10px; border-radius: 20px;
      border: 1px solid var(--clr-gray-200); background: var(--clr-surface);
      font-size: .75rem; font-weight: 500; color: var(--clr-gray-600);
      cursor: pointer; transition: all .15s; white-space: nowrap;
      &:hover { border-color: var(--clr-brand); color: var(--clr-brand); }
    }
    .chip-active { border-color: var(--clr-brand); color: var(--clr-brand); background: var(--clr-brand-light); font-weight: 700; }

    /* Cards */
    .saga-card {
      background: var(--clr-surface);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-sm);
      padding: 22px;
      margin-bottom: 16px;
      border: 1px solid var(--clr-gray-100);
    }
    .saga-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; gap: 12px; }
    .saga-identity { }
    .saga-patient { font-size: .9rem; font-weight: 600; color: var(--clr-gray-800); }
    .saga-meta { font-size: .78rem; color: var(--clr-gray-500); margin-top: 3px; }
    .saga-badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .step-badge {
      font-size: .72rem; font-weight: 600; color: var(--clr-gray-500);
      background: var(--clr-gray-100); padding: 3px 10px; border-radius: 20px;
    }
    .saga-footer { display: flex; gap: 16px; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--clr-gray-100); flex-wrap: wrap; }
    .saga-link { color: var(--clr-accent); text-decoration: none; font-size: .8rem; font-weight: 500; &:hover { text-decoration: underline; } }

    /* Detail */
    .detail-title { font-size: 1.1rem; font-weight: 700; color: var(--clr-gray-900); margin: 0; }
    .saga-id-code { font-size: .78rem; color: var(--clr-gray-400); }

    /* Stepper */
    .stepper { display: flex; gap: 0; margin: 6px 0 4px; overflow-x: auto; padding-bottom: 4px; }
    .step { display: flex; flex-direction: column; align-items: center; min-width: 90px; position: relative; }
    .step-icon-wrap { display: flex; align-items: center; width: 100%; }
    .step-circle {
      width: 34px; height: 34px; border-radius: 50%;
      background: var(--clr-gray-100); border: 2px solid var(--clr-gray-200);
      display: flex; align-items: center; justify-content: center; font-size: .95rem;
      flex-shrink: 0; transition: all .2s; z-index: 1;
    }
    .step-line { flex: 1; height: 2px; background: var(--clr-gray-200); }
    .done-line { background: #10b981; }
    .step-label { font-size: .67rem; color: var(--clr-gray-400); margin-top: 6px; text-align: center; font-weight: 500; line-height: 1.2; }

    .step.done .step-circle  { background: #d1fae5; border-color: #10b981; }
    .step.done .step-label   { color: #10b981; }
    .step.active .step-circle { background: var(--clr-brand-light); border-color: var(--clr-brand); box-shadow: 0 0 0 4px rgba(18,85,161,.12); }
    .step.active .step-label  { color: var(--clr-brand); font-weight: 700; }
    .step.cancelled .step-circle { background: #fee2e2; border-color: #ef4444; }
    .step.cancelled .step-label  { color: #ef4444; font-weight: 700; }

    .step-pulse {
      position: absolute; top: 0; left: 50%; transform: translateX(-50%);
      width: 34px; height: 34px; border-radius: 50%;
      background: rgba(18,85,161,.25); animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0%   { transform: translateX(-50%) scale(1); opacity: .6; }
      70%  { transform: translateX(-50%) scale(1.6); opacity: 0; }
      100% { transform: translateX(-50%) scale(1); opacity: 0; }
    }

    /* Context grid */
    .context-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--clr-gray-100); }
    .context-item { font-size: .85rem; color: var(--clr-gray-800); }
    .context-label { font-size: .68rem; color: var(--clr-gray-400); font-weight: 600; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 2px; }
    .lab-progress { background: var(--clr-gray-100); border-radius: 4px; height: 4px; margin-top: 4px; overflow: hidden; }
    .lab-bar { background: var(--clr-brand); height: 100%; border-radius: 4px; transition: width .3s; }
  `],
})
export class VisitTrackerComponent implements OnInit {
  private readonly svc = inject(SagaService);
  private readonly route = inject(ActivatedRoute);
  private readonly nameCache = inject(PatientNameCache);

  readonly STEPS = STEPS;

  sagas = signal<PatientVisitSaga[]>([]);
  singleSaga = signal<PatientVisitSaga | null>(null);
  loading = signal(true);
  loadingSingle = signal(false);
  encounterId = signal<string | null>(null);
  patientNames = signal<Record<string, string>>({});

  statusFilter = 'active';
  stepFilter: SagaStep | '' = '';

  ngOnInit(): void {
    const eid = this.route.snapshot.queryParamMap.get('encounter_id');
    this.encounterId.set(eid);
    if (eid) {
      this.loadingSingle.set(true);
      this.svc.getByEncounter(eid).subscribe({
        next: s => {
          this.singleSaga.set(s);
          this.loadingSingle.set(false);
          this.nameCache.resolve(s.patient_id).subscribe(n => this.patientNames.set({ [s.patient_id]: n }));
        },
        error: () => this.loadingSingle.set(false),
      });
    } else {
      this.loadList();
    }
  }

  loadList(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined).subscribe({
      next: r => {
        this.sagas.set(r.items);
        this.loading.set(false);
        const ids = r.items.map(s => s.patient_id);
        if (ids.length) this.nameCache.resolveMany(ids).subscribe(m => this.patientNames.set(m));
      },
      error: () => this.loading.set(false),
    });
  }

  toggleStepFilter(key: SagaStep): void {
    this.stepFilter = this.stepFilter === key ? '' : key;
  }

  filteredSagas(): PatientVisitSaga[] {
    if (!this.stepFilter) return this.sagas();
    return this.sagas().filter(s => this.resolvedStep(s) === this.stepFilter);
  }

  /** The display step: for cancelled/completed, return the last non-terminal step if available */
  resolvedStep(saga: PatientVisitSaga): SagaStep {
    if (saga.step === 'cancelled') {
      // Infer last position from context
      if (saga.context.invoice_id) return 'awaiting_payment';
      if ((saga.context.lab_order_ids ?? []).length > 0) return 'awaiting_lab';
      if (saga.context.encounter_id) return 'encounter_open';
      return 'awaiting_encounter';
    }
    return saga.step;
  }

  isActiveStep(saga: PatientVisitSaga, stepKey: SagaStep): boolean {
    if (saga.step === stepKey) return true;
    if (saga.step === 'cancelled') return this.resolvedStep(saga) === stepKey;
    return false;
  }

  isStepDone(saga: PatientVisitSaga, stepKey: SagaStep): boolean {
    if (saga.status === 'completed') return true;
    const effectiveStep = saga.step === 'cancelled' ? this.resolvedStep(saga) : saga.step;
    const current = STEP_ORDER.indexOf(effectiveStep);
    const target = STEP_ORDER.indexOf(stepKey);
    return target >= 0 && current >= 0 && target < current;
  }

  currentStepLabel(saga: PatientVisitSaga): string {
    if (saga.status === 'cancelled') return '✕ Cancelled';
    if (saga.status === 'completed') return '✓ Completed';
    const step = STEPS.find(s => s.key === saga.step);
    return step ? `${step.icon} ${step.label}` : saga.step;
  }

  sagaStatusClass(s: string): string {
    return { active: 'badge-booked', completed: 'badge-checked_in', cancelled: 'badge-cancelled' }[s] ?? '';
  }

  sagaStatusLabel(s: string): string {
    return { active: 'Active', completed: 'Completed', cancelled: 'Cancelled' }[s] ?? s;
  }
}
