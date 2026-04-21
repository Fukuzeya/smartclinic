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
      <h1>Register patient</h1>
      <a routerLink="/patients" class="btn btn-secondary">← Back</a>
    </div>

    @if (error()) {
      <div class="alert alert-error">{{ error() }}</div>
    }

    <div class="card">
      <form [formGroup]="form" (ngSubmit)="submit()">
        <h3 class="section-title">Personal details</h3>

        <div class="form-row">
          <div class="form-group">
            <label for="given_name">Given name *</label>
            <input id="given_name" formControlName="given_name" type="text" />
            @if (fc('given_name').invalid && fc('given_name').touched) {
              <span class="field-error">Required</span>
            }
          </div>

          <div class="form-group">
            <label for="middle_name">Middle name</label>
            <input id="middle_name" formControlName="middle_name" type="text" />
          </div>

          <div class="form-group">
            <label for="family_name">Family name *</label>
            <input id="family_name" formControlName="family_name" type="text" />
            @if (fc('family_name').invalid && fc('family_name').touched) {
              <span class="field-error">Required</span>
            }
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="national_id">National ID *</label>
            <input id="national_id" formControlName="national_id" type="text"
                   placeholder="00-000000A00" />
            @if (fc('national_id').errors?.['required'] && fc('national_id').touched) {
              <span class="field-error">Required</span>
            }
            @if (fc('national_id').errors?.['pattern'] && fc('national_id').touched) {
              <span class="field-error">Format: NN-NNNNNNN[A-Z]NN</span>
            }
          </div>

          <div class="form-group">
            <label for="date_of_birth">Date of birth *</label>
            <input id="date_of_birth" formControlName="date_of_birth" type="date" />
            @if (fc('date_of_birth').invalid && fc('date_of_birth').touched) {
              <span class="field-error">Required</span>
            }
          </div>

          <div class="form-group">
            <label for="sex">Sex *</label>
            <select id="sex" formControlName="sex">
              <option value="">— select —</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="unknown">Unknown / prefer not to say</option>
            </select>
            @if (fc('sex').invalid && fc('sex').touched) {
              <span class="field-error">Required</span>
            }
          </div>
        </div>

        <h3 class="section-title">Contact (at least one required)</h3>

        <div class="form-row">
          <div class="form-group">
            <label for="email">Email address</label>
            <input id="email" formControlName="email" type="email" />
            @if (fc('email').errors?.['email'] && fc('email').touched) {
              <span class="field-error">Invalid email address</span>
            }
          </div>

          <div class="form-group">
            <label for="phone">Phone (E.164)</label>
            <input id="phone" formControlName="phone" type="tel"
                   placeholder="+263771234567" />
            @if (fc('phone').errors?.['pattern'] && fc('phone').touched) {
              <span class="field-error">Must be E.164 format, e.g. +263771234567</span>
            }
          </div>
        </div>

        <div class="form-actions">
          <button type="submit" class="btn btn-primary"
                  [disabled]="form.invalid || submitting()">
            {{ submitting() ? 'Registering…' : 'Register patient' }}
          </button>
          <a routerLink="/patients" class="btn btn-secondary">Cancel</a>
        </div>
      </form>
    </div>
  `,
  styles: [`
    .section-title { margin: 20px 0 12px; color: #475569; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
    .form-actions { display: flex; gap: 12px; margin-top: 24px; }
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
