import { Component, inject, signal, OnInit } from '@angular/core';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { AppointmentService } from '../../shared/api/appointment.service';
import { PatientService } from '../../shared/api/patient.service';
import { PatientSummary } from '../../shared/models/patient.model';
import { DoctorSummary } from '../../shared/models/appointment.model';
import { debounceTime, distinctUntilChanged, Subject, switchMap, catchError, of } from 'rxjs';

@Component({
  selector: 'app-appointment-book',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Book Appointment</h1>
        <p class="page-subtitle">Schedule a consultation slot</p>
      </div>
      <a routerLink="/appointments" class="btn-secondary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        Back
      </a>
    </div>

    @if (error()) {
      <div class="alert-error" style="margin-bottom:20px">{{ error() }}</div>
    }

    <form [formGroup]="form" (ngSubmit)="submit()" class="form-layout">

      <!-- Patient picker -->
      <div class="card form-section">
        <div class="form-section-header">
          <div class="form-section-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
          </div>
          <div>
            <div class="form-section-title">Patient</div>
            <div class="form-section-sub">Search and select the patient for this appointment</div>
          </div>
        </div>

        @if (!selectedPatient()) {
          <div class="form-group search-wrap">
            <label>Search patient <span class="req">*</span></label>
            <div class="search-field">
              <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input type="search" class="form-control search-input"
                     [value]="patientSearchTerm"
                     (input)="onPatientSearch($any($event.target).value)"
                     placeholder="Type at least 2 characters…"/>
            </div>
            @if (patientResults().length > 0) {
              <ul class="search-dropdown">
                @for (p of patientResults(); track p.patient_id) {
                  <li (click)="selectPatient(p)" class="search-option">
                    <div class="avatar-sm">{{ p.display_name[0] }}</div>
                    <div>
                      <div class="option-name">{{ p.display_name }}</div>
                      <div class="option-sub">DOB: {{ p.date_of_birth }} · {{ p.sex }}</div>
                    </div>
                  </li>
                }
              </ul>
            }
          </div>
        } @else {
          <div class="selected-card selected-card--patient">
            <div class="avatar avatar--patient">{{ selectedPatient()!.display_name[0] }}</div>
            <div class="selected-info">
              <div class="selected-name">{{ selectedPatient()!.display_name }}</div>
              <div class="selected-meta">DOB: {{ selectedPatient()!.date_of_birth }} · {{ selectedPatient()!.sex }}</div>
            </div>
            <button type="button" class="btn-secondary btn-sm" (click)="clearPatient()">Change</button>
          </div>
        }
      </div>

      <!-- Doctor picker -->
      <div class="card form-section">
        <div class="form-section-header">
          <div class="form-section-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          </div>
          <div>
            <div class="form-section-title">Doctor</div>
            <div class="form-section-sub">Search and select the consulting doctor</div>
          </div>
        </div>

        @if (!selectedDoctor()) {
          <div class="form-group search-wrap">
            <label>Search doctor <span class="req">*</span></label>
            <div class="search-field">
              <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input type="search" class="form-control search-input"
                     [value]="doctorSearchTerm"
                     (input)="onDoctorSearch($any($event.target).value)"
                     placeholder="Type a name or username…"/>
            </div>
            @if (doctorResults().length > 0) {
              <ul class="search-dropdown">
                @for (d of doctorResults(); track d.doctor_id) {
                  <li (click)="selectDoctor(d)" class="search-option">
                    <div class="avatar-sm avatar-sm--doctor">{{ (d.display_name || d.username)[0].toUpperCase() }}</div>
                    <div>
                      <div class="option-name">{{ d.display_name || d.username }}</div>
                      <div class="option-sub">{{ d.username }}{{ d.email ? ' · ' + d.email : '' }}</div>
                    </div>
                  </li>
                }
              </ul>
            }
            @if (doctorSearchTerm.length > 0 && doctorResults().length === 0 && !doctorSearching()) {
              <div class="no-results">No doctors found matching "{{ doctorSearchTerm }}"</div>
            }
          </div>
        } @else {
          <div class="selected-card selected-card--doctor">
            <div class="avatar avatar--doctor">{{ (selectedDoctor()!.display_name || selectedDoctor()!.username)[0].toUpperCase() }}</div>
            <div class="selected-info">
              <div class="selected-name">{{ selectedDoctor()!.display_name || selectedDoctor()!.username }}</div>
              <div class="selected-meta">{{ selectedDoctor()!.username }}{{ selectedDoctor()!.email ? ' · ' + selectedDoctor()!.email : '' }}</div>
            </div>
            <button type="button" class="btn-secondary btn-sm" (click)="clearDoctor()">Change</button>
          </div>
        }
      </div>

      <!-- Appointment details -->
      <div class="card form-section">
        <div class="form-section-header">
          <div class="form-section-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          </div>
          <div>
            <div class="form-section-title">Appointment Details</div>
            <div class="form-section-sub">Slot timing and visit reason</div>
          </div>
        </div>

        <div class="field-grid-2">
          <div class="form-group">
            <label for="start_at">Start time <span class="req">*</span></label>
            <input id="start_at" class="form-control" formControlName="start_at" type="datetime-local"/>
            @if (fc('start_at').invalid && fc('start_at').touched) {
              <span class="field-error">Required</span>
            }
          </div>
          <div class="form-group">
            <label for="end_at">End time <span class="req">*</span></label>
            <input id="end_at" class="form-control" formControlName="end_at" type="datetime-local"/>
            @if (fc('end_at').invalid && fc('end_at').touched) {
              <span class="field-error">Required</span>
            }
          </div>
        </div>

        <div class="form-group">
          <label for="reason">Reason for visit</label>
          <textarea id="reason" class="form-control" formControlName="reason" rows="3" placeholder="Optional — brief description of presenting concern"></textarea>
        </div>
      </div>

      <!-- Actions -->
      <div class="form-actions">
        <button type="submit" class="btn-primary" [disabled]="form.invalid || !selectedPatient() || !selectedDoctor() || submitting()">
          @if (submitting()) {
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="spin"><path d="M21 12a9 9 0 0 1-9 9"/></svg>
            Booking…
          } @else {
            Book Appointment
          }
        </button>
        <a routerLink="/appointments" class="btn-secondary">Cancel</a>
      </div>
    </form>
  `,
  styles: [`
    .form-layout { display: flex; flex-direction: column; gap: 20px; max-width: 720px; }
    .form-section { padding: 24px; }
    .form-section-header {
      display: flex; align-items: flex-start; gap: 12px;
      margin-bottom: 20px; padding-bottom: 16px;
      border-bottom: 1px solid var(--clr-gray-100);
    }
    .form-section-icon {
      width: 36px; height: 36px; border-radius: 8px;
      background: var(--clr-brand-light); color: var(--clr-brand);
      display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    }
    .form-section-title { font-weight: 600; font-size: .95rem; color: var(--clr-gray-800); }
    .form-section-sub { font-size: .8rem; color: var(--clr-gray-500); margin-top: 2px; }

    .field-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 640px) { .field-grid-2 { grid-template-columns: 1fr; } }

    .req { color: var(--clr-danger); }

    /* Search widgets */
    .search-wrap { position: relative; }
    .search-field { position: relative; }
    .search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--clr-gray-400); pointer-events: none; }
    .search-input { padding-left: 34px !important; }
    .search-dropdown {
      list-style: none;
      position: absolute; left: 0; right: 0; top: calc(100% + 4px);
      background: var(--clr-surface);
      border: 1px solid var(--clr-gray-200);
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-md);
      z-index: 50; max-height: 220px; overflow-y: auto;
    }
    .search-option {
      display: flex; align-items: center; gap: 10px;
      padding: 10px 14px; cursor: pointer; font-size: .875rem;
      transition: background .1s;
      &:hover { background: var(--clr-gray-50); }
      &:not(:last-child) { border-bottom: 1px solid var(--clr-gray-100); }
    }
    .no-results { font-size: .8rem; color: var(--clr-gray-400); margin-top: 6px; padding: 0 4px; }

    /* Avatars */
    .avatar-sm {
      width: 28px; height: 28px; border-radius: 50%;
      background: var(--clr-brand); color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: .75rem; font-weight: 700; flex-shrink: 0;
    }
    .avatar-sm--doctor { background: var(--clr-info, #3b82f6); }

    .option-name { font-weight: 600; color: var(--clr-gray-800); }
    .option-sub  { font-size: .75rem; color: var(--clr-gray-500); }

    /* Selected cards */
    .selected-card {
      display: flex; align-items: center; gap: 14px;
      padding: 12px 16px;
      border-radius: var(--radius-md);
    }
    .selected-card--patient {
      background: var(--clr-success-bg);
      border: 1px solid var(--clr-success-border);
    }
    .selected-card--doctor {
      background: #eff6ff;
      border: 1px solid #bfdbfe;
    }
    .avatar {
      width: 40px; height: 40px; border-radius: 50%;
      color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: .9rem; flex-shrink: 0;
    }
    .avatar--patient { background: var(--clr-success); }
    .avatar--doctor  { background: var(--clr-info, #3b82f6); }
    .selected-info { flex: 1; }
    .selected-name { font-weight: 600; color: var(--clr-gray-800); }
    .selected-meta { font-size: .78rem; color: var(--clr-gray-500); }

    .form-actions { display: flex; gap: 12px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .spin { animation: spin .65s linear infinite; }
  `],
})
export class AppointmentBookComponent implements OnInit {
  private readonly apptSvc = inject(AppointmentService);
  private readonly patientSvc = inject(PatientService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);

  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);

  readonly patientResults = signal<PatientSummary[]>([]);
  readonly selectedPatient = signal<PatientSummary | null>(null);
  patientSearchTerm = '';
  private readonly patientSearch$ = new Subject<string>();

  readonly doctorResults = signal<DoctorSummary[]>([]);
  readonly selectedDoctor = signal<DoctorSummary | null>(null);
  readonly doctorSearching = signal(false);
  doctorSearchTerm = '';
  private readonly doctorSearch$ = new Subject<string>();

  readonly form = this.fb.group({
    start_at: ['', Validators.required],
    end_at:   ['', Validators.required],
    reason:   [''],
  });

  fc(name: string) { return this.form.controls[name as keyof typeof this.form.controls]; }

  ngOnInit(): void {
    const pid = this.route.snapshot.queryParamMap.get('patient_id');
    if (pid) {
      this.patientSvc.get(pid).subscribe(p => {
        this.selectedPatient.set({ patient_id: p.patient_id, display_name: p.display_name, date_of_birth: p.date_of_birth, sex: p.sex, has_email: !!p.email, has_phone: !!p.phone });
      });
    }

    this.patientSearch$.pipe(
      debounceTime(300), distinctUntilChanged(),
      switchMap(term => term.length >= 2
        ? this.patientSvc.search(term, 6).pipe(catchError(() => of({ items: [], total: 0, limit: 6, offset: 0 })))
        : of({ items: [], total: 0, limit: 6, offset: 0 })
      ),
    ).subscribe(r => this.patientResults.set(r.items));

    this.doctorSearch$.pipe(
      debounceTime(300), distinctUntilChanged(),
      switchMap(term => {
        this.doctorSearching.set(true);
        return this.apptSvc.searchDoctors(term).pipe(
          catchError(() => of({ items: [], total: 0 }))
        );
      }),
    ).subscribe(r => { this.doctorResults.set(r.items); this.doctorSearching.set(false); });

    // Load all doctors on mount so the dropdown pre-populates
    this.apptSvc.searchDoctors('').subscribe(r => this.doctorResults.set(r.items));
  }

  onPatientSearch(term: string): void { this.patientSearchTerm = term; this.patientSearch$.next(term); }
  selectPatient(p: PatientSummary): void { this.selectedPatient.set(p); this.patientResults.set([]); this.patientSearchTerm = ''; }
  clearPatient(): void { this.selectedPatient.set(null); }

  onDoctorSearch(term: string): void { this.doctorSearchTerm = term; this.doctorSearch$.next(term); }
  selectDoctor(d: DoctorSummary): void { this.selectedDoctor.set(d); this.doctorResults.set([]); this.doctorSearchTerm = ''; }
  clearDoctor(): void { this.selectedDoctor.set(null); this.apptSvc.searchDoctors('').subscribe(r => this.doctorResults.set(r.items)); }

  submit(): void {
    if (this.form.invalid || !this.selectedPatient() || !this.selectedDoctor()) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    this.submitting.set(true);
    this.error.set(null);
    this.apptSvc.book({
      patient_id: this.selectedPatient()!.patient_id,
      doctor_id:  this.selectedDoctor()!.doctor_id,
      start_at:   new Date(v.start_at!).toISOString(),
      end_at:     new Date(v.end_at!).toISOString(),
      reason:     v.reason || undefined,
    }).subscribe({
      next: res => this.router.navigate(['/appointments', res.appointment_id]),
      error: err => { this.error.set(err?.error?.detail ?? 'Booking failed.'); this.submitting.set(false); },
    });
  }
}
