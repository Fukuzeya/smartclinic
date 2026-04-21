import { Component, inject, signal, input, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DatePipe, SlicePipe } from '@angular/common';
import { InvoiceService } from '../../shared/api/invoice.service';
import { Invoice, InvoiceSummary } from '../../shared/models/invoice.model';
import { AuthService } from '../../core/auth/auth.service';

const CHARGE_CATEGORIES = ['consultation', 'lab_test', 'medication', 'procedure', 'accommodation', 'other'];
const PAYMENT_METHODS = ['cash', 'ecocash', 'zipit', 'insurance', 'bank_transfer', 'other'];

@Component({
  selector: 'app-invoice-detail',
  standalone: true,
  imports: [DatePipe, SlicePipe, ReactiveFormsModule],
  template: `
    @if (loading()) {
      <div class="loading">Loading…</div>
    } @else if (invoice()) {
      <div class="page-header">
        <div>
          <h1 class="page-title">Invoice</h1>
          <code style="font-size:.85rem;color:#64748b">{{ invoice()!.invoice_id }}</code>
        </div>
        <span class="badge" [class]="statusClass(invoice()!.status)" style="font-size:.9rem;padding:6px 14px">
          {{ invoice()!.status.replace('_', ' ') }}
        </span>
      </div>

      <div class="detail-grid">
        <!-- Invoice info + summary -->
        <div class="card">
          <h3 class="card-title">Invoice Information</h3>
          <dl class="kv-list">
            <dt>Patient</dt><dd><code>{{ invoice()!.patient_id }}</code></dd>
            <dt>Encounter</dt><dd><code>{{ invoice()!.encounter_id }}</code></dd>
            <dt>Currency</dt><dd><strong>{{ invoice()!.currency }}</strong></dd>
            <dt>Created</dt><dd>{{ invoice()!.created_at | date:'dd MMM yyyy HH:mm' }}</dd>
            @if (invoice()!.issued_at) {
              <dt>Issued</dt><dd>{{ invoice()!.issued_at | date:'dd MMM yyyy HH:mm' }}</dd>
            }
            @if (invoice()!.paid_at) {
              <dt>Paid</dt><dd>{{ invoice()!.paid_at | date:'dd MMM yyyy HH:mm' }}</dd>
            }
          </dl>

          @if (summary()) {
            <div class="balance-panel">
              <div class="balance-row"><span>Total Due</span><span class="amount">{{ summary()!.currency }} {{ summary()!.total_due }}</span></div>
              <div class="balance-row"><span>Total Paid</span><span class="amount paid">{{ summary()!.currency }} {{ summary()!.total_paid }}</span></div>
              <div class="balance-row balance-due"><span>Balance</span><span class="amount" [class.zero]="summary()!.balance === '0.00'">{{ summary()!.currency }} {{ summary()!.balance }}</span></div>
            </div>
          }
        </div>

        <!-- Actions -->
        <div class="card">
          <h3 class="card-title">Actions</h3>

          @if (invoice()!.status === 'draft' && auth.hasRole('accounts')) {
            <form [formGroup]="chargeForm" (ngSubmit)="addCharge()" class="inline-form">
              <h4 class="sub-title">Add Charge</h4>
              <select class="form-control" formControlName="category">
                @for (c of chargeCategories; track c) {
                  <option [value]="c">{{ c.replace('_', ' ') }}</option>
                }
              </select>
              <input class="form-control" formControlName="description" placeholder="Description" />
              <div class="form-row">
                <input class="form-control" formControlName="unit_price_amount" placeholder="Unit price" type="number" step="0.01" />
                <input class="form-control" formControlName="quantity" placeholder="Qty" type="number" min="1" />
              </div>
              <button type="submit" class="btn-primary btn-sm">Add Charge</button>
            </form>

            <button class="btn-secondary" style="margin-top:12px" (click)="issue()">
              Issue Invoice
            </button>
          }

          @if ((invoice()!.status === 'issued' || invoice()!.status === 'partially_paid') && auth.hasRole('accounts')) {
            <form [formGroup]="paymentForm" (ngSubmit)="recordPayment()" class="inline-form">
              <h4 class="sub-title">Record Payment</h4>
              <div class="form-row">
                <input class="form-control" formControlName="amount" placeholder="Amount" type="number" step="0.01" />
                <select class="form-control" formControlName="method">
                  @for (m of paymentMethods; track m) {
                    <option [value]="m">{{ m.replace('_', ' ') }}</option>
                  }
                </select>
              </div>
              <input class="form-control" formControlName="reference" placeholder="Reference / receipt no." />
              <button type="submit" class="btn-primary btn-sm">Record Payment</button>
            </form>
          }

          @if (invoice()!.status !== 'paid' && invoice()!.status !== 'void' && auth.hasRole('accounts')) {
            <button class="btn-danger" style="margin-top:8px" (click)="voidInvoice()">Void Invoice</button>
          }

          @if (actionError()) { <div class="alert-error" style="margin-top:8px">{{ actionError() }}</div> }
          @if (actionSuccess()) { <div class="alert-success" style="margin-top:8px">{{ actionSuccess() }}</div> }
        </div>
      </div>

      <!-- Charge lines -->
      @if (invoice()!.lines.length > 0) {
        <div class="card" style="margin-top:16px">
          <h3 class="card-title">Charge Lines</h3>
          <table class="data-table">
            <thead>
              <tr><th>Category</th><th>Description</th><th>Unit Price</th><th>Qty</th><th>Subtotal</th></tr>
            </thead>
            <tbody>
              @for (ln of invoice()!.lines; track ln.description) {
                <tr>
                  <td><span class="category-tag">{{ ln.category.replace('_', ' ') }}</span></td>
                  <td>{{ ln.description }}</td>
                  <td>{{ ln.unit_price.currency }} {{ ln.unit_price.amount }}</td>
                  <td>{{ ln.quantity }}</td>
                  <td><strong>{{ ln.unit_price.currency }} {{ (parseFloat(ln.unit_price.amount) * ln.quantity).toFixed(2) }}</strong></td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }

      <!-- Payments -->
      @if (invoice()!.payments.length > 0) {
        <div class="card" style="margin-top:16px">
          <h3 class="card-title">Payments Received</h3>
          <table class="data-table">
            <thead>
              <tr><th>Method</th><th>Amount</th><th>Reference</th><th>Recorded by</th></tr>
            </thead>
            <tbody>
              @for (p of invoice()!.payments; track p.reference) {
                <tr>
                  <td><span class="method-tag">{{ p.method.replace('_', ' ') }}</span></td>
                  <td><strong>{{ p.amount.currency }} {{ p.amount.amount }}</strong></td>
                  <td><code>{{ p.reference }}</code></td>
                  <td>{{ p.recorded_by | slice:0:8 }}…</td>
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
    .sub-title{font-size:.85rem;font-weight:600;color:#64748b;margin-bottom:8px;margin-top:0}
    .kv-list{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:.875rem}
    .kv-list dt{color:#64748b;font-weight:500}
    .kv-list dd{margin:0}
    .balance-panel{margin-top:16px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}
    .balance-row{display:flex;justify-content:space-between;align-items:center;padding:8px 14px;font-size:.875rem;border-bottom:1px solid #f1f5f9}
    .balance-row:last-child{border-bottom:none}
    .balance-due{background:#fafafa;font-weight:600}
    .amount{font-family:monospace;font-size:.9rem}
    .amount.paid{color:#10b981}
    .amount.zero{color:#94a3b8}
    .inline-form{display:flex;flex-direction:column;gap:8px}
    .form-row{display:flex;gap:8px}
    .form-row .form-control{flex:1}
    .btn-sm{padding:6px 14px;font-size:.8rem}
    .category-tag{background:#eff6ff;color:#2563eb;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:500;text-transform:capitalize}
    .method-tag{background:#f0fdf4;color:#16a34a;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:500;text-transform:capitalize}
  `],
})
export class InvoiceDetailComponent implements OnInit {
  id = input.required<string>();
  readonly auth = inject(AuthService);
  private readonly svc = inject(InvoiceService);
  private readonly fb = inject(FormBuilder);

