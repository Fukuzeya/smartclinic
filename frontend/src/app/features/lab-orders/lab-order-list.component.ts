import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { DatePipe, SlicePipe } from '@angular/common';
import { LabOrderService } from '../../shared/api/lab-order.service';
import { LabOrder } from '../../shared/models/lab-order.model';

@Component({
  selector: 'app-lab-order-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SlicePipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Laboratory Orders</h1>
    </div>

    <div class="filter-bar">
      <select class="form-control" style="width:180px" (change)="onStatusChange($any($event.target).value)">
        <option value="">All statuses</option>
        <option value="pending">Pending</option>
        <option value="sample_collected">Sample Collected</option>
        <option value="in_progress">In Progress</option>
        <option value="completed">Completed</option>
        <option value="cancelled">Cancelled</option>
      </select>
    </div>

    @if (loading()) {
      <div class="loading">Loading lab orders…</div>
    } @else if (orders().length === 0) {
      <div class="empty-state">No lab orders found.</div>
    } @else {
      <table class="data-table">
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Patient</th>
            <th>Tests</th>
            <th>Status</th>
            <th>Received</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (o of orders(); track o.order_id) {
            <tr>
              <td><code class="id-code">{{ o.order_id | slice:0:12 }}…</code></td>
              <td><code class="id-code">{{ o.patient_id | slice:0:12 }}…</code></td>
              <td>{{ o.lines.length }} test{{ o.lines.length !== 1 ? 's' : '' }}</td>
              <td><span class="badge" [class]="statusClass(o.status)">{{ o.status.replace('_', ' ') }}</span></td>
              <td>{{ o.received_at | date:'dd MMM HH:mm' }}</td>
              <td><a [routerLink]="['/lab-orders', o.order_id]" class="link">Manage →</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`.id-code{font-size:.78rem;color:#64748b}.link{color:#6366f1;text-decoration:none;font-weight:500}`],
})
export class LabOrderListComponent implements OnInit {
  private readonly svc = inject(LabOrderService);
  private readonly route = inject(ActivatedRoute);

  orders = signal<LabOrder[]>([]);
  loading = signal(true);
  private statusFilter = '';
  private encounterId: string | null = null;

  ngOnInit(): void {
    this.encounterId = this.route.snapshot.queryParamMap.get('encounter_id');
    this.load();
  }

  onStatusChange(s: string): void { this.statusFilter = s; this.load(); }

  statusClass(s: string): string {
    const m: Record<string, string> = {
      pending: 'badge-booked', sample_collected: 'badge-checked_in',
      in_progress: 'badge-checked_in', completed: 'badge-booked',
      cancelled: 'badge-cancelled',
    };
    return m[s] ?? '';
  }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined, this.encounterId ?? undefined).subscribe({
      next: r => { this.orders.set(r.items); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
