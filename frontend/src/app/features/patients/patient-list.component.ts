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
      <h1>Patients</h1>
      @if (auth.isReceptionist()) {
        <a routerLink="new" class="btn btn-primary">+ Register patient</a>
      }
    </div>

    <div class="card">
      <div class="search-bar">
        <input
          type="search"
          placeholder="Search by name…"
          [(ngModel)]="searchTerm"
          (ngModelChange)="onSearch($event)"
          class="search-input"
        />
      </div>

      @if (loading()) {
        <div class="loading-spinner">Loading…</div>
      } @else if (error()) {
        <div class="alert alert-error">{{ error() }}</div>
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
                  <a [routerLink]="p.patient_id" class="btn btn-secondary btn-sm">View</a>
                </td>
              </tr>
            }
          </tbody>
        </table>

        @if (total() > limit) {
          <div class="pagination">
            <button class="btn btn-secondary btn-sm"
                    [disabled]="offset() === 0"
                    (click)="prevPage()">← Prev</button>
            <span class="page-info">{{ pageLabel() }}</span>
            <button class="btn btn-secondary btn-sm"
                    [disabled]="offset() + limit >= total()"
                    (click)="nextPage()">Next →</button>
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .search-bar { margin-bottom: 16px; }
    .search-input {
      width: 100%;
      max-width: 400px;
      padding: 9px 12px;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      font-size: 0.9rem;
      outline: none;
      &:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.12); }
    }
    .pagination {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 16px;
      justify-content: flex-end;
    }
    .page-info { font-size: 0.85rem; color: #64748b; }
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
