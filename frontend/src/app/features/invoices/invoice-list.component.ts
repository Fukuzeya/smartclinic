import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { DatePipe, SlicePipe } from '@angular/common';
import { InvoiceService } from '../../shared/api/invoice.service';
import { Invoice } from '../../shared/models/invoice.model';

@Component({
  selector: 'app-invoice-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SlicePipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Invoices</h1>
    </div>

    <div class="filter-bar">
      <select class="form-control" style="width:180px" (change)="onStatusChange($any($event.target).value)">
        <option value="">All</option>
        <option value="draft">Draft</option>
        <option value="issued">Issued</option>
        <option value="partially_paid">Partially Paid</option>
        <option value="paid">Paid</option>
        <option value="void">Void</option>
      </select>
    </div>

    @if (loading()) {
      <div class="loading">Loading invoices…</div>
    } @else if (invoices().length === 0) {
      <div class="empty-state">No invoices found.</div>
    } @else {
      <table class="data-table">
        <thead>
          <tr>
            <th>Invoice ID</th>
            <th>Patient</th>
            <th>Currency</th>
            <th>Lines</th>
            <th>Status</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (inv of invoices(); track inv.invoice_id) {
            <tr>
              <td><code class="id-code">{{ inv.invoice_id | slice:0:12 }}…</code></td>
              <td><code class="id-code">{{ inv.patient_id | slice:0:12 }}…</code></td>
              <td><span class="currency-badge">{{ inv.currency }}</span></td>
              <td>{{ inv.lines.length }} charge{{ inv.lines.length !== 1 ? 's' : '' }}</td>
              <td><span class="badge" [class]="statusClass(inv.status)">{{ inv.status.replace('_', ' ') }}</span></td>
              <td>{{ inv.created_at | date:'dd MMM yyyy' }}</td>
              <td><a [routerLink]="['/invoices', inv.invoice_id]" class="link">View →</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`.id-code{font-size:.78rem;color:#64748b}.link{color:#6366f1;text-decoration:none;font-weight:500}.currency-badge{background:#f0f9ff;color:#0284c7;padding:2px 6px;border-radius:4px;font-size:.75rem;font-weight:600}`],
})
export class InvoiceListComponent implements OnInit {
  private readonly svc = inject(InvoiceService);
  private readonly route = inject(ActivatedRoute);

  invoices = signal<Invoice[]>([]);
  loading = signal(true);
  private statusFilter = '';
  private encounterId?: string;

  ngOnInit(): void {
    this.encounterId = this.route.snapshot.queryParamMap.get('encounter_id') ?? undefined;
    this.load();
  }

  onStatusChange(status: string): void {
    this.statusFilter = status;
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.encounterId, this.statusFilter || undefined).subscribe({
      next: r => { this.invoices.set(r.items); this.loading.set(false); },
      error: () => this.loading.set(false),
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
