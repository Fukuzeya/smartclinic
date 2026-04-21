import { Routes } from '@angular/router';

export const LAB_ORDER_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./lab-order-list.component').then(m => m.LabOrderListComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./lab-order-detail.component').then(m => m.LabOrderDetailComponent),
  },
];
