/**
 * Authentication service — wraps Keycloak JS and exposes a clean,
 * Angular-idiomatic API using Signals.
 *
 * The Keycloak PKCE flow (ADR 0011) is initiated here. The Angular app
 * bootstraps with `APP_INITIALIZER` calling `init()` so the token is
 * available before any HTTP call is made.
 */
import { Injectable, signal, computed } from '@angular/core';
import Keycloak from 'keycloak-js';
import { environment } from '@env';

export interface UserProfile {
  subject: string;
  username: string;
  email?: string;
  roles: Set<string>;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly _keycloak = new Keycloak({
    url: environment.keycloak.url,
    realm: environment.keycloak.realm,
    clientId: environment.keycloak.clientId,
  });

  private readonly _profile = signal<UserProfile | null>(null);

  readonly profile = this._profile.asReadonly();
  readonly isAuthenticated = computed(() => this._profile() !== null);
  readonly isReceptionist = computed(
    () => this._profile()?.roles.has('receptionist') ?? false
  );
  readonly isDoctor = computed(
    () => this._profile()?.roles.has('doctor') ?? false
  );
  readonly isPharmacist = computed(
    () => this._profile()?.roles.has('pharmacist') ?? false
  );

  async init(): Promise<void> {
    const authenticated = await this._keycloak.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false,
    });

    if (authenticated) {
      const tokenParsed = this._keycloak.tokenParsed!;
      this._profile.set({
        subject: tokenParsed['sub'] as string,
        username: (tokenParsed['preferred_username'] as string) ?? '',
        email: tokenParsed['email'] as string | undefined,
        roles: new Set<string>([
          ...(tokenParsed['realm_access']?.['roles'] ?? []),
        ]),
      });

      // Refresh token 30 s before expiry
      setInterval(async () => {
        try {
          await this._keycloak.updateToken(30);
        } catch {
          this.logout();
        }
      }, 10_000);
    }
  }

  /** Return the current Bearer token string, refreshing if needed. */
  async getToken(): Promise<string> {
    await this._keycloak.updateToken(30);
    return this._keycloak.token!;
  }

  logout(): void {
    this._keycloak.logout({ redirectUri: window.location.origin });
  }

  hasRole(role: string): boolean {
    return this._profile()?.roles.has(role) ?? false;
  }
}
