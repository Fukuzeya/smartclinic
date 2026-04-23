import { Injectable, inject, signal } from '@angular/core';
import { Observable, of, tap, map, shareReplay, catchError } from 'rxjs';
import { AppointmentService } from '../api/appointment.service';

/**
 * Shared cache that resolves doctor IDs to display names.
 * Fetches all doctors once from Keycloak (via scheduling service)
 * and caches in-memory.
 */
@Injectable({ providedIn: 'root' })
export class DoctorNameCache {
  private readonly apptSvc = inject(AppointmentService);
  private readonly cache = new Map<string, string>();
  private allLoaded = false;
  private loadAll$: Observable<Record<string, string>> | null = null;

  /** Eagerly load all doctors into cache (called once). */
  private ensureLoaded(): Observable<Record<string, string>> {
    if (this.allLoaded) return of(Object.fromEntries(this.cache));
    if (this.loadAll$) return this.loadAll$;
    this.loadAll$ = this.apptSvc.searchDoctors('').pipe(
      map(resp => {
        const nameMap: Record<string, string> = {};
        for (const d of resp.items) {
          nameMap[d.doctor_id] = d.display_name;
          this.cache.set(d.doctor_id, d.display_name);
        }
        this.allLoaded = true;
        this.loadAll$ = null;
        return nameMap;
      }),
      catchError(() => {
        this.loadAll$ = null;
        return of({} as Record<string, string>);
      }),
      shareReplay(1),
    );
    return this.loadAll$;
  }

  resolve(id: string): Observable<string> {
    if (this.cache.has(id)) return of(this.cache.get(id)!);
    return this.ensureLoaded().pipe(
      map(m => m[id] ?? id.substring(0, 12) + '…'),
    );
  }

  resolveMany(ids: string[]): Observable<Record<string, string>> {
    const unique = [...new Set(ids.filter(Boolean))];
    if (unique.length === 0) return of({});
    return this.ensureLoaded().pipe(
      map(m => {
        const result: Record<string, string> = {};
        for (const id of unique) {
          result[id] = m[id] ?? id.substring(0, 12) + '…';
        }
        return result;
      }),
    );
  }
}
