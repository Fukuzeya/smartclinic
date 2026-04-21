import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/**
 * Guards any route behind Keycloak authentication.
 * In practice, Keycloak's onLoad:'login-required' handles the redirect
 * before Angular even boots, but this guard provides a safety net for
 * edge cases (token expiry between navigations, direct deep-link hits).
 */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }
  // Token expired mid-session — redirect Keycloak to re-auth.
  auth.logout();
  return router.createUrlTree(['/']);
};

/**
 * Factory that creates a guard allowing only users with the given role.
 * Usage in routes: canActivate: [roleGuard('doctor')]
 */
export function roleGuard(role: string): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);

    if (!auth.isAuthenticated()) {
      auth.logout();
      return false;
    }
    if (auth.hasRole(role)) {
      return true;
    }
    return router.createUrlTree(['/forbidden']);
  };
}
