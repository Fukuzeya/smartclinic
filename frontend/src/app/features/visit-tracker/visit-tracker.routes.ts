import { Routes } from '@angular/router';

export const VISIT_TRACKER_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./visit-tracker.component').then(m => m.VisitTrackerComponent),
  },
];