  invoice = signal<Invoice | null>(null);
  summary = signal<InvoiceSummary | null>(null);
  loading = signal(true);
  actionError = signal('');
  actionSuccess = signal('');

  chargeCategories = CHARGE_CATEGORIES;
  paymentMethods = PAYMENT_METHODS;
  readonly parseFloat = parseFloat;

  chargeForm = this.fb.group({
    category: ['consultation', Validators.required],
    description: ['', Validators.required],
    unit_price_amount: ['', Validators.required],
    quantity: [1, [Validators.required, Validators.min(1)]],
  });

  paymentForm = this.fb.group({
    amount: ['', Validators.required],
    method: ['cash', Validators.required],
    reference: ['', Validators.required],
  });

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.svc.get(this.id()).subscribe({
      next: inv => {
        this.invoice.set(inv);
        this.loading.set(false);
        this.svc.getSummary(this.id()).subscribe({ next: s => this.summary.set(s) });
      },
      error: () => this.loading.set(false),
    });
  }

  addCharge(): void {
    if (this.chargeForm.invalid) return;
    const v = this.chargeForm.value as any;
    this.svc.addCharge(this.id(), {
      category: v.category,
      description: v.description,
      unit_price_amount: v.unit_price_amount,
      unit_price_currency: this.invoice()!.currency,
      quantity: v.quantity ?? 1,
    }).subscribe({
      next: () => { this.chargeForm.reset({ category: 'consultation', quantity: 1 }); this.actionSuccess.set('Charge added.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  issue(): void {
    if (!confirm('Issue this invoice? The patient will be notified.')) return;
    this.svc.issue(this.id()).subscribe({
      next: () => { this.actionSuccess.set('Invoice issued.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  recordPayment(): void {
    if (this.paymentForm.invalid) return;
    const v = this.paymentForm.value as any;
    this.svc.recordPayment(this.id(), {
      amount: v.amount,
      currency: this.invoice()!.currency,
      method: v.method,
      reference: v.reference,
    }).subscribe({
      next: () => { this.paymentForm.reset({ method: 'cash' }); this.actionSuccess.set('Payment recorded.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  voidInvoice(): void {
    const reason = prompt('Reason for voiding this invoice:');
    if (!reason?.trim()) return;
    this.svc.void(this.id(), reason).subscribe({
      next: () => { this.actionSuccess.set('Invoice voided.'); this.reload(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Error'),
    });
  }

  statusClass(s: string): string {
    return {
      draft: 'badge-no_show',
      issued: 'badge-booked',
      partially_paid: 'badge-checked_in',
      paid: 'badge-checked_in',
      void: 'badge-cancelled',
    }[s] ?? '';
  }
}
