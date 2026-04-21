import { Routes } from '@angular/router';

export const PATIENT_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./patient-list.component').then(m => m.PatientListComponent),
  },
  {
    path: 'new',
    loadComponent: () =>
      import('./patient-register.component').then(m => m.PatientRegisterComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./patient-detail.component').then(m => m.PatientDetailComponent),
  },
];
