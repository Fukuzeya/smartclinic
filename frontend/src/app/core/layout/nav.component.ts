import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../auth/auth.service';

@Component({
  selector: 'app-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <div class="topbar-inner">

        <!-- Brand -->
        <a routerLink="/dashboard" class="topbar-brand">
          <div class="brand-mark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
            </svg>
          </div>
          <span class="brand-name">SmartClinic</span>
          <span class="brand-tag">EHR</span>
        </a>

        <div class="topbar-divider"></div>

        <!-- Primary navigation -->
        <nav class="topbar-nav" aria-label="Main navigation">
          <a routerLink="/dashboard" routerLinkActive="tl-active"
             [routerLinkActiveOptions]="{exact:true}" class="tl">
            Dashboard
          </a>

          @if (auth.isReceptionist() || auth.isDoctor()) {
            <a routerLink="/patients" routerLinkActive="tl-active" class="tl">Patients</a>
            <a routerLink="/appointments" routerLinkActive="tl-active" class="tl">Appointments</a>
          }

          @if (auth.isDoctor()) {
            <a routerLink="/encounters" routerLinkActive="tl-active" class="tl">Encounters</a>
          }

          @if (auth.hasRole('lab_technician') || auth.isDoctor()) {
            <a routerLink="/lab-orders" routerLinkActive="tl-active" class="tl">Lab Orders</a>
          }

          @if (auth.hasRole('pharmacist') || auth.isDoctor()) {
            <a routerLink="/prescriptions" routerLinkActive="tl-active" class="tl">Prescriptions</a>
          }

          @if (auth.hasRole('pharmacist')) {
            <a routerLink="/stock" routerLinkActive="tl-active" class="tl">Drug Stock</a>
          }

          @if (auth.hasRole('accounts') || auth.isReceptionist()) {
            <a routerLink="/invoices" routerLinkActive="tl-active" class="tl">Invoices</a>
          }

          <a routerLink="/visit-tracker" routerLinkActive="tl-active" class="tl">Visit Tracker</a>
        </nav>

        <!-- Right: user + sign out -->
        <div class="topbar-user">
          <div class="user-chip">
            <div class="user-avatar">{{ (auth.profile()?.username ?? 'U')[0].toUpperCase() }}</div>
            <div class="user-meta">
              <span class="user-name">{{ auth.profile()?.username }}</span>
              <span class="user-role">{{ primaryRole() }}</span>
            </div>
          </div>
          <div class="topbar-divider"></div>
          <button class="signout-btn" (click)="auth.logout()" title="Sign out">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            Sign out
          </button>
        </div>

      </div>
    </header>
  `,
  styles: [`
    /* ── Top bar ── */
    .topbar {
      position: fixed;
      top: 0; left: 0; right: 0;
      height: var(--header-h, 56px);
      background: var(--clr-nav-bg, #0F2D52);
      z-index: 200;
      box-shadow: 0 1px 4px rgba(0,0,0,.25);
    }
    .topbar-inner {
      height: 100%;
      display: flex;
      align-items: center;
      padding: 0 20px;
      gap: 0;
    }

    /* ── Brand ── */
    .topbar-brand {
      display: flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
      color: #fff;
      flex-shrink: 0;
      padding-right: 4px;
    }
    .brand-mark {
      width: 28px; height: 28px;
      border-radius: 5px;
      background: rgba(255,255,255,.18);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      flex-shrink: 0;
    }
    .brand-name {
      font-size: .9rem;
      font-weight: 700;
      letter-spacing: -.01em;
      white-space: nowrap;
    }
    .brand-tag {
      font-size: .6rem;
      font-weight: 700;
      background: rgba(255,255,255,.15);
      color: rgba(255,255,255,.8);
      padding: 2px 6px;
      border-radius: 3px;
      letter-spacing: .1em;
      text-transform: uppercase;
    }

    /* ── Divider ── */
    .topbar-divider {
      width: 1px;
      height: 22px;
      background: rgba(255,255,255,.15);
      flex-shrink: 0;
      margin: 0 16px;
    }

    /* ── Nav links ── */
    .topbar-nav {
      flex: 1;
      display: flex;
      align-items: stretch;
      height: 100%;
      overflow-x: auto;
      scrollbar-width: none;
      &::-webkit-scrollbar { display: none; }
    }
    .tl {
      display: flex;
      align-items: center;
      padding: 0 13px;
      color: rgba(255,255,255,.72);
      text-decoration: none;
      font-size: .8rem;
      font-weight: 500;
      white-space: nowrap;
      border-bottom: 2px solid transparent;
      transition: color .12s, background .12s, border-color .12s;
      letter-spacing: .01em;

      &:hover {
        color: #fff;
        background: var(--clr-nav-hover, rgba(255,255,255,.08));
      }
    }
    .tl-active {
      color: #fff !important;
      border-bottom-color: var(--clr-nav-active-border, #60A5FA) !important;
      background: rgba(255,255,255,.1) !important;
    }

    /* ── User area ── */
    .topbar-user {
      display: flex;
      align-items: center;
      gap: 0;
      flex-shrink: 0;
    }
    .user-chip {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .user-avatar {
      width: 28px; height: 28px;
      border-radius: 50%;
      background: rgba(255,255,255,.22);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: .78rem;
      flex-shrink: 0;
      border: 1px solid rgba(255,255,255,.3);
    }
    .user-meta {
      display: flex;
      flex-direction: column;
      line-height: 1.2;
    }
    .user-name {
      font-size: .78rem;
      font-weight: 600;
      color: #fff;
    }
    .user-role {
      font-size: .65rem;
      color: rgba(255,255,255,.6);
      text-transform: capitalize;
    }
    .signout-btn {
      display: flex;
      align-items: center;
      gap: 5px;
      background: transparent;
      border: none;
      color: rgba(255,255,255,.7);
      font-size: .78rem;
      font-family: inherit;
      font-weight: 500;
      cursor: pointer;
      padding: 6px 10px;
      border-radius: 4px;
      white-space: nowrap;
      transition: background .12s, color .12s;
      &:hover {
        background: rgba(255,255,255,.12);
        color: #fff;
      }
    }
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
