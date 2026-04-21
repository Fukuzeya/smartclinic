import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, SlicePipe } from '@angular/common';
import { EncounterService } from '../../shared/api/encounter.service';
import { EncounterSummary } from '../../shared/models/encounter.model';
import { AuthService } from '../../core/auth/auth.service';

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
        <option value="open">Open</option>
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
              <td><code class="id-code">{{ enc.patient_id | slice:0:12 }}…</code></td>
              <td><code class="id-code">{{ enc.doctor_id | slice:0:12 }}…</code></td>
              <td>
                <span class="badge" [class]="'badge-' + enc.status">{{ enc.status }}</span>
              </td>
              <td>{{ enc.started_at | date:'dd MMM yyyy HH:mm' }}</td>
              <td><a [routerLink]="['/encounters', enc.encounter_id]" class="link">View →</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`.id-code { font-size:0.78rem; color:#64748b; } .link { color:#6366f1; text-decoration:none; font-weight:500; }`],
})
export class EncounterListComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly svc = inject(EncounterService);

  encounters = signal<EncounterSummary[]>([]);
  loading = signal(true);
  private statusFilter = '';

  ngOnInit(): void { this.load(); }

  onStatusChange(status: string): void {
    this.statusFilter = status;
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.svc.list(undefined, this.statusFilter || undefined).subscribe({
      next: r => { this.encounters.set(r.items); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
