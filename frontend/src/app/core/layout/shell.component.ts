import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavComponent } from './nav.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, NavComponent],
  template: `
    <app-nav />
    <main class="main-content">
      <router-outlet />
    </main>
  `,
  styles: [`
    :host {
      display: flex;
      min-height: 100vh;
    }
    .main-content {
      margin-left: 220px;
      flex: 1;
      padding: 24px;
      background: #f1f5f9;
      min-height: 100vh;
    }
  `],
})
export class ShellComponent {}
