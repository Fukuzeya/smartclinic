import { Component, inject, signal, OnInit } from '@angular/core';
import { forkJoin, catchError, of } from 'rxjs';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { PatientService } from '../../shared/api/patient.service';
import { AppointmentService } from '../../shared/api/appointment.service';
import { EncounterService } from '../../shared/api/encounter.service';
import { LabOrderService } from '../../shared/api/lab-order.service';
import { InvoiceService } from '../../shared/api/invoice.service';
import { PrescriptionService } from '../../shared/api/prescription.service';
import { StockService } from '../../shared/api/stock.service';

interface StatCard {
  label: string;
  value: number | string;
  sub?: string;
  iconColor: string;
  iconBg: string;
  svgPath: string;
  link?: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink],
  template: `
    <!-- Page header -->
    <div class="dash-header">
      <div class="dash-title-block">
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">{{ today() }}</p>
      </div>
      <div class="dash-user-badge">
        <div class="dub-avatar">{{ (auth.profile()?.username ?? 'U')[0].toUpperCase() }}</div>
        <div class="dub-text">
          <span class="dub-name">{{ greeting() }}, {{ auth.profile()?.username }}</span>
          <span class="dub-role">{{ primaryRole() }}</span>
        </div>
      </div>
    </div>

    <!-- Stat strip -->
    <div class="stat-strip">
      @for (card of stats(); track card.label) {
        @if (card.link) {
          <a [routerLink]="card.link" class="stat-tile">
            <div class="st-icon" [style.background]="card.iconBg" [style.color]="card.iconColor">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path [attr.d]="card.svgPath"/>
              </svg>
            </div>
            <div class="st-body">
              <div class="st-value">{{ card.value }}</div>
              <div class="st-label">{{ card.label }}</div>
              @if (card.sub) { <div class="st-sub">{{ card.sub }}</div> }
            </div>
            <svg class="st-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
          </a>
        } @else {
          <div class="stat-tile">
            <div class="st-icon" [style.background]="card.iconBg" [style.color]="card.iconColor">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path [attr.d]="card.svgPath"/>
              </svg>
            </div>
            <div class="st-body">
              <div class="st-value">{{ card.value }}</div>
              <div class="st-label">{{ card.label }}</div>
              @if (card.sub) { <div class="st-sub">{{ card.sub }}</div> }
            </div>
          </div>
        }
      }
    </div>

    <!-- Quick launch panel -->
    <div class="panel-section">
      <div class="panel-heading">
        <h2 class="panel-title">Quick Actions</h2>
        <span class="panel-rule"></span>
      </div>
      <div class="launch-grid">

        @if (auth.isReceptionist()) {
          <a routerLink="/patients/new" class="launch-item">
            <div class="li-icon" style="background:#E8F1FC;color:#1255A1">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
            </div>
            <div class="li-body">
              <div class="li-label">Register Patient</div>
              <div class="li-desc">New demographic record</div>
            </div>
            <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>

          <a routerLink="/appointments/new" class="launch-item">
            <div class="li-icon" style="background:#E0F7F4;color:#0F766E">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            </div>
            <div class="li-body">
              <div class="li-label">Book Appointment</div>
              <div class="li-desc">Schedule a consultation slot</div>
            </div>
            <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>
        }

        @if (auth.isDoctor()) {
          <a routerLink="/encounters/new" class="launch-item">
            <div class="li-icon" style="background:#E8F1FC;color:#1255A1">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4.5 12.5l3 3 5-6"/><circle cx="12" cy="12" r="9"/></svg>
            </div>
            <div class="li-body">
              <div class="li-label">Start Encounter</div>
              <div class="li-desc">Open a new clinical consultation</div>
            </div>
            <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>
        }

        @if (auth.hasRole('lab_technician')) {
          <a routerLink="/lab-orders" class="launch-item">
            <div class="li-icon" style="background:#FFF8E6;color:#B45309">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 3h6v5l4 13H5L9 8V3z"/><line x1="9" y1="3" x2="15" y2="3"/></svg>
            </div>
            <div class="li-body">
              <div class="li-label">Lab Worklist</div>
              <div class="li-desc">Process pending samples</div>
            </div>
            <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>
        }

        @if (auth.hasRole('pharmacist')) {
          <a routerLink="/prescriptions" class="launch-item">
            <div class="li-icon" style="background:#F3F0FF;color:#5B21B6">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
            </div>
            <div class="li-body">
              <div class="li-label">Dispense Queue</div>
              <div class="li-desc">Pending prescriptions</div>
            </div>
            <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>

          <a routerLink="/stock" class="launch-item">
            <div class="li-icon" style="background:#E8F1FC;color:#1255A1">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
            </div>
            <div class="li-body">
              <div class="li-label">Drug Stock</div>
              <div class="li-desc">Manage inventory &amp; reorders</div>
            </div>
            <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>
        }

        @if (auth.hasRole('accounts')) {
          <a routerLink="/invoices" class="launch-item">
            <div class="li-icon" style="background:#ECFDF5;color:#065F46">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
            </div>
            <div class="li-body">
              <div class="li-label">Billing Queue</div>
              <div class="li-desc">Unpaid invoices</div>
            </div>
            <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </a>
        }

        <a routerLink="/visit-tracker" class="launch-item">
          <div class="li-icon" style="background:#EFF6FF;color:#1D4ED8">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3"/></svg>
          </div>
          <div class="li-body">
            <div class="li-label">Visit Tracker</div>
            <div class="li-desc">Live patient journey / saga state</div>
          </div>
          <svg class="li-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
        </a>

      </div>
    </div>
  `,
  styles: [`
    /* ── Header ── */
    .dash-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 28px;
      flex-wrap: wrap;
      gap: 12px;
    }
    .dash-user-badge {
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--clr-surface);
      border: 1px solid var(--clr-gray-200);
      border-radius: var(--radius-md);
      padding: 8px 14px;
    }
    .dub-avatar {
      width: 32px; height: 32px;
      border-radius: 50%;
      background: var(--clr-brand);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: .8rem;
      flex-shrink: 0;
    }
    .dub-text { display: flex; flex-direction: column; line-height: 1.25; }
    .dub-name { font-size: .825rem; font-weight: 600; color: var(--clr-gray-800); }
    .dub-role { font-size: .7rem; color: var(--clr-gray-500); text-transform: capitalize; }

    /* ── Stat strip ── */
    .stat-strip {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 14px;
      margin-bottom: 32px;
    }
    .stat-tile {
      background: var(--clr-surface);
      border: 1px solid var(--clr-gray-200);
      border-radius: var(--radius-md);
      padding: 16px 18px;
      display: flex;
      align-items: center;
      gap: 14px;
      text-decoration: none;
      color: inherit;
      box-shadow: var(--shadow-xs);
      transition: box-shadow .15s, border-color .15s;
      cursor: default;

      &[href], &[routerLink] {
        cursor: pointer;
        &:hover {
          box-shadow: var(--shadow-sm);
          border-color: var(--clr-accent);
        }
      }
    }
    .st-icon {
      width: 40px; height: 40px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .st-body { flex: 1; min-width: 0; }
    .st-value {
      font-size: 1.65rem;
      font-weight: 700;
      line-height: 1;
      letter-spacing: -.025em;
      color: var(--clr-gray-900);
    }
    .st-label {
      font-size: .7rem;
      font-weight: 600;
      color: var(--clr-gray-500);
      text-transform: uppercase;
      letter-spacing: .07em;
      margin-top: 5px;
    }
    .st-sub {
      font-size: .7rem;
      color: var(--clr-gray-400);
      margin-top: 2px;
    }
    .st-arrow {
      color: var(--clr-gray-300);
      flex-shrink: 0;
    }

    /* ── Quick launch ── */
    .panel-section { }
    .panel-heading {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    .panel-title {
      font-size: .75rem;
      font-weight: 700;
      color: var(--clr-gray-500);
      text-transform: uppercase;
      letter-spacing: .1em;
      white-space: nowrap;
    }
    .panel-rule {
      flex: 1;
      height: 1px;
      background: var(--clr-gray-200);
    }
    .launch-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 10px;
    }
    .launch-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      background: var(--clr-surface);
      border: 1px solid var(--clr-gray-200);
      border-radius: var(--radius-md);
      text-decoration: none;
      color: var(--clr-gray-800);
      transition: border-color .13s, box-shadow .13s, background .13s;

      &:hover {
        border-color: var(--clr-brand);
        background: var(--clr-brand-light);
        box-shadow: 0 0 0 3px rgba(18,85,161,.07);

        .li-arrow { color: var(--clr-brand); }
      }
    }
    .li-icon {
      width: 36px; height: 36px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .li-body { flex: 1; min-width: 0; }
    .li-label {
      font-size: .85rem;
      font-weight: 600;
      color: var(--clr-gray-800);
      line-height: 1.2;
    }
    .li-desc {
      font-size: .75rem;
      color: var(--clr-gray-500);
      margin-top: 2px;
    }
    .li-arrow { color: var(--clr-gray-300); flex-shrink: 0; transition: color .12s; }
  `],
})
export class DashboardComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly patientSvc = inject(PatientService);
  private readonly apptSvc = inject(AppointmentService);
  private readonly encounterSvc = inject(EncounterService);
  private readonly labSvc = inject(LabOrderService);
  private readonly invoiceSvc = inject(InvoiceService);
  private readonly rxSvc = inject(PrescriptionService);
  private readonly stockSvc = inject(StockService);

  stats = signal<StatCard[]>([]);

  greeting(): string {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  today(): string {
    return new Date().toLocaleDateString('en-GB', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    });
  }

  primaryRole(): string {
    const roles = this.auth.profile()?.roles;
    if (!roles) return '';
    for (const r of ['doctor', 'receptionist', 'pharmacist', 'accounts', 'lab_technician']) {
      if (roles.has(r)) return r.replace('_', ' ');
    }
    return '';
  }

  ngOnInit(): void {
    const todayStr = new Date().toISOString().split('T')[0];

    if (this.auth.hasRole('pharmacist')) {
      this._loadPharmacistStats();
    } else if (this.auth.hasRole('lab_technician')) {
      this._loadLabStats();
    } else if (this.auth.hasRole('accounts')) {
      this._loadAccountsStats();
    } else {
      this._loadDefaultStats(todayStr);
    }
  }

  private _loadPharmacistStats(): void {
    forkJoin({
      rxPending:  this.rxSvc.list(undefined, 'pending', 1, 0).pipe(catchError(() => of({ total: 0 }))),
      rxPartial:  this.rxSvc.list(undefined, 'partially_dispensed', 1, 0).pipe(catchError(() => of({ total: 0 }))),
      rxAll:      this.rxSvc.list(undefined, undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      stockAll:   this.stockSvc.list(false).pipe(catchError(() => of({ total: 0 }))),
      stockLow:   this.stockSvc.list(true).pipe(catchError(() => of({ total: 0 }))),
    }).subscribe(({ rxPending, rxPartial, rxAll, stockAll, stockLow }) => {
      this.stats.set([
        {
          label: 'Pending Prescriptions',
          value: (rxPending as any).total ?? '–',
          sub: 'Awaiting dispensing',
          iconColor: '#B45309', iconBg: '#FFF8E6',
          svgPath: 'M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2zM12 8v8M8 12h8',
          link: '/prescriptions',
        },
        {
          label: 'Partially Dispensed',
          value: (rxPartial as any).total ?? '–',
          iconColor: '#5B21B6', iconBg: '#F3F0FF',
          svgPath: 'M12 2v20M2 12h20',
          link: '/prescriptions',
        },
        {
          label: 'Total Prescriptions',
          value: (rxAll as any).total ?? '–',
          iconColor: '#15803d', iconBg: '#DCFCE7',
          svgPath: 'M4.5 12.5l3 3 5-6M12 3a9 9 0 1 0 0 18A9 9 0 0 0 12 3z',
          link: '/prescriptions',
        },
        {
          label: 'Drugs in Stock',
          value: (stockAll as any).total ?? '–',
          iconColor: '#1255A1', iconBg: '#E8F1FC',
          svgPath: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
          link: '/stock',
        },
        {
          label: 'Low / Out of Stock',
          value: (stockLow as any).total ?? '–',
          sub: 'Needs reorder',
          iconColor: '#DC2626', iconBg: '#FEE2E2',
          svgPath: 'M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z',
          link: '/stock',
        },
      ]);
    });
  }

  private _loadLabStats(): void {
    forkJoin({
      labPending:   this.labSvc.list(undefined, 'pending', undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      labCollected: this.labSvc.list(undefined, 'sample_collected', undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      labProgress:  this.labSvc.list(undefined, 'in_progress', undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      labCompleted: this.labSvc.list(undefined, 'completed', undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      labAll:       this.labSvc.list(undefined, undefined, undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
    }).subscribe(({ labPending, labCollected, labProgress, labCompleted, labAll }) => {
      this.stats.set([
        {
          label: 'Pending Orders',
          value: (labPending as any).total ?? '–',
          sub: 'Awaiting sample collection',
          iconColor: '#B45309', iconBg: '#FFF8E6',
          svgPath: 'M9 3h6v5l4 13H5L9 8V3z',
          link: '/lab-orders',
        },
        {
          label: 'Samples Collected',
          value: (labCollected as any).total ?? '–',
          sub: 'Ready for testing',
          iconColor: '#1D4ED8', iconBg: '#DBEAFE',
          svgPath: 'M9 3h6v5l4 13H5L9 8V3z',
          link: '/lab-orders',
        },
        {
          label: 'In Progress',
          value: (labProgress as any).total ?? '–',
          sub: 'Results being entered',
          iconColor: '#5B21B6', iconBg: '#F3F0FF',
          svgPath: 'M9 3h6v5l4 13H5L9 8V3z',
          link: '/lab-orders',
        },
        {
          label: 'Completed Today',
          value: (labCompleted as any).total ?? '–',
          iconColor: '#15803d', iconBg: '#DCFCE7',
          svgPath: 'M4.5 12.5l3 3 5-6M12 3a9 9 0 1 0 0 18A9 9 0 0 0 12 3z',
          link: '/lab-orders',
        },
        {
          label: 'Total Orders',
          value: (labAll as any).total ?? '–',
          iconColor: '#1255A1', iconBg: '#E8F1FC',
          svgPath: 'M9 3h6v5l4 13H5L9 8V3z',
          link: '/lab-orders',
        },
      ]);
    });
  }

  private _loadAccountsStats(): void {
    forkJoin({
      invoicesOpen: this.invoiceSvc.list(undefined, undefined, 'issued', 1, 0).pipe(catchError(() => of({ total: 0 }))),
      invoicesAll:  this.invoiceSvc.list(undefined, undefined, undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
    }).subscribe(({ invoicesOpen, invoicesAll }) => {
      this.stats.set([
        {
          label: 'Unpaid Invoices',
          value: (invoicesOpen as any).total ?? '–',
          sub: 'Awaiting payment',
          iconColor: '#DC2626', iconBg: '#FEE2E2',
          svgPath: 'M2 9h20M2 5h20a0 0 0 0 1 0 0v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z',
          link: '/invoices',
        },
        {
          label: 'Total Invoices',
          value: (invoicesAll as any).total ?? '–',
          iconColor: '#065F46', iconBg: '#ECFDF5',
          svgPath: 'M2 9h20M2 5h20a0 0 0 0 1 0 0v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z',
          link: '/invoices',
        },
      ]);
    });
  }

  private _loadDefaultStats(todayStr: string): void {
    forkJoin({
      patients:     this.patientSvc.search('', 1, 0).pipe(catchError(() => of({ total: 0 }))),
      appts:        this.apptSvc.list(undefined, todayStr, undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      encounters:   this.encounterSvc.list(undefined, 'in_progress', 1, 0).pipe(catchError(() => of({ total: 0 }))),
      labPending:   this.labSvc.list(undefined, 'pending', undefined, 1, 0).pipe(catchError(() => of({ total: 0 }))),
      invoicesOpen: this.invoiceSvc.list(undefined, undefined, 'issued', 1, 0).pipe(catchError(() => of({ total: 0 }))),
    }).subscribe(({ patients, appts, encounters, labPending, invoicesOpen }) => {
      this.stats.set([
        {
          label: 'Total Patients',
          value: (patients as any).total ?? '–',
          iconColor: '#1255A1', iconBg: '#E8F1FC',
          svgPath: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
          link: '/patients',
        },
        {
          label: "Today's Appointments",
          value: (appts as any).total ?? '–',
          sub: todayStr,
          iconColor: '#0F766E', iconBg: '#E0F7F4',
          svgPath: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z',
          link: '/appointments',
        },
        {
          label: 'Open Encounters',
          value: (encounters as any).total ?? '–',
          iconColor: '#15803d', iconBg: '#DCFCE7',
          svgPath: 'M4.5 12.5l3 3 5-6M12 3a9 9 0 1 0 0 18A9 9 0 0 0 12 3z',
          link: '/encounters',
        },
        {
          label: 'Lab Pending',
          value: (labPending as any).total ?? '–',
          iconColor: '#B45309', iconBg: '#FFF8E6',
          svgPath: 'M9 3h6v5l4 13H5L9 8V3z',
          link: '/lab-orders',
        },
        {
          label: 'Unpaid Invoices',
          value: (invoicesOpen as any).total ?? '–',
          iconColor: '#DC2626', iconBg: '#FEE2E2',
          svgPath: 'M2 9h20M2 5h20a0 0 0 0 1 0 0v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z',
          link: '/invoices',
        },
      ]);
    });
  }
}
