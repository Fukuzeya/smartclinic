import { Component, inject, signal, OnInit } from '@angular/core';
import { forkJoin, catchError, of } from 'rxjs';
import { RouterLink } from '@angular/router';
import { NgTemplateOutlet } from '@angular/common';
import { AuthService } from '../../core/auth/auth.service';
import { PatientService } from '../../shared/api/patient.service';
import { AppointmentService } from '../../shared/api/appointment.service';
import { EncounterService } from '../../shared/api/encounter.service';
import { LabOrderService } from '../../shared/api/lab-order.service';
import { InvoiceService } from '../../shared/api/invoice.service';

interface StatCard {
  label: string;
  value: number | string;
  sub?: string;
  icon: string;
  color: string;
  link?: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, NgTemplateOutlet],
  template: `
    <div class="page-header">
      <h1 class="page-title">Dashboard</h1>
      <p class="page-subtitle">{{ greeting() }}, {{ auth.profile()?.username }}</p>
    </div>

    <div class="stats-grid">
      @for (card of stats(); track card.label) {
        <div class="stat-card" [style.border-left-color]="card.color">
          @if (card.link) {
            <a [routerLink]="card.link" class="stat-link">
              <ng-container *ngTemplateOutlet="cardContent; context: { card: card }" />
            </a>
          } @else {
            <ng-container *ngTemplateOutlet="cardContent; context: { card: card }" />
          }
        </div>
      }
    </div>

    <ng-template #cardContent let-card="card">
      <div class="stat-icon" [style.color]="card.color">{{ card.icon }}</div>
      <div class="stat-body">
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
        @if (card.sub) { <div class="stat-sub">{{ card.sub }}</div> }
      </div>
    </ng-template>

    <div class="quick-actions">
      <h2 class="section-title">Quick Actions</h2>
      <div class="action-grid">
        @if (auth.isReceptionist() || auth.isDoctor()) {
          <a routerLink="/patients/new" class="action-card">
            <span class="action-icon">👤</span>
            <span>Register Patient</span>
          </a>
          <a routerLink="/appointments/new" class="action-card">
            <span class="action-icon">📅</span>
            <span>Book Appointment</span>
          </a>
        }
        @if (auth.isDoctor()) {
          <a routerLink="/encounters/new" class="action-card">
            <span class="action-icon">🩺</span>
            <span>Start Encounter</span>
          </a>
        }
        @if (auth.hasRole('lab_technician')) {
          <a routerLink="/lab-orders" class="action-card">
            <span class="action-icon">🧪</span>
            <span>Lab Worklist</span>
          </a>
        }
        @if (auth.hasRole('pharmacist')) {
          <a routerLink="/prescriptions" class="action-card">
            <span class="action-icon">💊</span>
            <span>Dispense Queue</span>
          </a>
        }
        @if (auth.hasRole('accounts')) {
          <a routerLink="/invoices" class="action-card">
            <span class="action-icon">💵</span>
            <span>Billing Queue</span>
          </a>
        }
        <a routerLink="/visit-tracker" class="action-card">
          <span class="action-icon">🗺️</span>
          <span>Visit Tracker</span>
        </a>
      </div>
    </div>
  `,
  styles: [`
    .page-header { margin-bottom: 28px; }
    .page-subtitle { color: #64748b; margin-top: 4px; }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }
    .stat-card {
      background: #fff;
      border-radius: 10px;
      padding: 20px;
      border-left: 4px solid #cbd5e1;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .stat-link { display: flex; align-items: center; gap: 16px; text-decoration: none; color: inherit; width: 100%; }
    .stat-icon { font-size: 2rem; }
    .stat-value { font-size: 1.75rem; font-weight: 700; line-height: 1; }
    .stat-label { font-size: 0.8rem; color: #64748b; margin-top: 4px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-sub { font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }

    .section-title { font-size: 1rem; font-weight: 600; color: #334155; margin-bottom: 16px; }
    .action-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 12px;
    }
    .action-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      padding: 20px 16px;
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      text-decoration: none;
      color: #334155;
      font-size: 0.9rem;
      font-weight: 500;
      transition: all 0.15s;
      cursor: pointer;
    }
    .action-card:hover { border-color: #6366f1; background: #f0f0ff; color: #6366f1; }
    .action-icon { font-size: 1.75rem; }
  `],
})
export class DashboardComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly patientSvc = inject(PatientService);
  private readonly apptSvc = inject(AppointmentService);
  private readonly encounterSvc = inject(EncounterService);
  private readonly labSvc = inject(LabOrderService);
  private readonly invoiceSvc = inject(InvoiceService);

  stats = signal<StatCard[]>([]);

  greeting(): string {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  ngOnInit(): void {
    const today = new Date().toISOString().split('T')[0];
    forkJoin({
      patients: this.patientSvc.search('', 1, 0).pipe(catchError(() => of({ total: 0 }))),
      appts: this.apptSvc.list(undefined, today, undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      encounters: this.encounterSvc.list(undefined, 'open', 1, 0).pipe(catchError(() => of({ total: 0 }))),
      labPending: this.labSvc.list(undefined, 'pending', undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      invoicesOpen: this.invoiceSvc.list(undefined, undefined, 'issued', 1, 0).pipe(catchError(() => of({ total: 0 }))),
    }).subscribe(({ patients, appts, encounters, labPending, invoicesOpen }) => {
      this.stats.set([
        { label: 'Patients', value: (patients as any).total ?? '–', icon: '👤', color: '#6366f1', link: '/patients' },
        { label: "Today's Appointments", value: (appts as any).total ?? '–', icon: '📅', color: '#0ea5e9', link: '/appointments', sub: today },
        { label: 'Open Encounters', value: (encounters as any).total ?? '–', icon: '🩺', color: '#10b981', link: '/encounters' },
        { label: 'Lab Pending', value: (labPending as any).total ?? '–', icon: '🧪', color: '#f59e0b', link: '/lab-orders' },
        { label: 'Unpaid Invoices', value: (invoicesOpen as any).total ?? '–', icon: '💵', color: '#ef4444', link: '/invoices' },
      ]);
    });
  }
}
