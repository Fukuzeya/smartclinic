import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavComponent } from './nav.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, NavComponent],
  template: `
    <app-nav />
    <main class="shell-main">
      <div class="shell-content">
        <router-outlet />
      </div>
    </main>
  `,
  styles: [`
    .shell-main {
      padding-top: var(--header-h, 56px);
      min-height: 100vh;
      background: var(--clr-bg);
    }
    .shell-content {
      max-width: 1400px;
      margin: 0 auto;
      padding: 28px 32px 48px;
    }
    @media (max-width: 900px) {
      .shell-content { padding: 16px 16px 32px; }
    }
  `],
})
export class ShellComponent {}
