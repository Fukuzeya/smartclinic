import {
  Component, inject, signal, computed, OnInit, DestroyRef
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { debounceTime, distinctUntilChanged, Subject, switchMap, catchError, of } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { PatientService } from '../../shared/api/patient.service';
import { PatientSummary } from '../../shared/models/patient.model';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-patient-list',
  standalone: true,
  imports: [RouterLink, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Patients</h1>
        <p class="page-subtitle">Search and manage patient records</p>
      </div>
      @if (auth.isReceptionist()) {
        <a routerLink="new" class="btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Register Patient
        </a>
      }
    </div>

    <div class="card">
      <div class="search-bar">
        <div class="search-field-wrap">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            type="search"
            placeholder="Search patients by name…"
            [(ngModel)]="searchTerm"
            (ngModelChange)="onSearch($event)"
            class="form-control search-input"
          />
        </div>
      </div>

      @if (loading()) {
        <div class="loading">Loading…</div>
      } @else if (error()) {
        <div class="alert-error">{{ error() }}</div>
      } @else if (patients().length === 0) {
        <div class="empty-state">
          <strong>No patients found</strong>
          <p>{{ searchTerm ? 'Try a different search term.' : 'Register the first patient to get started.' }}</p>
        </div>
      } @else {
        <table class="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Date of birth</th>
              <th>Sex</th>
              <th>Contact</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (p of patients(); track p.patient_id) {
              <tr>
                <td><strong>{{ p.display_name }}</strong></td>
                <td>{{ p.date_of_birth }}</td>
                <td>{{ p.sex }}</td>
                <td>
                  @if (p.has_email) { <span title="Email">✉</span> }
                  @if (p.has_phone) { <span title="Phone">📞</span> }
                </td>
                <td>
                  <a [routerLink]="p.patient_id" class="btn-secondary btn-sm">View</a>
                </td>
              </tr>
            }
          </tbody>
        </table>

        @if (total() > limit) {
          <div class="pagination">
            <button class="btn-secondary btn-sm"
                    [disabled]="offset() === 0"
                    (click)="prevPage()">← Prev</button>
            <span class="page-info">{{ pageLabel() }}</span>
            <button class="btn-secondary btn-sm"
                    [disabled]="offset() + limit >= total()"
                    (click)="nextPage()">Next →</button>
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .search-bar { margin-bottom: 20px; }
    .search-field-wrap { position: relative; max-width: 400px; }
    .search-icon { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); color: var(--clr-gray-400); pointer-events: none; }
    .search-input { padding-left: 36px !important; }
    .pagination { display: flex; align-items: center; gap: 12px; margin-top: 16px; justify-content: flex-end; }
    .page-info { font-size: .825rem; color: var(--clr-gray-500); }
  `],
})
export class PatientListComponent implements OnInit {
  private readonly svc = inject(PatientService);
  readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  readonly limit = 20;

  readonly patients = signal<PatientSummary[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  searchTerm = '';
  private readonly search$ = new Subject<string>();

  readonly pageLabel = computed(() =>
    `${this.offset() + 1}–${Math.min(this.offset() + this.limit, this.total())} of ${this.total()}`
  );

  ngOnInit(): void {
    this.search$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap(term => {
          this.loading.set(true);
          this.error.set(null);
          this.offset.set(0);
          return this.svc.search(term, this.limit, 0).pipe(
            catchError(err => {
              this.error.set('Failed to load patients. Please try again.');
              return of({ items: [], total: 0, limit: this.limit, offset: 0 });
            })
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(resp => {
        this.patients.set(resp.items);
        this.total.set(resp.total);
        this.loading.set(false);
      });

    this.search$.next('');
  }

  onSearch(term: string): void {
    this.search$.next(term);
  }

  prevPage(): void {
    const newOffset = Math.max(0, this.offset() - this.limit);
    this.loadPage(newOffset);
  }

  nextPage(): void {
    this.loadPage(this.offset() + this.limit);
  }

  private loadPage(newOffset: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.svc.search(this.searchTerm, this.limit, newOffset)
      .pipe(
        catchError(() => {
          this.error.set('Failed to load page.');
          return of({ items: this.patients(), total: this.total(), limit: this.limit, offset: newOffset });
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(resp => {
        this.patients.set(resp.items);
        this.total.set(resp.total);
        this.offset.set(newOffset);
        this.loading.set(false);
      });
  }
}
