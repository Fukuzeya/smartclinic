import { Routes } from '@angular/router';
import { ShellComponent } from './core/layout/shell.component';
import { authGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'patients',
        loadChildren: () =>
          import('./features/patients/patients.routes').then(m => m.PATIENT_ROUTES),
      },
      {
        path: 'appointments',
        loadChildren: () =>
          import('./features/appointments/appointments.routes').then(m => m.APPOINTMENT_ROUTES),
      },
      {
        path: 'encounters',
        loadChildren: () =>
          import('./features/encounters/encounters.routes').then(m => m.ENCOUNTER_ROUTES),
      },
      {
        path: 'lab-orders',
        loadChildren: () =>
          import('./features/lab-orders/lab-orders.routes').then(m => m.LAB_ORDER_ROUTES),
      },
      {
        path: 'prescriptions',
        loadChildren: () =>
          import('./features/prescriptions/prescriptions.routes').then(m => m.PRESCRIPTION_ROUTES),
      },
      {
        path: 'invoices',
        loadChildren: () =>
          import('./features/invoices/invoices.routes').then(m => m.INVOICE_ROUTES),
      },
      {
        path: 'visit-tracker',
        loadChildren: () =>
          import('./features/visit-tracker/visit-tracker.routes').then(m => m.VISIT_TRACKER_ROUTES),
      },
      {
        path: 'forbidden',
        loadComponent: () =>
          import('./features/errors/forbidden.component').then(m => m.ForbiddenComponent),
      },
    ],
  },
  {
    path: '404',
    loadComponent: () =>
      import('./features/errors/not-found.component').then(m => m.NotFoundComponent),
  },
  { path: '**', redirectTo: '404' },
];
