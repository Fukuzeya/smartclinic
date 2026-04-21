import { Routes } from '@angular/router';

export const INVOICE_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./invoice-list.component').then(m => m.InvoiceListComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./invoice-detail.component').then(m => m.InvoiceDetailComponent),
  },
];
