import { Component, inject, signal, input, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DatePipe, SlicePipe } from '@angular/common';
import { LabOrderService } from '../../shared/api/lab-order.service';
import { LabOrder } from '../../shared/models/lab-order.model';
import { AuthService } from '../../core/auth/auth.service';

const INTERPRETATION_OPTIONS = [
  'normal', 'low', 'high', 'critical_low', 'critical_high',
  'positive', 'negative', 'indeterminate',
];

@Component({
  selector: 'app-lab-order-detail',
  standalone: true,
  imports: [DatePipe, SlicePipe, ReactiveFormsModule],
  template: `
    @if (loading()) {
      <div class="loading">Loading…</div>
    } @else if (order()) {
      <div class="page-header">
        <div>
          <h1 class="page-title">Lab Order</h1>
          <code style="font-size:.85rem;color:#64748b">{{ order()!.order_id }}</code>
        </div>
        <span class="badge" [class]="statusClass(order()!.status)" style="font-size:.9rem;padding:6px 14px">
          {{ order()!.status.replace('_', ' ') }}
        </span>
      </div>

      <div class="detail-grid">
        <!-- Order info -->
        <div class="card">
          <h3 class="card-title">Order Information</h3>
          <dl class="kv-list">
            <dt>Patient</dt><dd><code>{{ order()!.patient_id }}</code></dd>
            <dt>Encounter</dt><dd><code>{{ order()!.encounter_id }}</code></dd>
            <dt>Ordered by</dt><dd>{{ order()!.ordered_by }}</dd>
            <dt>Sample type</dt><dd>{{ order()!.sample_type ?? '—' }}</dd>
            <dt>Received</dt><dd>{{ order()!.received_at | date:'dd MMM yyyy HH:mm' }}</dd>
            @if (order()!.completed_at) {
              <dt>Completed</dt><dd>{{ order()!.completed_at | date:'dd MMM yyyy HH:mm' }}</dd>
            }
          </dl>

          <h4 style="margin-top:16px;font-size:.85rem;color:#64748b;font-weight:600">REQUESTED TESTS</h4>
          <ul style="padding:0;list-style:none;font-size:.875rem">
            @for (ln of order()!.lines; track ln.test_code) {
              <li style="padding:6px 0;border-bottom:1px solid #f1f5f9">
                <code>{{ ln.test_code }}</code>
                <span class="badge badge-booked" style="font-size:.7rem;margin-left:8px">{{ ln.urgency }}</span>
                @if (ln.notes) { <span style="color:#64748b;font-size:.8rem;margin-left:8px">{{ ln.notes }}</span> }
              </li>
            }
          </ul>
        </div>

        <!-- Actions & Results -->
        <div class="card">
          <h3 class="card-title">Actions</h3>

          @if (order()!.status === 'pending' && auth.hasRole('lab_technician')) {
            <div class="form-group">
              <label>Collect Sample</label>
              <div style="display:flex;gap:8px;align-items:center">
                <select class="form-control" style="flex:1" #sampleSelect>
                  <option value="blood">Blood</option>
                  <option value="urine">Urine</option>
                  <option value="stool">Stool</option>
                  <option value="sputum">Sputum</option>
                  <option value="swab">Swab</option>
                </select>
                <button class="btn-primary" (click)="collectSample(sampleSelect.value)">Collect</button>
              </div>
            </div>
          }

          @if ((order()!.status === 'sample_collected' || order()!.status === 'in_progress') && auth.hasRole('lab_technician')) {
            <form [formGroup]="resultForm" (ngSubmit)="recordResult()" class="inline-form">
              <h4 class="card-title" style="margin-top:4px">Record Result</h4>
              <div class="form-row">
                <input class="form-control" formControlName="test_code" placeholder="Test code" />
                <input class="form-control" formControlName="test_name" placeholder="Test name" />
              </div>
              <div class="form-row">
                <input class="form-control" formControlName="value" placeholder="Value" />
                <input class="form-control" formControlName="unit" placeholder="Unit (optional)" />
              </div>
              <select class="form-control" formControlName="interpretation">
                @for (opt of interpretations; track opt) {
                  <option [value]="opt">{{ opt.replace('_', ' ') }}</option>
                }
              </select>
              <input class="form-control" formControlName="notes" placeholder="Notes (optional)" />
              <button type="submit" class="btn-primary btn-sm">Save Result</button>
            </form>

            <button class="btn-secondary" style="margin-top:12px" (click)="complete()">
              ✓ Mark Complete & Publish Results
            </button>
          }

          @if (order()!.status !== 'cancelled' && order()!.status !== 'completed' && auth.hasRole('lab_technician')) {
            <button class="btn-danger" style="margin-top:8px" (click)="cancel()">Cancel Order</button>
          }

          @if (actionError()) { <div class="alert-error" style="margin-top:8px">{{ actionError() }}</div> }
          @if (actionSuccess()) { <div class="alert-success" style="margin-top:8px">{{ actionSuccess() }}</div> }
        </div>
      </div>

      <!-- Results table -->
      @if (order()!.results.length > 0) {
        <div class="card" style="margin-top:16px">
          <h3 class="card-title">Results</h3>
          <table class="data-table">
            <thead>
              <tr><th>Test Code</th><th>Name</th><th>Value</th><th>Unit</th><th>Interpretation</th><th>By</th></tr>
            </thead>
            <tbody>
              @for (r of order()!.results; track r.test_code) {
                <tr [class.critical-row]="r.interpretation === 'critical_low' || r.interpretation === 'critical_high'">
                  <td><code>{{ r.test_code }}</code></td>
                  <td>{{ r.test_name }}</td>
                  <td><strong>{{ r.value }}</strong></td>
                  <td>{{ r.unit ?? '—' }}</td>
                  <td>
                    <span class="badge" [class]="iClass(r.interpretation)">
                      {{ r.interpretation.replace('_', ' ') }}
                    </span>
                  </td>
                  <td>{{ r.performed_by | slice:0:8 }}…</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
    }
  `,
  styles: [`
    .detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    @media(max-width:768px){.detail-grid{grid-template-columns:1fr}}
    .card-title{font-weight:600;color:#334155;margin-bottom:12px;font-size:.95rem}
    .kv-list{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:.875rem}
    .kv-list dt{color:#64748b;font-weight:500}
    .kv-list dd{margin:0}
    .inline-form{display:flex;flex-direction:column;gap:8px}
    .form-row{display:flex;gap:8px}
    .form-row .form-control{flex:1}
    .btn-sm{padding:6px 14px;font-size:.8rem}
    .critical-row{background:#fff5f5}
  `],
})
export class LabOrderDetailComponent implements OnInit {
  id = input.required<string>();
  readonly auth = inject(AuthService);
  private readonly svc = inject(LabOrderService);
  private readonly fb = inject(FormBuilder);

