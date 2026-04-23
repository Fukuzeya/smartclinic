import { Routes } from '@angular/router';
import { ShellComponent } from './core/layout/shell.component';
import { authGuard, roleGuard } from './core/auth/auth.guard';

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
        canActivate: [roleGuard('receptionist', 'doctor')],
        loadChildren: () =>
          import('./features/patients/patients.routes').then(m => m.PATIENT_ROUTES),
      },
      {
        path: 'appointments',
        canActivate: [roleGuard('receptionist', 'doctor')],
        loadChildren: () =>
          import('./features/appointments/appointments.routes').then(m => m.APPOINTMENT_ROUTES),
      },
      {
        path: 'encounters',
        canActivate: [roleGuard('doctor')],
        loadChildren: () =>
          import('./features/encounters/encounters.routes').then(m => m.ENCOUNTER_ROUTES),
      },
      {
        path: 'lab-orders',
        canActivate: [roleGuard('lab_technician', 'doctor')],
        loadChildren: () =>
          import('./features/lab-orders/lab-orders.routes').then(m => m.LAB_ORDER_ROUTES),
      },
      {
        path: 'prescriptions',
        canActivate: [roleGuard('pharmacist', 'doctor')],
        loadChildren: () =>
          import('./features/prescriptions/prescriptions.routes').then(m => m.PRESCRIPTION_ROUTES),
      },
      {
        path: 'stock',
        canActivate: [roleGuard('pharmacist')],
        loadChildren: () =>
          import('./features/stock/stock.routes').then(m => m.STOCK_ROUTES),
      },
      {
        path: 'invoices',
        canActivate: [roleGuard('accounts', 'receptionist')],
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
