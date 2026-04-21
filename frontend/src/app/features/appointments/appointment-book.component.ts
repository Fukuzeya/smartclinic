import { Component, inject, signal, OnInit } from '@angular/core';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { AppointmentService } from '../../shared/api/appointment.service';
import { PatientService } from '../../shared/api/patient.service';
import { AuthService } from '../../core/auth/auth.service';
import { PatientSummary } from '../../shared/models/patient.model';
import { debounceTime, distinctUntilChanged, Subject, switchMap, catchError, of } from 'rxjs';

@Component({
  selector: 'app-appointment-book',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="page-header">
      <h1>Book appointment</h1>
      <a routerLink="/appointments" class="btn btn-secondary">← Back</a>
    </div>

    @if (error()) {
      <div class="alert alert-error">{{ error() }}</div>
    }

    <div class="card">
      <form [formGroup]="form" (ngSubmit)="submit()">

        <div class="form-group">
          <label for="patient_search">Patient *</label>
          <input id="patient_search" type="search"
                 [value]="patientSearchTerm"
                 (input)="onPatientSearch($any($event.target).value)"
                 placeholder="Search by name…" />
          @if (patientResults().length > 0) {
            <ul class="patient-dropdown">
              @for (p of patientResults(); track p.patient_id) {
                <li (click)="selectPatient(p)" class="patient-option">
                  {{ p.display_name }} · {{ p.date_of_birth }}
                </li>
              }
            </ul>
          }
          @if (selectedPatient()) {
            <div class="selected-patient">
              ✓ {{ selectedPatient()!.display_name }}
              <button type="button" class="btn btn-secondary btn-sm" (click)="clearPatient()">×</button>
            </div>
          }
        </div>

        <div class="form-group">
          <label for="doctor_id">Doctor ID *</label>
          <input id="doctor_id" formControlName="doctor_id" type="text"
                 placeholder="Doctor's user ID from Keycloak" />
          @if (fc('doctor_id').invalid && fc('doctor_id').touched) {
            <span class="field-error">Required</span>
          }
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="start_at">Start time *</label>
            <input id="start_at" formControlName="start_at" type="datetime-local" />
            @if (fc('start_at').invalid && fc('start_at').touched) {
              <span class="field-error">Required</span>
            }
          </div>

          <div class="form-group">
            <label for="end_at">End time *</label>
            <input id="end_at" formControlName="end_at" type="datetime-local" />
            @if (fc('end_at').invalid && fc('end_at').touched) {
              <span class="field-error">Required</span>
            }
          </div>
        </div>

        <div class="form-group">
          <label for="reason">Reason for visit</label>
          <textarea id="reason" formControlName="reason" rows="3"
                    placeholder="Optional — brief description"></textarea>
        </div>

        <div class="form-actions">
          <button type="submit" class="btn btn-primary"
                  [disabled]="form.invalid || !selectedPatient() || submitting()">
            {{ submitting() ? 'Booking…' : 'Book appointment' }}
          </button>
          <a routerLink="/appointments" class="btn btn-secondary">Cancel</a>
        </div>
      </form>
    </div>
  `,
  styles: [`
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .form-actions { display: flex; gap: 12px; margin-top: 24px; }
    .patient-dropdown {
      list-style: none;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      margin-top: 4px;
      background: #fff;
      box-shadow: 0 4px 12px rgba(0,0,0,.08);
      max-height: 200px;
      overflow-y: auto;
    }
    .patient-option {
      padding: 10px 12px;
      cursor: pointer;
      font-size: 0.9rem;
      &:hover { background: #f1f5f9; }
    }
    .selected-patient {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 6px;
      color: #15803d;
      font-size: 0.9rem;
      font-weight: 500;
    }
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

  readonly form = this.fb.group({
    doctor_id: ['', Validators.required],
    start_at:  ['', Validators.required],
    end_at:    ['', Validators.required],
    reason:    [''],
  });

  fc(name: string) {
    return this.form.controls[name as keyof typeof this.form.controls];
  }

  ngOnInit(): void {
    // Pre-fill patient_id from query param (e.g. from patient detail "Book" button)
    const pid = this.route.snapshot.queryParamMap.get('patient_id');
    if (pid) {
      this.patientSvc.get(pid).subscribe(p => {
        this.selectedPatient.set({
          patient_id: p.patient_id,
          display_name: p.display_name,
          date_of_birth: p.date_of_birth,
          sex: p.sex,
          has_email: !!p.email,
          has_phone: !!p.phone,
        });
      });
    }

    this.patientSearch$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap(term =>
          term.length >= 2
            ? this.patientSvc.search(term, 6).pipe(catchError(() => of({ items: [], total: 0, limit: 6, offset: 0 })))
            : of({ items: [], total: 0, limit: 6, offset: 0 })
        ),
      )
      .subscribe(r => this.patientResults.set(r.items));
  }

  onPatientSearch(term: string): void {
    this.patientSearchTerm = term;
    this.patientSearch$.next(term);
  }

  selectPatient(p: PatientSummary): void {
    this.selectedPatient.set(p);
    this.patientResults.set([]);
    this.patientSearchTerm = '';
  }

  clearPatient(): void {
    this.selectedPatient.set(null);
  }

  submit(): void {
    if (this.form.invalid || !this.selectedPatient()) {
      this.form.markAllAsTouched();
      return;
    }

    const v = this.form.getRawValue();
    this.submitting.set(true);
    this.error.set(null);

    this.apptSvc.book({
      patient_id: this.selectedPatient()!.patient_id,
      doctor_id:  v.doctor_id!,
      start_at:   new Date(v.start_at!).toISOString(),
      end_at:     new Date(v.end_at!).toISOString(),
      reason:     v.reason || undefined,
    }).subscribe({
      next: res => this.router.navigate(['/appointments', res.appointment_id]),
      error: err => {
        this.error.set(err?.error?.detail ?? 'Booking failed. Please try again.');
        this.submitting.set(false);
      },
    });
  }
}
