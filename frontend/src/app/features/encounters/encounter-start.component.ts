import { Component, inject, signal, OnInit } from '@angular/core';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { debounceTime, distinctUntilChanged, Subject, switchMap, catchError, of, forkJoin } from 'rxjs';
import { EncounterService } from '../../shared/api/encounter.service';
import { PatientService } from '../../shared/api/patient.service';
import { AppointmentService } from '../../shared/api/appointment.service';
import { PatientSummary } from '../../shared/models/patient.model';
import { Appointment } from '../../shared/models/appointment.model';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-encounter-start',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Start Encounter</h1>
        <p class="page-subtitle">Open a new clinical consultation record</p>
      </div>
      <a routerLink="/encounters" class="btn-secondary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        Back
      </a>
    </div>

    <div class="start-layout">
      <!-- Left: form -->
      <form [formGroup]="form" (ngSubmit)="submit()" class="form-layout">
        <div class="card form-section">
          <div class="form-section-header">
            <div class="form-section-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
            <div>
              <div class="form-section-title">Select Patient</div>
              <div class="form-section-sub">Search by name to find the patient</div>
            </div>
          </div>

          <div class="form-group">
            <label>Patient <span class="req">*</span></label>
            @if (!selectedPatient()) {
              <div class="search-wrap">
                <svg class="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input
                  class="form-control search-input"
                  type="search"
                  placeholder="Type patient name to search…"
                  [value]="patientSearchTerm()"
                  (input)="onPatientSearch($any($event.target).value)"
                  (focus)="showPatientDropdown.set(true)"
                  (blur)="onSearchBlur()"
                />
              </div>

              @if (showPatientDropdown() && patientResults().length > 0) {
                <div class="dropdown">
                  @for (p of patientResults(); track p.patient_id) {
                    <button type="button" class="dropdown-item" (mousedown)="$event.preventDefault()" (click)="selectPatient(p)">
                      <div class="dropdown-avatar">{{ p.display_name[0] }}</div>
                      <div class="dropdown-info">
                        <div class="dropdown-name">{{ p.display_name }}</div>
                        <div class="dropdown-meta">{{ p.sex }} · DOB {{ p.date_of_birth }}</div>
                      </div>
                    </button>
                  }
                </div>
              }
              @if (showPatientDropdown() && patientSearchTerm().length >= 2 && patientResults().length === 0 && !patientSearching()) {
                <div class="dropdown"><div class="dropdown-empty">No patients found</div></div>
              }
            }

            @if (selectedPatient()) {
              <div class="selected-chip">
                <div class="chip-avatar">{{ selectedPatient()!.display_name[0] }}</div>
                <div class="chip-info">
                  <strong>{{ selectedPatient()!.display_name }}</strong>
                  <span>{{ selectedPatient()!.sex }} · DOB {{ selectedPatient()!.date_of_birth }}</span>
                </div>
                <button type="button" class="chip-remove" (click)="clearPatient()" title="Change patient">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
            }

            @if (form.controls['patient_id'].invalid && form.controls['patient_id'].touched) {
              <span class="field-error">Please select a patient</span>
            }
          </div>
        </div>

        <!-- Appointment linking -->
        <div class="card form-section">
          <div class="form-section-header">
            <div class="form-section-icon appt-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            </div>
            <div>
              <div class="form-section-title">Link Appointment <span class="optional-tag">optional</span></div>
              <div class="form-section-sub">Connect this encounter to a checked-in appointment</div>
            </div>
          </div>

          @if (patientAppointments().length > 0) {
            <div class="appt-list">
              @for (a of patientAppointments(); track a.appointment_id) {
                <button type="button"
                        [class]="'appt-card' + (form.value.appointment_id === a.appointment_id ? ' appt-selected' : '')"
                        (click)="selectAppointment(a)">
                  <div class="appt-card-status">
                    <span [class]="'badge badge-' + a.status">{{ a.status }}</span>
                  </div>
                  <div class="appt-card-time">{{ a.start_at.substring(11, 16) }}</div>
                  <div class="appt-card-date">{{ a.start_at.substring(0, 10) }}</div>
                  @if (a.reason) {
                    <div class="appt-card-reason">{{ a.reason }}</div>
                  }
                  @if (form.value.appointment_id === a.appointment_id) {
                    <div class="appt-check">✓</div>
                  }
                </button>
              }
            </div>
          } @else if (selectedPatient()) {
            <div class="empty-appts">No recent appointments for this patient.</div>
          } @else {
            <div class="empty-appts">Select a patient first to see their appointments.</div>
          }
        </div>

        @if (error()) {
          <div class="alert-error">{{ error() }}</div>
        }

        <div class="form-actions">
          <button type="submit" class="btn-primary" [disabled]="form.invalid || loading()">
            @if (loading()) {
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="spin"><path d="M21 12a9 9 0 0 1-9 9"/></svg>
              Starting…
            } @else {
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Start Encounter
            }
          </button>
          <a routerLink="/encounters" class="btn-secondary">Cancel</a>
        </div>
      </form>

      <!-- Right: today's checked-in patients quick-pick -->
      <div class="sidebar">
        <div class="card">
          <h3 class="sidebar-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            Today's Checked-In
          </h3>
          @if (todayAppointments().length > 0) {
            <div class="today-list">
              @for (a of todayAppointments(); track a.appointment_id) {
                <button type="button" class="today-item" (click)="pickFromToday(a)">
                  <div class="today-time">{{ a.start_at.substring(11, 16) }}</div>
                  <div class="today-info">
                    <div class="today-patient-name">{{ patientNameMap()[a.patient_id] || 'Loading…' }}</div>
                    @if (a.reason) {
                      <div class="today-reason">{{ a.reason }}</div>
                    }
                  </div>
                  <span class="badge badge-checked_in" style="font-size:.65rem">checked in</span>
                </button>
              }
            </div>
          } @else {
            <div class="empty-appts">No checked-in appointments today.</div>
          }
        </div>
      </div>
    </div>
  `,
  styles: [`
    .start-layout { display: grid; grid-template-columns: 1fr 300px; gap: 20px; align-items: start; }
    @media (max-width: 900px) { .start-layout { grid-template-columns: 1fr; } }
    .form-layout { display: flex; flex-direction: column; gap: 20px; }
    .form-section { padding: 24px; }
    .form-section-header {
      display: flex; align-items: flex-start; gap: 12px;
      margin-bottom: 20px; padding-bottom: 16px;
      border-bottom: 1px solid var(--clr-gray-100);
    }
    .form-section-icon {
      width: 36px; height: 36px; border-radius: 8px;
      background: #ecfdf5; color: #10b981;
      display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    }
    .appt-icon { background: #eff6ff; color: #3b82f6; }
    .form-section-title { font-weight: 600; font-size: .95rem; }
    .form-section-sub { font-size: .8rem; color: var(--clr-gray-500); margin-top: 2px; }
    .req { color: var(--clr-danger); }
    .optional-tag { font-size: .75rem; color: var(--clr-gray-400); font-weight: 400; margin-left: 4px; }
    .form-actions { display: flex; gap: 12px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .spin { animation: spin .65s linear infinite; }

    /* Search */
    .search-wrap { position: relative; }
    .search-icon { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); color: var(--clr-gray-400); pointer-events: none; }
    .search-input { padding-left: 36px !important; }

    /* Dropdown */
    .dropdown {
      position: absolute; z-index: 50; width: 100%;
      background: #fff; border: 1px solid var(--clr-gray-200);
      border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,.12);
      max-height: 240px; overflow-y: auto; margin-top: 4px;
    }
    .dropdown-item {
      display: flex; align-items: center; gap: 10px;
      width: 100%; padding: 10px 14px; border: none; background: none;
      cursor: pointer; text-align: left; font-family: inherit;
      transition: background .1s;
    }
    .dropdown-item:hover { background: var(--clr-brand-light); }
    .dropdown-avatar {
      width: 32px; height: 32px; border-radius: 50%;
      background: var(--clr-brand); color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: .8rem; flex-shrink: 0;
    }
    .dropdown-name { font-weight: 600; font-size: .875rem; color: var(--clr-gray-800); }
    .dropdown-meta { font-size: .75rem; color: var(--clr-gray-500); }
    .dropdown-empty { padding: 14px; color: var(--clr-gray-400); font-size: .85rem; text-align: center; }

    /* Selected patient chip */
    .selected-chip {
      display: flex; align-items: center; gap: 10px;
      margin-top: 10px; padding: 10px 14px;
      background: #ecfdf5; border: 1px solid #6ee7b7;
      border-radius: 8px;
    }
    .chip-avatar {
      width: 36px; height: 36px; border-radius: 50%;
      background: #10b981; color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: .85rem; flex-shrink: 0;
    }
    .chip-info { flex: 1; }
    .chip-info strong { display: block; font-size: .9rem; color: #065f46; }
    .chip-info span { font-size: .78rem; color: #047857; }
    .chip-remove {
      background: none; border: none; cursor: pointer; color: #047857; padding: 4px;
      border-radius: 4px; display: flex; align-items: center;
    }
    .chip-remove:hover { background: rgba(0,0,0,.08); }

    /* Appointment cards */
    .appt-list { display: flex; flex-direction: column; gap: 8px; }
    .appt-card {
      display: flex; align-items: center; gap: 12px;
      width: 100%; padding: 12px 14px; border: 1px solid var(--clr-gray-200);
      border-radius: 8px; background: #fff; cursor: pointer;
      font-family: inherit; text-align: left;
      transition: border-color .12s, background .12s;
    }
    .appt-card:hover { border-color: var(--clr-brand); background: var(--clr-brand-light); }
    .appt-selected { border-color: #10b981 !important; background: #ecfdf5 !important; }
    .appt-card-time { font-size: 1rem; font-weight: 700; color: var(--clr-gray-800); }
    .appt-card-date { font-size: .78rem; color: var(--clr-gray-500); }
    .appt-card-reason { font-size: .78rem; color: var(--clr-gray-500); flex: 1; }
    .appt-check { color: #10b981; font-weight: 700; font-size: 1.1rem; margin-left: auto; }
    .empty-appts { color: var(--clr-gray-400); font-size: .85rem; padding: 8px 0; }

    /* Sidebar */
    .sidebar { position: sticky; top: calc(var(--header-h, 56px) + 16px); }
    .sidebar-title {
      font-size: .8rem; font-weight: 700; color: var(--clr-gray-600);
      text-transform: uppercase; letter-spacing: .05em;
      display: flex; align-items: center; gap: 6px;
      margin-bottom: 12px;
    }
    .today-list { display: flex; flex-direction: column; gap: 6px; }
    .today-item {
      display: flex; align-items: center; gap: 10px;
      width: 100%; padding: 10px 12px; border: 1px solid var(--clr-gray-200);
      border-radius: 6px; background: #fff; cursor: pointer;
      font-family: inherit; text-align: left;
      transition: border-color .12s, background .12s;
    }
    .today-item:hover { border-color: var(--clr-brand); background: var(--clr-brand-light); }
    .today-time { font-weight: 700; font-size: .9rem; color: var(--clr-gray-800); white-space: nowrap; }
    .today-patient-name { font-size: .82rem; color: var(--clr-gray-800); font-weight: 600; }
    .today-reason { font-size: .72rem; color: var(--clr-gray-400); }
    .form-group { position: relative; }
  `],
})
export class EncounterStartComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly svc = inject(EncounterService);
  private readonly patientSvc = inject(PatientService);
  private readonly apptSvc = inject(AppointmentService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  loading = signal(false);
  error = signal('');

  // Patient search
  patientSearchTerm = signal('');
  patientResults = signal<PatientSummary[]>([]);
  patientSearching = signal(false);
  showPatientDropdown = signal(false);
  selectedPatient = signal<PatientSummary | null>(null);
  private readonly patientSearch$ = new Subject<string>();

  // Appointments for selected patient
  patientAppointments = signal<Appointment[]>([]);

  // Today's checked-in appointments for this doctor
  todayAppointments = signal<Appointment[]>([]);
  patientNameMap = signal<Record<string, string>>({});

  form = this.fb.group({
    patient_id: ['', Validators.required],
    appointment_id: [''],
  });

  ngOnInit(): void {
    // Wire up debounced patient search
    this.patientSearch$.pipe(
      debounceTime(300),
      distinctUntilChanged(),
      switchMap(term => {
        if (term.length < 2) { this.patientResults.set([]); return of(null); }
        this.patientSearching.set(true);
        return this.patientSvc.search(term, 8, 0).pipe(catchError(() => of({ items: [] })));
      }),
    ).subscribe(resp => {
      if (resp) this.patientResults.set(resp.items);
      this.patientSearching.set(false);
    });

    // Load today's checked-in appointments for this doctor
    const todayStr = new Date().toISOString().split('T')[0];
    const doctorId = this.auth.profile()?.subject;
    if (doctorId) {
      this.apptSvc.list(undefined, todayStr, 'checked_in', 50, 0).pipe(
        catchError(() => of({ items: [] })),
      ).subscribe(resp => {
        this.todayAppointments.set(resp.items);
        this.resolvePatientNames(resp.items);
      });
    }

    // Check for pre-filled query params (from appointment detail)
    const qp = this.route.snapshot.queryParams;
    if (qp['patient_id']) {
      this.form.patchValue({ patient_id: qp['patient_id'] });
      // Load patient details to show name
      this.patientSvc.get(qp['patient_id']).pipe(catchError(() => of(null))).subscribe(p => {
        if (p) {
          this.selectedPatient.set({
            patient_id: p.patient_id,
            display_name: p.display_name,
            date_of_birth: p.date_of_birth,
            sex: p.sex,
            has_email: !!p.email,
            has_phone: !!p.phone,
          });
          this.loadPatientAppointments(p.patient_id);
        }
      });
    }
    if (qp['appointment_id']) {
      this.form.patchValue({ appointment_id: qp['appointment_id'] });
    }
  }

  onSearchBlur(): void {
    // Delay to allow dropdown click events to fire before hiding
    setTimeout(() => this.showPatientDropdown.set(false), 200);
  }

  onPatientSearch(term: string): void {
    this.patientSearchTerm.set(term);
    this.showPatientDropdown.set(true);
    // If they clear while a patient is selected, unselect
    if (this.selectedPatient() && term !== this.selectedPatient()!.display_name) {
      this.clearPatient();
    }
    this.patientSearch$.next(term);
  }

  selectPatient(p: PatientSummary): void {
    this.selectedPatient.set(p);
    this.form.patchValue({ patient_id: p.patient_id });
    this.patientSearchTerm.set(p.display_name);
    this.showPatientDropdown.set(false);
    this.patientResults.set([]);
    this.loadPatientAppointments(p.patient_id);
  }

  clearPatient(): void {
    this.selectedPatient.set(null);
    this.form.patchValue({ patient_id: '', appointment_id: '' });
    this.patientAppointments.set([]);
  }

  selectAppointment(a: Appointment): void {
    if (this.form.value.appointment_id === a.appointment_id) {
      this.form.patchValue({ appointment_id: '' });
    } else {
      this.form.patchValue({ appointment_id: a.appointment_id });
    }
  }

  pickFromToday(a: Appointment): void {
    // Load the patient for this appointment then select both
    this.form.patchValue({ patient_id: a.patient_id, appointment_id: a.appointment_id });
    this.patientSvc.get(a.patient_id).pipe(catchError(() => of(null))).subscribe(p => {
      if (p) {
        this.selectedPatient.set({
          patient_id: p.patient_id,
          display_name: p.display_name,
          date_of_birth: p.date_of_birth,
          sex: p.sex,
          has_email: !!p.email,
          has_phone: !!p.phone,
        });
        this.patientSearchTerm.set(p.display_name);
        this.loadPatientAppointments(p.patient_id);
      }
    });
  }

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');
    const { patient_id, appointment_id } = this.form.value;
    const doctor_id = this.auth.profile()?.subject;
    if (!doctor_id) { this.error.set('Unable to determine doctor identity'); this.loading.set(false); return; }
    this.svc.start({ patient_id: patient_id!, doctor_id, appointment_id: appointment_id || undefined }).subscribe({
      next: r => this.router.navigate(['/encounters', r.encounter_id]),
      error: e => { this.error.set(e.error?.detail ?? 'Failed to start encounter'); this.loading.set(false); },
    });
  }

  private loadPatientAppointments(patientId: string): void {
    this.apptSvc.list(patientId, undefined, undefined, 10, 0).pipe(
      catchError(() => of({ items: [] })),
    ).subscribe(resp => {
      this.patientAppointments.set(resp.items);
    });
  }

  private resolvePatientNames(appointments: Appointment[]): void {
    const uniqueIds = [...new Set(appointments.map(a => a.patient_id))];
    if (uniqueIds.length === 0) return;
    const requests = uniqueIds.reduce((acc, id) => {
      acc[id] = this.patientSvc.get(id).pipe(catchError(() => of(null)));
      return acc;
    }, {} as Record<string, any>);
    forkJoin(requests).subscribe((results: Record<string, any>) => {
      const nameMap: Record<string, string> = {};
      for (const [id, patient] of Object.entries(results)) {
        nameMap[id] = patient?.display_name ?? id.substring(0, 12) + '…';
      }
      this.patientNameMap.set(nameMap);
    });
  }
}
