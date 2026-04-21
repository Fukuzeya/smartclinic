import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="error-page">
      <div class="error-code">404</div>
      <h1 class="error-title">Page Not Found</h1>
      <p class="error-msg">The page you're looking for doesn't exist or has been moved.</p>
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
      color: #e2e8f0;
      line-height: 1;
    }
    .error-title {
      font-size: 1.5rem;
      font-weight: 700;
      color: #1e293b;
    }
    .error-msg {
      color: #64748b;
      font-size: 0.95rem;
      max-width: 360px;
    }
  `],
})
export class NotFoundComponent {}
