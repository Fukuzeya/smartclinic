/**
 * HTTP interceptor — attaches the Keycloak Bearer token to every
 * outbound request targeting a SmartClinic API host.
 *
 * Uses the functional interceptor API introduced in Angular 15,
 * compatible with the standalone bootstrap style used here.
 */
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '@env';

const API_ORIGINS = Object.values(environment.api);

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const isApiCall = API_ORIGINS.some((origin) => req.url.startsWith(origin));
  if (!isApiCall) {
    return next(req);
  }

  const auth = inject(AuthService);
  return from(auth.getToken()).pipe(
    switchMap((token) =>
      next(
        req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      )
    )
  );
};
