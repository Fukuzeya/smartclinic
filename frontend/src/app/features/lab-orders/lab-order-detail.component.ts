import { Component, inject, signal, input, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DatePipe, SlicePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { LabOrderService } from '../../shared/api/lab-order.service';
import { LabOrder } from '../../shared/models/lab-order.model';
import { AuthService } from '../../core/auth/auth.service';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';
import { DoctorNameCache } from '../../shared/services/doctor-name-cache.service';

const INTERPRETATION_OPTIONS = [
  'normal', 'low', 'high', 'critical_low', 'critical_high',
  'positive', 'negative', 'indeterminate',
];

@Component({
  selector: 'app-lab-order-detail',
  standalone: true,
  imports: [DatePipe, SlicePipe, ReactiveFormsModule, RouterLink],
  template: `
    @if (loading()) {
      <div class="loading">Loading…</div>
    } @else if (!order()) {
      <div class="empty-state">
        <h2>Lab order not found</h2>
        <a routerLink="/lab-orders" class="link">← Back to orders</a>
      </div>
    } @else {
      <div class="page-header">
        <div>
          <a routerLink="/lab-orders" class="back-link">← Lab Orders</a>
          <h1 class="page-title">Lab Order</h1>
          <div style="font-size:0.9rem;color:var(--clr-gray-700);font-weight:600;margin-top:2px">{{ patientName() || 'Patient' }}</div>
        </div>
        <span class="status-chip" [class]="'sc-' + order()!.status">
          {{ formatStatus(order()!.status) }}
        </span>
      </div>

      <!-- Workflow stepper -->
      <div class="stepper">
        <div class="step" [class.step-done]="stepDone(1)" [class.step-active]="stepActive(1)">
          <div class="step-dot">1</div>
          <div class="step-label">Order Received</div>
        </div>
        <div class="step-line" [class.step-line-done]="stepDone(2)"></div>
        <div class="step" [class.step-done]="stepDone(2)" [class.step-active]="stepActive(2)">
          <div class="step-dot">2</div>
          <div class="step-label">Sample Collected</div>
        </div>
        <div class="step-line" [class.step-line-done]="stepDone(3)"></div>
        <div class="step" [class.step-done]="stepDone(3)" [class.step-active]="stepActive(3)">
          <div class="step-dot">3</div>
          <div class="step-label">Results Entered</div>
        </div>
        <div class="step-line" [class.step-line-done]="stepDone(4)"></div>
        <div class="step" [class.step-done]="stepDone(4)" [class.step-active]="stepActive(4)">
          <div class="step-dot">✓</div>
          <div class="step-label">Completed</div>
        </div>
      </div>

      <div class="detail-grid">
        <!-- Left: Order info -->
        <div>
          <div class="card">
            <h3 class="card-title">Order Information</h3>
            <dl class="kv-list">
              <dt>Patient</dt><dd>{{ patientName() || order()!.patient_id }}</dd>
              <dt>Encounter</dt><dd><a [routerLink]="['/encounters', order()!.encounter_id]" class="link">{{ order()!.encounter_id | slice:0:18 }}…</a></dd>
              <dt>Ordered by</dt><dd>{{ doctorName() || (order()!.ordered_by | slice:0:12) + '…' }}</dd>
              <dt>Sample type</dt><dd>{{ order()!.sample_type ?? 'Not collected' }}</dd>
              <dt>Received</dt><dd>{{ order()!.received_at | date:'dd MMM yyyy HH:mm' }}</dd>
              @if (order()!.completed_at) {
                <dt>Completed</dt><dd>{{ order()!.completed_at | date:'dd MMM yyyy HH:mm' }}</dd>
              }
            </dl>
          </div>

          <!-- Requested tests -->
          <div class="card" style="margin-top:16px">
            <h3 class="card-title">Requested Tests</h3>
            <div class="test-list">
              @for (ln of order()!.lines; track ln.test_code) {
                <div class="test-item" [class.test-done]="hasResult(ln.test_code)">
                  <div class="test-main">
                    <code class="test-code">{{ ln.test_code }}</code>
                    <span class="urgency-badge" [class]="'urg-' + ln.urgency">{{ ln.urgency }}</span>
                    @if (hasResult(ln.test_code)) {
                      <span class="result-check">✓ Result entered</span>
                    }
                  </div>
                  @if (ln.notes) {
                    <div class="test-notes">{{ ln.notes }}</div>
                  }
                  @if (!hasResult(ln.test_code) && canEnterResults()) {
                    <button class="btn-fill-test" (click)="prefillTest(ln.test_code)">Enter result →</button>
                  }
                </div>
              }
            </div>
          </div>

          <!-- Results table -->
          @if (order()!.results.length > 0) {
            <div class="card" style="margin-top:16px">
              <h3 class="card-title">Results</h3>
              <div class="results-grid">
                @for (r of order()!.results; track r.test_code) {
                  <div class="result-card" [class.result-critical]="r.interpretation === 'critical_low' || r.interpretation === 'critical_high'">
                    <div class="result-header">
                      <code class="test-code">{{ r.test_code }}</code>
                      <span class="interp-badge" [class]="'interp-' + r.interpretation">{{ formatStatus(r.interpretation) }}</span>
                    </div>
                    <div class="result-name">{{ r.test_name }}</div>
                    <div class="result-value-row">
                      <span class="result-value">{{ r.value }}</span>
                      @if (r.unit) { <span class="result-unit">{{ r.unit }}</span> }
                    </div>
                    @if (r.notes) {
                      <div class="result-notes">{{ r.notes }}</div>
                    }
                  </div>
                }
              </div>
            </div>
          }
        </div>

        <!-- Right: Actions -->
        <div>
          <div class="card action-card" [class.action-highlight]="order()!.status !== 'completed' && order()!.status !== 'cancelled'">
            <h3 class="card-title">Lab Technician Actions</h3>

            @if (!auth.hasRole('lab_technician')) {
              <p class="muted">Read-only — actions require lab technician role.</p>
            } @else {

              <!-- Step 1: Collect Sample -->
              @if (order()!.status === 'pending') {
                <div class="action-section">
                  <div class="action-step-label">Step 1: Collect Sample</div>
                  <div style="display:flex;gap:8px;align-items:center">
                    <select class="form-control" style="flex:1" #sampleSelect>
                      <option value="blood">Blood</option>
                      <option value="urine">Urine</option>
                      <option value="stool">Stool</option>
                      <option value="sputum">Sputum</option>
                      <option value="swab">Swab</option>
                    </select>
                    <button class="btn-primary" (click)="collectSample(sampleSelect.value)">
                      Collect Sample
                    </button>
                  </div>
                </div>
              }

              <!-- Step 2: Record Results -->
              @if (order()!.status === 'sample_collected' || order()!.status === 'in_progress') {
                <div class="action-section">
                  <div class="action-step-label">
                    Step 2: Record Results
                    <span class="progress-text">{{ order()!.results.length }} / {{ order()!.lines.length }} tests</span>
                  </div>
                  <form [formGroup]="resultForm" (ngSubmit)="recordResult()" class="result-form">
                    <div class="form-row">
                      <div class="form-group" style="flex:1">
                        <label class="form-label">Test Code</label>
                        <input class="form-control" formControlName="test_code" placeholder="e.g. HBA1C" />
                      </div>
                      <div class="form-group" style="flex:1">
                        <label class="form-label">Test Name</label>
                        <input class="form-control" formControlName="test_name" placeholder="e.g. HbA1c" />
                      </div>
                    </div>
                    <div class="form-row">
                      <div class="form-group" style="flex:2">
                        <label class="form-label">Result Value</label>
                        <input class="form-control" formControlName="value" placeholder="Result value" />
                      </div>
                      <div class="form-group" style="flex:1">
                        <label class="form-label">Unit</label>
                        <input class="form-control" formControlName="unit" placeholder="e.g. mmol/L" />
                      </div>
                    </div>
                    <div class="form-row">
                      <div class="form-group" style="flex:1">
                        <label class="form-label">Ref Range Lower</label>
                        <input class="form-control" formControlName="reference_range_lower" placeholder="Optional" />
                      </div>
                      <div class="form-group" style="flex:1">
                        <label class="form-label">Ref Range Upper</label>
                        <input class="form-control" formControlName="reference_range_upper" placeholder="Optional" />
                      </div>
                    </div>
                    <div class="form-group">
                      <label class="form-label">Interpretation</label>
                      <select class="form-control" formControlName="interpretation">
                        @for (opt of interpretations; track opt) {
                          <option [value]="opt">{{ formatStatus(opt) }}</option>
                        }
                      </select>
                    </div>
                    <div class="form-group">
                      <label class="form-label">Notes</label>
                      <input class="form-control" formControlName="notes" placeholder="Optional clinical notes" />
                    </div>
                    <button type="submit" class="btn-primary" style="width:100%">Save Result</button>
                  </form>
                </div>

                <!-- Step 3: Complete -->
                <div class="action-section" style="margin-top:16px">
                  <div class="action-step-label">Step 3: Complete & Publish</div>
                  <button class="btn-success" style="width:100%"
                          [disabled]="order()!.results.length === 0"
                          (click)="complete()">
                    ✓ Mark Complete & Publish Results
                  </button>
                  @if (order()!.results.length === 0) {
                    <div class="hint">Enter at least one result before completing.</div>
                  }
                </div>
              }

              <!-- Completed/Cancelled state -->
              @if (order()!.status === 'completed') {
                <div class="completed-banner">
                  <div class="completed-icon">✓</div>
                  <div>Order completed and results published.</div>
                </div>
              }
              @if (order()!.status === 'cancelled') {
                <div class="cancelled-banner">Order was cancelled.</div>
              }

              <!-- Cancel button -->
              @if (order()!.status !== 'cancelled' && order()!.status !== 'completed') {
                <button class="btn-danger" style="margin-top:16px;width:100%" (click)="cancel()">Cancel Order</button>
              }
            }

            @if (actionError()) { <div class="alert-error" style="margin-top:12px">{{ actionError() }}</div> }
            @if (actionSuccess()) { <div class="alert-success" style="margin-top:12px">{{ actionSuccess() }}</div> }
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .back-link { font-size: .8rem; color: var(--clr-brand); text-decoration: none; }
    .back-link:hover { text-decoration: underline; }

    .status-chip { padding: 6px 16px; border-radius: 16px; font-size: .85rem; font-weight: 600; }
    .sc-pending { background: #fef3c7; color: #92400e; }
    .sc-sample_collected { background: #dbeafe; color: #1e40af; }
    .sc-in_progress { background: #e0e7ff; color: #3730a3; }
    .sc-completed { background: #d1fae5; color: #065f46; }
    .sc-cancelled { background: #f1f5f9; color: #475569; }

    /* Stepper */
    .stepper { display: flex; align-items: center; justify-content: center; gap: 0; margin-bottom: 24px; padding: 16px; background: #fff; border-radius: 8px; border: 1px solid var(--clr-gray-100); }
    .step { display: flex; flex-direction: column; align-items: center; gap: 6px; }
    .step-dot { width: 32px; height: 32px; border-radius: 50%; background: var(--clr-gray-200); color: var(--clr-gray-500); display: flex; align-items: center; justify-content: center; font-size: .8rem; font-weight: 700; transition: all .2s; }
    .step-label { font-size: .72rem; color: var(--clr-gray-500); font-weight: 500; white-space: nowrap; }
    .step-active .step-dot { background: var(--clr-brand); color: #fff; box-shadow: 0 0 0 4px rgba(59,130,246,.2); }
    .step-active .step-label { color: var(--clr-brand); font-weight: 700; }
    .step-done .step-dot { background: #10b981; color: #fff; }
    .step-done .step-label { color: #059669; }
    .step-line { flex: 1; height: 2px; background: var(--clr-gray-200); margin: 0 8px; margin-bottom: 20px; }
    .step-line-done { background: #10b981; }

    .detail-grid { display: grid; grid-template-columns: 1fr 380px; gap: 16px; align-items: start; }
    @media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }
    .card-title { font-weight: 600; color: var(--clr-gray-700); margin-bottom: 12px; font-size: .95rem; }
    .kv-list { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; font-size: .875rem; }
    .kv-list dt { color: var(--clr-gray-500); font-weight: 500; }
    .kv-list dd { margin: 0; color: var(--clr-gray-800); }
    .link { color: var(--clr-accent); text-decoration: none; }
    .link:hover { text-decoration: underline; }
    .muted { color: var(--clr-gray-400); font-size: .875rem; }

    /* Test list */
    .test-list { display: flex; flex-direction: column; gap: 0; }
    .test-item { padding: 10px 0; border-bottom: 1px solid #f1f5f9; display: flex; flex-direction: column; gap: 4px; }
    .test-item:last-child { border-bottom: none; }
    .test-main { display: flex; align-items: center; gap: 8px; }
    .test-code { font-size: .85rem; font-weight: 700; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; }
    .test-done .test-code { background: #d1fae5; color: #065f46; }
    .urgency-badge { font-size: .68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }
    .urg-routine { background: #f1f5f9; color: #64748b; }
    .urg-urgent { background: #fef3c7; color: #92400e; }
    .urg-stat { background: #fee2e2; color: #991b1b; }
    .result-check { font-size: .75rem; color: #10b981; font-weight: 600; }
    .test-notes { font-size: .8rem; color: var(--clr-gray-500); padding-left: 4px; }
    .btn-fill-test { font-size: .75rem; color: var(--clr-brand); background: none; border: none; cursor: pointer; padding: 2px 0; text-decoration: underline; align-self: flex-start; }

    /* Results grid */
    .results-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
    .result-card { border: 1px solid var(--clr-gray-200); border-radius: 8px; padding: 12px; }
    .result-critical { border-color: #fca5a5; background: #fef2f2; }
    .result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .result-name { font-size: .8rem; color: var(--clr-gray-500); margin-bottom: 8px; }
    .result-value-row { display: flex; align-items: baseline; gap: 4px; }
    .result-value { font-size: 1.3rem; font-weight: 700; color: var(--clr-gray-800); }
    .result-unit { font-size: .8rem; color: var(--clr-gray-500); }
    .result-notes { font-size: .75rem; color: var(--clr-gray-500); margin-top: 6px; font-style: italic; }
    .interp-badge { font-size: .68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; }
    .interp-normal, .interp-negative { background: #d1fae5; color: #065f46; }
    .interp-low, .interp-high { background: #fef3c7; color: #92400e; }
    .interp-critical_low, .interp-critical_high { background: #fee2e2; color: #991b1b; }
    .interp-positive, .interp-indeterminate { background: #e0e7ff; color: #3730a3; }

    /* Action panel */
    .action-card { position: sticky; top: calc(var(--header-h) + 16px); }
    .action-highlight { border: 2px solid var(--clr-accent); }
    .action-section { padding: 12px; background: var(--clr-gray-50); border-radius: 8px; }
    .action-step-label { font-size: .8rem; font-weight: 700; color: var(--clr-gray-600); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
    .progress-text { font-size: .75rem; color: var(--clr-brand); }
    .result-form { display: flex; flex-direction: column; gap: 8px; }
    .form-row { display: flex; gap: 8px; }
    .form-group { display: flex; flex-direction: column; gap: 3px; }
    .form-label { font-size: .7rem; font-weight: 600; color: var(--clr-gray-500); text-transform: uppercase; letter-spacing: .04em; }
    .hint { font-size: .75rem; color: var(--clr-gray-400); margin-top: 4px; }
    .btn-success { background: #10b981; color: #fff; border: none; padding: 10px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: .85rem; }
    .btn-success:hover { background: #059669; }
    .btn-success:disabled { opacity: .5; cursor: not-allowed; }
    .completed-banner { display: flex; align-items: center; gap: 10px; padding: 16px; background: #d1fae5; border-radius: 8px; color: #065f46; font-weight: 600; font-size: .9rem; }
    .completed-icon { width: 32px; height: 32px; background: #10b981; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1rem; flex-shrink: 0; }
    .cancelled-banner { padding: 16px; background: #f1f5f9; border-radius: 8px; color: #475569; font-weight: 600; font-size: .9rem; text-align: center; }
  `],
})
export class LabOrderDetailComponent implements OnInit {
  id = input.required<string>();
  readonly auth = inject(AuthService);
  private readonly svc = inject(LabOrderService);
  private readonly fb = inject(FormBuilder);
  private readonly nameCache = inject(PatientNameCache);
  private readonly doctorCache = inject(DoctorNameCache);

