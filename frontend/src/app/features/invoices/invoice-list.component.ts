import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { DatePipe, SlicePipe, DecimalPipe } from '@angular/common';
import { InvoiceService } from '../../shared/api/invoice.service';
import { Invoice } from '../../shared/models/invoice.model';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';

@Component({
  selector: 'app-invoice-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SlicePipe, DecimalPipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Invoices</h1>
    </div>

    <!-- Status chip bar -->
    <div class="chip-bar">
      @for (f of statusFilters; track f.value) {
        <button class="chip" [class.chip-active]="statusFilter === f.value"
                (click)="onStatusChange(f.value)">
          {{ f.label }}
          @if (f.value === '' && total() > 0) { <span class="chip-count">{{ total() }}</span> }
        </button>
      }
    </div>

    @if (loading()) {
      <div class="loading">Loading invoices…</div>
    } @else if (invoices().length === 0) {
      <div class="empty-state">No invoices found.</div>
    } @else {
      <table class="data-table">
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Patient</th>
            <th>Charges</th>
            <th>Total</th>
            <th>Status</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (inv of invoices(); track inv.invoice_id) {
            <tr>
              <td><code class="id-code">{{ inv.invoice_id | slice:0:12 }}…</code></td>
              <td class="patient-cell">{{ patientNames()[inv.patient_id] || '…' }}</td>
              <td>{{ inv.lines.length }} line{{ inv.lines.length !== 1 ? 's' : '' }}</td>
              <td class="amount-cell">
                <span class="currency-tag">{{ inv.currency }}</span>
                {{ computeTotal(inv) | number:'1.2-2' }}
              </td>
              <td>
                <span class="status-chip" [class]="'sc-' + inv.status">{{ formatStatus(inv.status) }}</span>
              </td>
              <td class="date-cell">{{ inv.created_at | date:'dd MMM yyyy' }}</td>
              <td><a [routerLink]="['/invoices', inv.invoice_id]" class="link">View →</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`
    .chip-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
    .chip { padding: 6px 14px; border-radius: 20px; font-size: .8rem; font-weight: 500; border: 1px solid var(--clr-gray-200); background: #fff; color: var(--clr-gray-600); cursor: pointer; transition: all .15s; display: flex; align-items: center; gap: 6px; }
    .chip:hover { border-color: var(--clr-brand); color: var(--clr-brand); }
    .chip-active { background: var(--clr-brand); color: #fff !important; border-color: var(--clr-brand); }
    .chip-count { background: rgba(0,0,0,.1); padding: 1px 7px; border-radius: 10px; font-size: .72rem; font-weight: 700; }
    .chip-active .chip-count { background: rgba(255,255,255,.25); }

    .id-code { font-size: .78rem; color: var(--clr-gray-500); }
    .patient-cell { font-weight: 600; color: var(--clr-gray-800); }
    .date-cell { font-size: .8rem; color: var(--clr-gray-500); }
    .link { color: var(--clr-brand); text-decoration: none; font-weight: 500; }
    .link:hover { text-decoration: underline; }
    .amount-cell { font-weight: 700; font-variant-numeric: tabular-nums; }
    .currency-tag { font-size: .7rem; font-weight: 700; background: var(--clr-brand-light); color: var(--clr-brand); padding: 2px 5px; border-radius: 3px; margin-right: 4px; }

    .status-chip { padding: 4px 10px; border-radius: 12px; font-size: .75rem; font-weight: 600; }
    .sc-draft { background: #f1f5f9; color: #475569; }
    .sc-issued { background: #dbeafe; color: #1e40af; }
    .sc-partially_paid { background: #fef3c7; color: #92400e; }
    .sc-paid { background: #d1fae5; color: #065f46; }
    .sc-void { background: #fee2e2; color: #991b1b; }
  `],
})
export class InvoiceListComponent implements OnInit {
  private readonly svc = inject(InvoiceService);
  private readonly route = inject(ActivatedRoute);
  private readonly nameCache = inject(PatientNameCache);

  invoices = signal<Invoice[]>([]);
  loading = signal(true);
  patientNames = signal<Record<string, string>>({});
  total = signal(0);
  statusFilter = '';
  private encounterId?: string;

  statusFilters = [
    { value: '', label: 'All' },
    { value: 'draft', label: 'Draft' },
    { value: 'issued', label: 'Issued' },
    { value: 'partially_paid', label: 'Partially Paid' },
    { value: 'paid', label: 'Paid' },
    { value: 'void', label: 'Void' },
  ];

  ngOnInit(): void {
    this.encounterId = this.route.snapshot.queryParamMap.get('encounter_id') ?? undefined;
    this.load();
  }

  onStatusChange(status: string): void {
    this.statusFilter = status;
    this.load();
  }

  formatStatus(s: string): string { return s.replace(/_/g, ' '); }

  computeTotal(inv: Invoice): number {
    return inv.lines.reduce((sum, ln) => sum + parseFloat(ln.unit_price.amount) * ln.quantity, 0);
  }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.encounterId, this.statusFilter || undefined).subscribe({
      next: r => {
        this.invoices.set(r.items);
        this.total.set(r.total);
        this.loading.set(false);
        const ids = r.items.map(i => i.patient_id);
        if (ids.length) this.nameCache.resolveMany(ids).subscribe(m => this.patientNames.set(m));
      },
      error: () => this.loading.set(false),
    });
  }
}
