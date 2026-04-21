import { Routes } from '@angular/router';

export const ENCOUNTER_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./encounter-list.component').then(m => m.EncounterListComponent),
  },
  {
    path: 'new',
    loadComponent: () =>
      import('./encounter-start.component').then(m => m.EncounterStartComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./encounter-detail.component').then(m => m.EncounterDetailComponent),
  },
];
