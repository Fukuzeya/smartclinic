import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { DatePipe, SlicePipe } from '@angular/common';
import { LabOrderService } from '../../shared/api/lab-order.service';
import { LabOrder } from '../../shared/models/lab-order.model';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';

@Component({
  selector: 'app-lab-order-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SlicePipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Laboratory Orders</h1>
    </div>

    <!-- Status chip bar -->
    <div class="chip-bar">
      @for (f of statusFilters; track f.value) {
        <button class="chip" [class.chip-active]="statusFilter === f.value"
                (click)="onStatusChange(f.value)">
          {{ f.label }}
          @if (f.value === '' && total() > 0) { <span class="chip-count">{{ total() }}</span> }
          @if (f.value === 'pending' && pendingCount() > 0) { <span class="chip-count chip-count-warn">{{ pendingCount() }}</span> }
        </button>
      }
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
            <th>Urgency</th>
            <th>Status</th>
            <th>Received</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (o of orders(); track o.order_id) {
            <tr [class.urgent-row]="hasUrgent(o)">
              <td><code class="id-code">{{ o.order_id | slice:0:12 }}…</code></td>
              <td class="patient-cell">{{ patientNames()[o.patient_id] || '…' }}</td>
              <td class="tests-cell">
                @for (ln of o.lines; track ln.test_code) {
                  <span class="test-tag">{{ ln.test_code }}</span>
                }
              </td>
              <td>
                @if (hasUrgent(o)) {
                  <span class="urgency-badge urgency-urgent">URGENT</span>
                } @else if (hasStat(o)) {
                  <span class="urgency-badge urgency-stat">STAT</span>
                } @else {
                  <span class="urgency-badge urgency-routine">Routine</span>
                }
              </td>
              <td><span class="status-chip" [class]="statusClass(o.status)">{{ formatStatus(o.status) }}</span></td>
              <td class="date-cell">{{ o.received_at | date:'dd MMM HH:mm' }}</td>
              <td><a [routerLink]="['/lab-orders', o.order_id]" class="link">Manage →</a></td>
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
    .chip-count-warn { background: #fef3c7; color: #92400e; }
    .chip-active .chip-count-warn { background: rgba(255,255,255,.25); color: #fff; }

    .id-code { font-size: .78rem; color: var(--clr-gray-500); }
    .patient-cell { font-weight: 600; color: var(--clr-gray-800); }
    .date-cell { font-size: .8rem; color: var(--clr-gray-500); }
    .link { color: var(--clr-brand); text-decoration: none; font-weight: 500; }
    .link:hover { text-decoration: underline; }

    .tests-cell { display: flex; gap: 4px; flex-wrap: wrap; }
    .test-tag { background: #eff6ff; color: #2563eb; padding: 2px 8px; border-radius: 4px; font-size: .72rem; font-weight: 600; font-family: monospace; }

    .urgency-badge { padding: 2px 8px; border-radius: 4px; font-size: .7rem; font-weight: 700; letter-spacing: .03em; }
    .urgency-routine { background: #f1f5f9; color: #64748b; }
    .urgency-urgent { background: #fef3c7; color: #92400e; }
    .urgency-stat { background: #fee2e2; color: #991b1b; }

    .status-chip { padding: 4px 10px; border-radius: 12px; font-size: .75rem; font-weight: 600; }
    .status-pending { background: #fef3c7; color: #92400e; }
    .status-sample_collected { background: #dbeafe; color: #1e40af; }
    .status-in_progress { background: #e0e7ff; color: #3730a3; }
    .status-completed { background: #d1fae5; color: #065f46; }
    .status-cancelled { background: #f1f5f9; color: #475569; }

    .urgent-row { background: #fffbeb; }
  `],
})
export class LabOrderListComponent implements OnInit {
  private readonly svc = inject(LabOrderService);
  private readonly route = inject(ActivatedRoute);
  private readonly nameCache = inject(PatientNameCache);

  orders = signal<LabOrder[]>([]);
  loading = signal(true);
  patientNames = signal<Record<string, string>>({});
  total = signal(0);
  pendingCount = signal(0);
  statusFilter = '';
  private encounterId: string | null = null;

  statusFilters = [
    { value: '', label: 'All' },
    { value: 'pending', label: 'Pending' },
    { value: 'sample_collected', label: 'Sample Collected' },
    { value: 'in_progress', label: 'In Progress' },
    { value: 'completed', label: 'Completed' },
    { value: 'cancelled', label: 'Cancelled' },
  ];

  ngOnInit(): void {
    this.encounterId = this.route.snapshot.queryParamMap.get('encounter_id');
    this.load();
  }

  onStatusChange(s: string): void { this.statusFilter = s; this.load(); }

  hasUrgent(o: LabOrder): boolean { return o.lines.some(l => l.urgency === 'urgent'); }
  hasStat(o: LabOrder): boolean { return o.lines.some(l => l.urgency === 'stat'); }

  formatStatus(s: string): string { return s.replace(/_/g, ' '); }

  statusClass(s: string): string { return 'status-' + s; }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined, this.encounterId ?? undefined).subscribe({
      next: r => {
        this.orders.set(r.items);
        this.total.set(r.total);
        this.loading.set(false);
        const ids = r.items.map(o => o.patient_id);
        if (ids.length) this.nameCache.resolveMany(ids).subscribe(m => this.patientNames.set(m));
      },
      error: () => this.loading.set(false),
    });
    // Fetch pending count for badge
    if (this.statusFilter !== 'pending') {
      this.svc.list(undefined, 'pending', this.encounterId ?? undefined, 1, 0).subscribe({
        next: r => this.pendingCount.set(r.total),
      });
    }
  }
}
