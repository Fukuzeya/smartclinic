import { Injectable, inject } from '@angular/core';
import { Observable, of, forkJoin } from 'rxjs';
import { map, tap, catchError, shareReplay } from 'rxjs/operators';
import { PatientService } from '../api/patient.service';

/**
 * Shared cache that resolves patient IDs to display names.
 * Caches results in-memory so repeated lookups are instant.
 */
@Injectable({ providedIn: 'root' })
export class PatientNameCache {
  private readonly patientSvc = inject(PatientService);
  private readonly cache = new Map<string, string>();
  private readonly pending = new Map<string, Observable<string>>();

  resolve(id: string): Observable<string> {
    if (this.cache.has(id)) return of(this.cache.get(id)!);
    if (this.pending.has(id)) return this.pending.get(id)!;
    const req$ = this.patientSvc.get(id).pipe(
      map(p => p.display_name),
      catchError(() => of(id.substring(0, 12) + '…')),
      tap(name => { this.cache.set(id, name); this.pending.delete(id); }),
      shareReplay(1),
    );
    this.pending.set(id, req$);
    return req$;
  }

  resolveMany(ids: string[]): Observable<Record<string, string>> {
    const unique = [...new Set(ids.filter(Boolean))];
    if (unique.length === 0) return of({});
    const requests: Record<string, Observable<string>> = {};
    for (const id of unique) {
      requests[id] = this.resolve(id);
    }
    return forkJoin(requests);
  }

  getCached(id: string): string {
    return this.cache.get(id) ?? '';
  }
}
