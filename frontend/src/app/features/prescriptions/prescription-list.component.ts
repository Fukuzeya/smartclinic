import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, SlicePipe } from '@angular/common';
import { PrescriptionService } from '../../shared/api/prescription.service';
import { Prescription } from '../../shared/models/prescription.model';

@Component({
  selector: 'app-prescription-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SlicePipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Dispense Queue</h1>
    </div>

    <div class="filter-bar">
      <select class="form-control" style="width:180px" (change)="onStatusChange($any($event.target).value)">
        <option value="pending">Pending</option>
        <option value="">All</option>
        <option value="dispensed">Dispensed</option>
        <option value="rejected">Rejected</option>
      </select>
    </div>

    @if (loading()) {
      <div class="loading">Loading prescriptions…</div>
    } @else if (prescriptions().length === 0) {
      <div class="empty-state">No prescriptions found.</div>
    } @else {
      <table class="data-table">
        <thead>
          <tr>
            <th>Prescription ID</th>
            <th>Patient</th>
            <th>Drugs</th>
            <th>Status</th>
            <th>Received</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (rx of prescriptions(); track rx.prescription_id) {
            <tr>
              <td><code class="id-code">{{ rx.prescription_id | slice:0:12 }}…</code></td>
              <td><code class="id-code">{{ rx.patient_id | slice:0:12 }}…</code></td>
              <td class="drug-cell">
                @for (ln of rx.lines; track ln.drug_name) {
                  <span class="drug-tag">{{ ln.drug_name }}</span>
                }
              </td>
              <td>
                <span class="badge" [class]="statusClass(rx.status)">{{ rx.status.replace('_', ' ') }}</span>
              </td>
              <td>{{ rx.received_at | date:'dd MMM yyyy HH:mm' }}</td>
              <td><a [routerLink]="['/prescriptions', rx.prescription_id]" class="link">View →</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`.id-code{font-size:.78rem;color:#64748b}.link{color:#6366f1;text-decoration:none;font-weight:500}.drug-cell{display:flex;gap:4px;flex-wrap:wrap}.drug-tag{background:#f0fdf4;color:#16a34a;padding:2px 6px;border-radius:4px;font-size:.75rem;font-weight:500}`],
})
export class PrescriptionListComponent implements OnInit {
  private readonly svc = inject(PrescriptionService);
  prescriptions = signal<Prescription[]>([]);
  loading = signal(true);
  private statusFilter = 'pending';

  ngOnInit(): void { this.load(); }

  onStatusChange(status: string): void {
    this.statusFilter = status;
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined).subscribe({
      next: r => { this.prescriptions.set(r.items); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  statusClass(s: string): string {
    return {
      pending: 'badge-booked',
      dispensed: 'badge-checked_in',
      partially_dispensed: 'badge-checked_in',
      rejected: 'badge-cancelled',
      cancelled: 'badge-cancelled',
    }[s] ?? '';
  }
}
