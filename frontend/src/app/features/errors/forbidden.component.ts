import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { inject } from '@angular/core';

@Component({
  selector: 'app-forbidden',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="error-page">
      <div class="error-code">403</div>
      <h1 class="error-title">Access Denied</h1>
      <p class="error-msg">
        Your role (<strong>{{ role() }}</strong>) does not have permission to view this page.
      </p>
      <a routerLink="/dashboard" class="btn-primary">Back to Dashboard</a>
    </div>
  `,
  styles: [`
    .error-page {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 70vh;
      text-align: center;
      gap: 16px;
    }
    .error-code {
      font-size: 6rem;
      font-weight: 800;
      color: #fee2e2;
      line-height: 1;
    }
    .error-title { font-size: 1.5rem; font-weight: 700; color: #1e293b; }
    .error-msg { color: #64748b; font-size: 0.95rem; max-width: 380px; }
  `],
})
export class ForbiddenComponent {
  private readonly auth = inject(AuthService);

  role(): string {
    const roles = this.auth.profile()?.roles;
    if (!roles) return 'unknown';
    for (const r of ['doctor', 'receptionist', 'pharmacist', 'accounts', 'lab_technician']) {
      if (roles.has(r)) return r.replace('_', ' ');
    }
    return 'unknown';
  }
}
