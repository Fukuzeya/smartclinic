import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { PatientService } from '../../shared/api/patient.service';

@Component({
  selector: 'app-patient-register',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Register Patient</h1>
        <p class="page-subtitle">Complete the form below to add a new patient record</p>
      </div>
      <a routerLink="/patients" class="btn-secondary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        Back to Patients
      </a>
    </div>

    @if (error()) {
      <div class="alert-error" style="margin-bottom:20px">{{ error() }}</div>
    }

    <form [formGroup]="form" (ngSubmit)="submit()" class="form-layout">
      <!-- Personal details -->
      <div class="card form-section">
        <div class="form-section-header">
          <div class="form-section-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
          </div>
          <div>
            <div class="form-section-title">Personal Details</div>
            <div class="form-section-sub">Legal name and demographic information</div>
          </div>
        </div>

        <div class="field-grid-3">
          <div class="form-group">
            <label for="given_name">Given name <span class="req">*</span></label>
            <input id="given_name" class="form-control" formControlName="given_name" type="text" placeholder="e.g. Chipo" autocomplete="given-name"/>
            @if (fc('given_name').invalid && fc('given_name').touched) {
              <span class="field-error">Required</span>
            }
          </div>
          <div class="form-group">
            <label for="middle_name">Middle name</label>
            <input id="middle_name" class="form-control" formControlName="middle_name" type="text" placeholder="Optional" autocomplete="additional-name"/>
          </div>
          <div class="form-group">
            <label for="family_name">Family name <span class="req">*</span></label>
            <input id="family_name" class="form-control" formControlName="family_name" type="text" placeholder="e.g. Moyo" autocomplete="family-name"/>
            @if (fc('family_name').invalid && fc('family_name').touched) {
              <span class="field-error">Required</span>
            }
          </div>
        </div>

        <div class="field-grid-3">
          <div class="form-group">
            <label for="national_id">National ID <span class="req">*</span></label>
            <input id="national_id" class="form-control" formControlName="national_id" type="text" placeholder="63-123456A-75"/>
            @if (fc('national_id').errors?.['required'] && fc('national_id').touched) {
              <span class="field-error">Required</span>
            }
            @if (fc('national_id').errors?.['pattern'] && fc('national_id').touched) {
              <span class="field-error">Format: NN-NNNNNNN[A-Z]NN</span>
            }
          </div>
          <div class="form-group">
            <label for="date_of_birth">Date of birth <span class="req">*</span></label>
            <input id="date_of_birth" class="form-control" formControlName="date_of_birth" type="date"/>
            @if (fc('date_of_birth').invalid && fc('date_of_birth').touched) {
              <span class="field-error">Required</span>
            }
          </div>
          <div class="form-group">
            <label for="sex">Sex <span class="req">*</span></label>
            <select id="sex" class="form-control" formControlName="sex">
              <option value="">Select…</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="unknown">Prefer not to say</option>
            </select>
            @if (fc('sex').invalid && fc('sex').touched) {
              <span class="field-error">Required</span>
            }
          </div>
        </div>
      </div>

      <!-- Contact details -->
      <div class="card form-section">
        <div class="form-section-header">
          <div class="form-section-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.59 3.47 2 2 0 0 1 3.56 1.29h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9a16 16 0 0 0 6 6l1.27-.9a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21.9 16z"/></svg>
          </div>
          <div>
            <div class="form-section-title">Contact Information</div>
            <div class="form-section-sub">At least one contact method is recommended</div>
          </div>
        </div>

        <div class="field-grid-2">
          <div class="form-group">
            <label for="email">Email address</label>
            <input id="email" class="form-control" formControlName="email" type="email" placeholder="patient@example.com" autocomplete="email"/>
            @if (fc('email').errors?.['email'] && fc('email').touched) {
              <span class="field-error">Enter a valid email address</span>
            }
          </div>
          <div class="form-group">
            <label for="phone">Phone number</label>
            <input id="phone" class="form-control" formControlName="phone" type="tel" placeholder="+263771234567" autocomplete="tel"/>
            @if (fc('phone').errors?.['pattern'] && fc('phone').touched) {
              <span class="field-error">Use E.164 format: +263771234567</span>
            }
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="form-actions">
        <button type="submit" class="btn-primary" [disabled]="form.invalid || submitting()">
          @if (submitting()) {
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" opacity=".2"/><path d="M21 12a9 9 0 0 1-9 9"/></svg>
            Registering…
          } @else {
            Register Patient
          }
        </button>
        <a routerLink="/patients" class="btn-secondary">Cancel</a>
      </div>
    </form>
  `,
  styles: [`
    .form-layout { display: flex; flex-direction: column; gap: 20px; max-width: 860px; }

    .form-section { padding: 24px; }
    .form-section-header {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--clr-gray-100);
    }
    .form-section-icon {
      width: 36px; height: 36px;
      border-radius: 8px;
      background: var(--clr-brand-light);
      color: var(--clr-brand);
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }
    .form-section-title { font-weight: 600; font-size: .95rem; color: var(--clr-gray-800); }
    .form-section-sub { font-size: .8rem; color: var(--clr-gray-500); margin-top: 2px; }

    .field-grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 4px; }
    .field-grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
    @media (max-width: 700px) {
      .field-grid-3 { grid-template-columns: 1fr; }
      .field-grid-2 { grid-template-columns: 1fr; }
    }

    .req { color: var(--clr-danger); }
    .form-actions { display: flex; gap: 12px; align-items: center; }

    @keyframes spin { to { transform: rotate(360deg); } }
    .spin { animation: spin .65s linear infinite; }
  `],
})
export class PatientRegisterComponent {
  private readonly svc = inject(PatientService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);

  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = this.fb.group({
    given_name:    ['', Validators.required],
    middle_name:   [''],
    family_name:   ['', Validators.required],
    national_id:   ['', [Validators.required, Validators.pattern(/^\d{2}-\d{7}[A-Z]\d{2}$/)]],
    date_of_birth: ['', Validators.required],
    sex:           ['', Validators.required],
    email:         ['', Validators.email],
    phone:         ['', Validators.pattern(/^\+[1-9]\d{6,14}$/)],
  });

  fc(name: string) {
    return this.form.controls[name as keyof typeof this.form.controls];
  }

  submit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const v = this.form.getRawValue();
    this.submitting.set(true);
    this.error.set(null);
    this.svc.register({
      given_name:    v.given_name!,
      middle_name:   v.middle_name || undefined,
      family_name:   v.family_name!,
      national_id:   v.national_id!,
      date_of_birth: v.date_of_birth!,
      sex:           v.sex as 'male' | 'female' | 'unknown',
      email:         v.email || undefined,
      phone:         v.phone || undefined,
    }).subscribe({
      next: res => this.router.navigate(['/patients', res.patient_id]),
      error: err => {
        this.error.set(err?.error?.detail ?? 'Registration failed. Please try again.');
        this.submitting.set(false);
      },
    });
  }
}