  order = signal<LabOrder | null>(null);
  loading = signal(true);
  actionError = signal('');
  actionSuccess = signal('');
  interpretations = INTERPRETATION_OPTIONS;

  resultForm = this.fb.group({
    test_code: ['', Validators.required],
    test_name: ['', Validators.required],
    value: ['', Validators.required],
    unit: [''],
    interpretation: ['normal', Validators.required],
    notes: [''],
  });

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.svc.get(this.id()).subscribe({
      next: o => { this.order.set(o); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  collectSample(sampleType: string): void {
    this.svc.collectSample(this.id(), sampleType).subscribe({
      next: () => { this.actionSuccess.set('Sample collected.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  recordResult(): void {
    if (this.resultForm.invalid) return;
    const v = this.resultForm.value as any;
    this.svc.recordResult(this.id(), {
      test_code: v.test_code, test_name: v.test_name,
      value: v.value, unit: v.unit || undefined,
      interpretation: v.interpretation, notes: v.notes || undefined,
    }).subscribe({
      next: () => { this.resultForm.reset({ interpretation: 'normal' }); this.actionSuccess.set('Result recorded.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  complete(): void {
    if (!confirm('Mark this order as completed and publish results?')) return;
    this.svc.complete(this.id()).subscribe({
      next: () => { this.actionSuccess.set('Order completed. Results published.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  cancel(): void {
    const reason = prompt('Reason for cancellation:');
    if (!reason) return;
    this.svc.cancel(this.id(), reason).subscribe({
      next: () => { this.actionSuccess.set('Order cancelled.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  statusClass(s: string): string {
    return { pending: 'badge-booked', sample_collected: 'badge-checked_in', in_progress: 'badge-checked_in', completed: 'badge-booked', cancelled: 'badge-cancelled' }[s] ?? '';
  }

  iClass(i: string): string {
    if (i === 'critical_low' || i === 'critical_high') return 'badge-cancelled';
    if (i === 'normal' || i === 'negative') return 'badge-booked';
    return 'badge-no_show';
  }
}
