import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, SlicePipe } from '@angular/common';
import { PrescriptionService } from '../../shared/api/prescription.service';
import { Prescription } from '../../shared/models/prescription.model';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';

@Component({
  selector: 'app-prescription-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SlicePipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Dispense Queue</h1>
    </div>

    <!-- Status chip bar -->
    <div class="chip-bar">
      @for (f of statusFilters; track f.value) {
        <button class="chip" [class.chip-active]="statusFilter === f.value"
                (click)="onStatusChange(f.value)">
          {{ f.label }}
          @if (f.value === 'pending' && pendingCount() > 0) { <span class="chip-count chip-count-warn">{{ pendingCount() }}</span> }
        </button>
      }
    </div>

    @if (loading()) {
      <div class="loading">Loading prescriptions…</div>
    } @else if (prescriptions().length === 0) {
      <div class="empty-state">No prescriptions found.</div>
    } @else {
      <table class="data-table">
        <thead>
          <tr>
            <th>Prescription</th>
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
              <td class="patient-cell">{{ patientNames()[rx.patient_id] || '…' }}</td>
              <td class="drug-cell">
                @for (ln of rx.lines; track ln.drug_name) {
                  <span class="drug-tag">{{ ln.drug_name }}</span>
                }
              </td>
              <td>
                <span class="status-chip" [class]="'sc-' + rx.status">{{ formatStatus(rx.status) }}</span>
              </td>
              <td class="date-cell">{{ rx.received_at | date:'dd MMM HH:mm' }}</td>
              <td><a [routerLink]="['/prescriptions', rx.prescription_id]" class="link">View →</a></td>
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
    .drug-cell { display: flex; gap: 4px; flex-wrap: wrap; }
    .drug-tag { background: #f0fdf4; color: #16a34a; padding: 2px 6px; border-radius: 4px; font-size: .72rem; font-weight: 600; }

    .status-chip { padding: 4px 10px; border-radius: 12px; font-size: .75rem; font-weight: 600; }
    .sc-pending { background: #fef3c7; color: #92400e; }
    .sc-dispensed { background: #d1fae5; color: #065f46; }
    .sc-partially_dispensed { background: #dbeafe; color: #1e40af; }
    .sc-rejected { background: #fee2e2; color: #991b1b; }
    .sc-cancelled { background: #f1f5f9; color: #475569; }
  `],
})
export class PrescriptionListComponent implements OnInit {
  private readonly svc = inject(PrescriptionService);
  private readonly nameCache = inject(PatientNameCache);
  prescriptions = signal<Prescription[]>([]);
  loading = signal(true);
  patientNames = signal<Record<string, string>>({});
  pendingCount = signal(0);
  statusFilter = 'pending';

  statusFilters = [
    { value: 'pending', label: 'Pending' },
    { value: 'partially_dispensed', label: 'Partial' },
    { value: '', label: 'All' },
    { value: 'dispensed', label: 'Dispensed' },
    { value: 'rejected', label: 'Rejected' },
  ];

  ngOnInit(): void { this.load(); }

  onStatusChange(status: string): void {
    this.statusFilter = status;
    this.load();
  }

  formatStatus(s: string): string { return s.replace(/_/g, ' '); }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined).subscribe({
      next: r => {
        this.prescriptions.set(r.items);
        this.loading.set(false);
        const ids = r.items.map(rx => rx.patient_id);
        if (ids.length) this.nameCache.resolveMany(ids).subscribe(m => this.patientNames.set(m));
      },
      error: () => this.loading.set(false),
    });
    // Fetch pending count
    if (this.statusFilter !== 'pending') {
      this.svc.list(undefined, 'pending', 1, 0).subscribe({
        next: r => this.pendingCount.set(r.total),
      });
    }
  }
}
