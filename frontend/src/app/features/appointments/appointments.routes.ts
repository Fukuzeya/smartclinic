import { Routes } from '@angular/router';

export const APPOINTMENT_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./appointment-list.component').then(m => m.AppointmentListComponent),
  },
  {
    path: 'new',
    loadComponent: () =>
      import('./appointment-book.component').then(m => m.AppointmentBookComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./appointment-detail.component').then(m => m.AppointmentDetailComponent),
  },
];
