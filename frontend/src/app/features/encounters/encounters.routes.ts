import { Routes } from '@angular/router';
import { roleGuard } from '../../core/auth/auth.guard';

export const ENCOUNTER_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./encounter-list.component').then(m => m.EncounterListComponent),
  },
  {
    path: 'new',
    canActivate: [roleGuard('doctor')],
    loadComponent: () =>
      import('./encounter-start.component').then(m => m.EncounterStartComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./encounter-detail.component').then(m => m.EncounterDetailComponent),
  },
];
