import { Component, inject, signal } from '@angular/core';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { EncounterService } from '../../shared/api/encounter.service';

@Component({
  selector: 'app-encounter-start',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <div class="page-header">
      <h1 class="page-title">Start Clinical Encounter</h1>
    </div>

    <div class="card" style="max-width:480px">
      <form [formGroup]="form" (ngSubmit)="submit()">
        <div class="form-group">
          <label>Patient ID <span class="required">*</span></label>
          <input class="form-control" formControlName="patient_id" placeholder="pat_xxxxxxxx-…" />
        </div>
        <div class="form-group">
          <label>Appointment ID <span style="color:#94a3b8">(optional)</span></label>
          <input class="form-control" formControlName="appointment_id" placeholder="apt_xxxxxxxx-…" />
        </div>

        @if (error()) {
          <div class="alert-error">{{ error() }}</div>
        }

        <button type="submit" class="btn-primary" [disabled]="form.invalid || loading()">
          {{ loading() ? 'Starting…' : 'Start Encounter' }}
        </button>
      </form>
    </div>
  `,
})
export class EncounterStartComponent {
  private readonly fb = inject(FormBuilder);
  private readonly svc = inject(EncounterService);
  private readonly router = inject(Router);

  loading = signal(false);
  error = signal('');

  form = this.fb.group({
    patient_id: ['', Validators.required],
    appointment_id: [''],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');
    const { patient_id, appointment_id } = this.form.value;
    this.svc.start({ patient_id: patient_id!, appointment_id: appointment_id || undefined }).subscribe({
      next: r => this.router.navigate(['/encounters', r.encounter_id]),
      error: e => { this.error.set(e.error?.detail ?? 'Failed to start encounter'); this.loading.set(false); },
    });
  }
}
