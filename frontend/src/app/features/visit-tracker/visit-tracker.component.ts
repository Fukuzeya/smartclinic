import { Component, inject, signal, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, NgTemplateOutlet, SlicePipe } from '@angular/common';
import { SagaService } from '../../shared/api/saga.service';
import { PatientVisitSaga, SagaStep } from '../../shared/models/saga.model';

const STEPS: { key: SagaStep; label: string; icon: string; desc: string }[] = [
  { key: 'awaiting_encounter', label: 'Checked In', icon: '📋', desc: 'Patient checked in; awaiting doctor' },
  { key: 'encounter_open',    label: 'In Consultation', icon: '🩺', desc: 'Encounter open with doctor' },
  { key: 'awaiting_lab',      label: 'Lab Processing', icon: '🧪', desc: 'Lab tests ordered and in progress' },
  { key: 'awaiting_payment',  label: 'Awaiting Payment', icon: '💵', desc: 'Consultation complete; invoice issued' },
  { key: 'completed',         label: 'Visit Complete', icon: '✅', desc: 'Invoice paid — visit closed' },
];

@Component({
  selector: 'app-visit-tracker',
  standalone: true,
  imports: [RouterLink, DatePipe, NgTemplateOutlet, SlicePipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Visit Tracker</h1>
      <p style="color:#64748b;margin:0;font-size:.9rem">Real-time patient journey across all departments</p>
    </div>

    @if (encounterId()) {
      <!-- Single saga view via encounter_id query param -->
      @if (loadingSingle()) {
        <div class="loading">Loading visit…</div>
      } @else if (singleSaga()) {
        <ng-container *ngTemplateOutlet="sagaTimeline; context: { saga: singleSaga() }" />
      } @else {
        <div class="empty-state">No visit found for this encounter.</div>
      }
    } @else {
      <!-- Saga list view -->
      <div class="filter-bar">
        <select class="form-control" style="width:180px" (change)="onStatusChange($any($event.target).value)">
          <option value="active">Active visits</option>
          <option value="">All</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      @if (loading()) {
        <div class="loading">Loading visits…</div>
      } @else if (sagas().length === 0) {
        <div class="empty-state">No patient visits found.</div>
      } @else {
        @for (saga of sagas(); track saga.saga_id) {
          <div class="saga-card">
            <div class="saga-header">
              <div>
                <code style="font-size:.8rem;color:#64748b">{{ saga.saga_id }}</code>
                <div style="font-size:.85rem;color:#475569;margin-top:2px">
                  Patient <code>{{ saga.patient_id | slice:0:12 }}…</code>
                  &nbsp;·&nbsp;
                  Started {{ saga.started_at | date:'dd MMM yyyy HH:mm' }}
                </div>
              </div>
              <span class="badge" [class]="sagaStatusClass(saga.status)" style="font-size:.8rem">
                {{ saga.status }}
              </span>
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
              @if (saga.context.lab_order_ids.length) {
                <a [routerLink]="['/lab-orders']"
                   [queryParams]="{encounter_id: saga.context.encounter_id}"
                   class="saga-link">
                  Lab Orders ({{ saga.context.lab_orders_completed.length }}/{{ saga.context.lab_order_ids.length }}) →
                </a>
              }
            </div>
          </div>
        }
      }
    }

    <!-- Reusable stepper row template -->
    <ng-template #stepperRow let-saga="saga">
      <div class="stepper">
        @for (step of visibleSteps(saga); track step.key; let last = $last) {
          <div class="step" [class.active]="saga.step === step.key" [class.done]="isStepDone(saga, step.key)" [class.cancelled]="saga.status === 'cancelled' && saga.step === step.key">
            <div class="step-icon-wrap">
              <div class="step-circle">{{ step.icon }}</div>
              @if (!last) { <div class="step-line"></div> }
            </div>
            <div class="step-label">{{ step.label }}</div>
            @if (saga.step === step.key && saga.status !== 'completed' && saga.status !== 'cancelled') {
              <div class="step-pulse"></div>
            }
          </div>
        }
      </div>
    </ng-template>

    <!-- Full detail timeline template -->
    <ng-template #sagaTimeline let-saga="saga">
      <div class="saga-card">
        <div class="saga-header">
          <div>
            <h2 style="font-size:1.1rem;font-weight:700;color:#1e293b;margin:0">Patient Visit</h2>
            <code style="font-size:.8rem;color:#64748b">{{ saga.saga_id }}</code>
          </div>
          <span class="badge" [class]="sagaStatusClass(saga.status)" style="font-size:.85rem;padding:6px 14px">
            {{ saga.status }}
          </span>
        </div>

        <ng-container *ngTemplateOutlet="stepperRow; context: { saga: saga }" />

        <div class="context-grid">
          <div class="context-item">
            <div class="context-label">Patient</div>
            <code>{{ saga.patient_id }}</code>
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
          @if (saga.context.lab_order_ids.length) {
            <div class="context-item">
              <div class="context-label">Lab Orders</div>
              <span>{{ saga.context.lab_orders_completed.length }} / {{ saga.context.lab_order_ids.length }} completed</span>
              <div class="lab-progress">
                <div class="lab-bar" [style.width.%]="(saga.context.lab_orders_completed.length / saga.context.lab_order_ids.length) * 100"></div>
              </div>
            </div>
          }
          <div class="context-item">
            <div class="context-label">Started</div>
            <span>{{ saga.started_at | date:'dd MMM yyyy HH:mm' }}</span>
          </div>
          @if (saga.completed_at) {
            <div class="context-item">
              <div class="context-label">Completed</div>
              <span>{{ saga.completed_at | date:'dd MMM yyyy HH:mm' }}</span>
            </div>
          }
        </div>
      </div>
    </ng-template>
  `,
  styles: [`
    .saga-card{background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.07);padding:20px;margin-bottom:16px;border:1px solid #e2e8f0}
    .saga-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}
    .saga-footer{display:flex;gap:16px;margin-top:16px;padding-top:12px;border-top:1px solid #f1f5f9}
    .saga-link{color:#6366f1;text-decoration:none;font-size:.8rem;font-weight:500}
    .saga-link:hover{text-decoration:underline}

    /* Stepper */
    .stepper{display:flex;gap:0;margin:8px 0 4px;overflow-x:auto;padding-bottom:4px}
    .step{display:flex;flex-direction:column;align-items:center;min-width:100px;position:relative}
    .step-icon-wrap{display:flex;align-items:center;width:100%}
    .step-circle{width:36px;height:36px;border-radius:50%;background:#f1f5f9;border:2px solid #e2e8f0;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;transition:all .2s;z-index:1}
    .step-line{flex:1;height:2px;background:#e2e8f0}
    .step-label{font-size:.7rem;color:#94a3b8;margin-top:6px;text-align:center;font-weight:500}
    .step.done .step-circle{background:#d1fae5;border-color:#10b981}
    .step.active .step-circle{background:#eef2ff;border-color:#6366f1;box-shadow:0 0 0 4px rgba(99,102,241,.15)}
    .step.active .step-label{color:#6366f1;font-weight:700}
    .step.done .step-label{color:#10b981}
    .step.cancelled .step-circle{background:#fee2e2;border-color:#ef4444}
    .step.done .step-line{background:#10b981}
    .step-pulse{position:absolute;top:0;left:50%;transform:translateX(-50%);width:36px;height:36px;border-radius:50%;background:rgba(99,102,241,.3);animation:pulse 1.5s infinite}
    @keyframes pulse{0%{transform:translateX(-50%) scale(1);opacity:.6}70%{transform:translateX(-50%) scale(1.5);opacity:0}100%{transform:translateX(-50%) scale(1);opacity:0}}

    /* Context grid */
    .context-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-top:16px;padding-top:12px;border-top:1px solid #f1f5f9}
    .context-item{font-size:.85rem;color:#1e293b}
    .context-label{font-size:.7rem;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}
    .lab-progress{background:#f1f5f9;border-radius:4px;height:4px;margin-top:4px;overflow:hidden}
    .lab-bar{background:#6366f1;height:100%;border-radius:4px;transition:width .3s}
  `],
})
export class VisitTrackerComponent implements OnInit {
  private readonly svc = inject(SagaService);
  private readonly route = inject(ActivatedRoute);

  sagas = signal<PatientVisitSaga[]>([]);
  singleSaga = signal<PatientVisitSaga | null>(null);
  loading = signal(true);
  loadingSingle = signal(false);
  encounterId = signal<string | null>(null);
  private statusFilter = 'active';

  readonly allSteps = STEPS;

  ngOnInit(): void {
    const eid = this.route.snapshot.queryParamMap.get('encounter_id');
    this.encounterId.set(eid);
    if (eid) {
      this.loadingSingle.set(true);
      this.svc.getByEncounter(eid).subscribe({
        next: s => { this.singleSaga.set(s); this.loadingSingle.set(false); },
        error: () => this.loadingSingle.set(false),
      });
    } else {
      this.loadList();
    }
  }

  onStatusChange(status: string): void {
    this.statusFilter = status;
    this.loadList();
  }

  private loadList(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined).subscribe({
      next: r => { this.sagas.set(r.items); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  visibleSteps(saga: PatientVisitSaga) {
    if (saga.status === 'cancelled') return STEPS.slice(0, STEPS.findIndex(s => s.key === saga.step) + 1);
    return STEPS;
  }

  isStepDone(saga: PatientVisitSaga, stepKey: SagaStep): boolean {
    const order = STEPS.map(s => s.key);
    const current = order.indexOf(saga.step);
    const target = order.indexOf(stepKey);
    return target < current || saga.status === 'completed';
  }

  sagaStatusClass(s: string): string {
    return { active: 'badge-booked', completed: 'badge-checked_in', cancelled: 'badge-cancelled' }[s] ?? '';
  }
}