  order = signal<LabOrder | null>(null);
  loading = signal(true);
  actionError = signal('');
  actionSuccess = signal('');
  patientName = signal('');
  doctorName = signal('');
  interpretations = INTERPRETATION_OPTIONS;

  resultForm = this.fb.group({
    test_code: ['', Validators.required],
    test_name: ['', Validators.required],
    value: ['', Validators.required],
    unit: [''],
    reference_range_lower: [''],
    reference_range_upper: [''],
    interpretation: ['normal', Validators.required],
    notes: [''],
  });

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.actionError.set('');
    this.svc.get(this.id()).subscribe({
      next: o => {
        this.order.set(o);
        this.loading.set(false);
        this.nameCache.resolve(o.patient_id).subscribe(n => this.patientName.set(n));
        this.doctorCache.resolve(o.ordered_by).subscribe(n => this.doctorName.set(n));
      },
      error: () => this.loading.set(false),
    });
  }

  formatStatus(s: string): string { return s.replace(/_/g, ' '); }

  canEnterResults(): boolean {
    const s = this.order()?.status;
    return (s === 'sample_collected' || s === 'in_progress') && this.auth.hasRole('lab_technician');
  }

  hasResult(testCode: string): boolean {
    return !!this.order()?.results.some(r => r.test_code === testCode);
  }

  prefillTest(testCode: string): void {
    this.resultForm.patchValue({ test_code: testCode, test_name: testCode });
  }

  // Stepper logic
  private get stepIndex(): number {
    const s = this.order()?.status;
    if (s === 'pending') return 1;
    if (s === 'sample_collected') return 2;
    if (s === 'in_progress') return 3;
    if (s === 'completed') return 4;
    return 0;
  }
  stepDone(n: number): boolean { return this.stepIndex >= n; }
  stepActive(n: number): boolean { return this.stepIndex === n; }

  collectSample(sampleType: string): void {
    this.actionError.set(''); this.actionSuccess.set('');
    this.svc.collectSample(this.id(), sampleType).subscribe({
      next: () => { this.actionSuccess.set('Sample collected successfully.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error collecting sample'),
    });
  }

  recordResult(): void {
    if (this.resultForm.invalid) return;
    this.actionError.set(''); this.actionSuccess.set('');
    const v = this.resultForm.value as any;
    this.svc.recordResult(this.id(), {
      test_code: v.test_code, test_name: v.test_name,
      value: v.value, unit: v.unit || undefined,
      reference_range_lower: v.reference_range_lower || undefined,
      reference_range_upper: v.reference_range_upper || undefined,
      interpretation: v.interpretation, notes: v.notes || undefined,
    }).subscribe({
      next: () => { this.resultForm.reset({ interpretation: 'normal' }); this.actionSuccess.set('Result recorded.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error recording result'),
    });
  }

  complete(): void {
    if (!confirm('Mark this order as completed and publish results to the doctor?')) return;
    this.actionError.set(''); this.actionSuccess.set('');
    this.svc.complete(this.id()).subscribe({
      next: () => { this.actionSuccess.set('Order completed — results published.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error completing order'),
    });
  }

  cancel(): void {
    const reason = prompt('Reason for cancellation:');
    if (!reason) return;
    this.actionError.set(''); this.actionSuccess.set('');
    this.svc.cancel(this.id(), reason).subscribe({
      next: () => { this.actionSuccess.set('Order cancelled.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error cancelling order'),
    });
  }
}
