import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../auth/auth.service';

@Component({
  selector: 'app-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">🏥</span>
        <span class="brand-name">SmartClinic</span>
      </div>

      <ul class="nav-list">
        <li>
          <a routerLink="/dashboard" routerLinkActive="active" class="nav-link">
            <span class="nav-icon">📊</span>
            <span>Dashboard</span>
          </a>
        </li>

        @if (auth.isReceptionist() || auth.isDoctor()) {
          <li class="nav-section">PATIENT</li>
          <li>
            <a routerLink="/patients" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">👤</span>
              <span>Patients</span>
            </a>
          </li>
          <li>
            <a routerLink="/appointments" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">📅</span>
              <span>Appointments</span>
            </a>
          </li>
        }

        @if (auth.isDoctor()) {
          <li class="nav-section">CLINICAL</li>
          <li>
            <a routerLink="/encounters" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">🩺</span>
              <span>Encounters</span>
            </a>
          </li>
        }

        @if (auth.hasRole('lab_technician') || auth.isDoctor()) {
          <li class="nav-section">LABORATORY</li>
          <li>
            <a routerLink="/lab-orders" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">🧪</span>
              <span>Lab Orders</span>
            </a>
          </li>
        }

        @if (auth.hasRole('pharmacist')) {
          <li class="nav-section">PHARMACY</li>
          <li>
            <a routerLink="/prescriptions" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">💊</span>
              <span>Prescriptions</span>
            </a>
          </li>
        }

        @if (auth.hasRole('accounts') || auth.isReceptionist()) {
          <li class="nav-section">BILLING</li>
          <li>
            <a routerLink="/invoices" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">💵</span>
              <span>Invoices</span>
            </a>
          </li>
        }

        <li class="nav-section">OPERATIONS</li>
        <li>
          <a routerLink="/visit-tracker" routerLinkActive="active" class="nav-link">
            <span class="nav-icon">🗺️</span>
            <span>Visit Tracker</span>
          </a>
        </li>
      </ul>

      <div class="sidebar-footer">
        <div class="user-info">
          <span class="user-name">{{ auth.profile()?.username }}</span>
          <span class="user-role">{{ primaryRole() }}</span>
        </div>
        <button class="logout-btn" (click)="auth.logout()">Sign out</button>
      </div>
    </nav>
  `,
  styles: [`
    .sidebar {
      display: flex;
      flex-direction: column;
      width: 220px;
      height: 100vh;
      background: #1e293b;
      color: #f8fafc;
      padding: 0;
      position: fixed;
      left: 0;
      top: 0;
      overflow-y: auto;
    }
    .sidebar-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 20px 16px;
      border-bottom: 1px solid #334155;
      font-size: 1.1rem;
      font-weight: 700;
      position: sticky;
      top: 0;
      background: #1e293b;
      z-index: 1;
    }
    .nav-list {
      list-style: none;
      margin: 0;
      padding: 12px 0;
      flex: 1;
    }
    .nav-section {
      padding: 12px 16px 4px;
      font-size: .6rem;
      font-weight: 700;
      color: #475569;
      letter-spacing: .08em;
    }
    .nav-link {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 16px;
      color: #94a3b8;
      text-decoration: none;
      border-radius: 6px;
      margin: 1px 8px;
      transition: background 0.15s, color 0.15s;
      font-size: .9rem;
    }
    .nav-link:hover, .nav-link.active {
      background: #334155;
      color: #f8fafc;
    }
    .nav-icon { font-size: 1rem; width: 20px; text-align: center; }
    .sidebar-footer {
      padding: 16px;
      border-top: 1px solid #334155;
      position: sticky;
      bottom: 0;
      background: #1e293b;
    }
    .user-name { display: block; font-weight: 600; font-size: 0.9rem; }
    .user-role { display: block; font-size: 0.75rem; color: #94a3b8; text-transform: capitalize; }
    .logout-btn {
      margin-top: 10px;
      width: 100%;
      padding: 8px;
      background: transparent;
      border: 1px solid #475569;
      color: #94a3b8;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      transition: background 0.15s;
    }
    .logout-btn:hover { background: #334155; color: #f8fafc; }
  `],
})
export class NavComponent {
  readonly auth = inject(AuthService);

  primaryRole(): string {
    const roles = this.auth.profile()?.roles;
    if (!roles) return '';
    for (const r of ['doctor', 'receptionist', 'pharmacist', 'accounts', 'lab_technician']) {
      if (roles.has(r)) return r.replace('_', ' ');
    }
    return '';
  }
}
