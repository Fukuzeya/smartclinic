import { Routes } from '@angular/router';

export const PRESCRIPTION_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./prescription-list.component').then(m => m.PrescriptionListComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./prescription-detail.component').then(m => m.PrescriptionDetailComponent),
  },
];
