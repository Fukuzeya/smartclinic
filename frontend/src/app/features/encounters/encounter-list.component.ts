import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, SlicePipe } from '@angular/common';
import { EncounterService } from '../../shared/api/encounter.service';
import { EncounterSummary } from '../../shared/models/encounter.model';
import { AuthService } from '../../core/auth/auth.service';
import { PatientNameCache } from '../../shared/services/patient-name-cache.service';
import { DoctorNameCache } from '../../shared/services/doctor-name-cache.service';

@Component({
  selector: 'app-encounter-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SlicePipe],
  template: `
    <div class="page-header">
      <h1 class="page-title">Clinical Encounters</h1>
      @if (auth.isDoctor()) {
        <a routerLink="/encounters/new" class="btn-primary">+ Start Encounter</a>
      }
    </div>

    <div class="filter-bar">
      <select class="form-control" style="width:180px" (change)="onStatusChange($any($event.target).value)">
        <option value="">All statuses</option>
        <option value="in_progress">In Progress</option>
        <option value="closed">Closed</option>
      </select>
    </div>

    @if (loading()) {
      <div class="loading">Loading encounters…</div>
    } @else if (encounters().length === 0) {
      <div class="empty-state">No encounters found.</div>
    } @else {
      <table class="data-table">
        <thead>
          <tr>
            <th>Encounter ID</th>
            <th>Patient</th>
            <th>Doctor</th>
            <th>Status</th>
            <th>Started</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (enc of encounters(); track enc.encounter_id) {
            <tr>
              <td><code class="id-code">{{ enc.encounter_id | slice:0:12 }}…</code></td>
              <td>{{ patientNames()[enc.patient_id] || '…' }}</td>
              <td>{{ doctorNames()[enc.doctor_id] || '…' }}</td>
              <td>
                <span class="badge" [class]="'badge-' + enc.status">{{ enc.status.replace('_', ' ') }}</span>
              </td>
              <td>{{ enc.started_at | date:'dd MMM yyyy HH:mm' }}</td>
              <td><a [routerLink]="['/encounters', enc.encounter_id]" class="link">View →</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`.id-code{font-size:.78rem;color:var(--clr-gray-500)}.link{color:var(--clr-brand);text-decoration:none;font-weight:500}.link:hover{text-decoration:underline}`],
})
export class EncounterListComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly svc = inject(EncounterService);
  private readonly nameCache = inject(PatientNameCache);
  private readonly doctorCache = inject(DoctorNameCache);

  encounters = signal<EncounterSummary[]>([]);
  loading = signal(true);
  patientNames = signal<Record<string, string>>({});
  doctorNames = signal<Record<string, string>>({});
  private statusFilter = '';

  ngOnInit(): void { this.load(); }

  onStatusChange(status: string): void {
    this.statusFilter = status;
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined).subscribe({
      next: r => {
        this.encounters.set(r.items);
        this.loading.set(false);
        const pIds = r.items.map(e => e.patient_id);
        if (pIds.length) this.nameCache.resolveMany(pIds).subscribe(m => this.patientNames.set(m));
        const dIds = r.items.map(e => e.doctor_id);
        if (dIds.length) this.doctorCache.resolveMany(dIds).subscribe(m => this.doctorNames.set(m));
      },
      error: () => this.loading.set(false),
    });
  }
}
