import { Component, input, OnInit, signal, inject } from '@angular/core';
import { DatePipe, NgClass } from '@angular/common';
import { EncounterService, EncounterEventRecord, EncounterEventStream } from '../../shared/api/encounter.service';

/** Human-readable labels for every clinical event type */
const EVENT_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  'clinical.encounter.started.v1':              { label: 'Encounter Opened',      icon: '◆', color: '#1255A1' },
  'clinical.encounter.vital_signs_recorded.v1': { label: 'Vitals Recorded',        icon: '◆', color: '#0EA5E9' },
  'clinical.encounter.soap_note_added.v1':      { label: 'SOAP Note Added',        icon: '◆', color: '#0EA5E9' },
  'clinical.encounter.diagnosis_recorded.v1':   { label: 'Diagnosis Recorded',     icon: '◆', color: '#1772C9' },
  'clinical.encounter.prescription_issued.v1':  { label: 'Prescription Issued',    icon: '◆', color: '#059669' },
  'clinical.encounter.lab_order_placed.v1':     { label: 'Lab Order Placed',       icon: '◆', color: '#D97706' },
  'clinical.encounter.closed.v1':               { label: 'Encounter Closed',       icon: '◆', color: '#15803D' },
  'clinical.encounter.voided.v1':               { label: 'Encounter Voided',       icon: '◆', color: '#DC2626' },
};

function labelFor(eventType: string) {
  return EVENT_LABELS[eventType] ?? { label: eventType.replace(/clinical\.encounter\./,'').replace(/\.v\d+$/,'').replace(/_/g,' '), icon: '📌', color: '#94a3b8' };
}

@Component({
  selector: 'app-encounter-timeline',
  standalone: true,
  imports: [DatePipe, NgClass],
  template: `
    <div class="timeline-header">
      <h3 class="section-title">Event Timeline
        <span class="event-count">{{ stream()?.event_count ?? 0 }} events</span>
      </h3>
      @if (stream()) {
        <span class="chain-badge" [ngClass]="stream()!.chain_valid ? 'chain-ok' : 'chain-broken'">
          {{ stream()!.chain_valid ? '🔒 Chain intact' : '⚠ Chain broken' }}
        </span>
      }
    </div>

    @if (loading()) {
      <div class="timeline-loading">Loading event history…</div>
    } @else if (!stream()) {
      <div class="timeline-empty">No events found.</div>
    } @else {
      <div class="timeline">
        @for (ev of stream()!.events; track ev.sequence) {
          <div class="tl-item" [ngClass]="{ 'tl-terminal': ev.event_type.includes('closed') || ev.event_type.includes('voided') }">
            <div class="tl-dot" [style.background]="labelFor(ev.event_type).color">
              {{ labelFor(ev.event_type).icon }}
            </div>
            <div class="tl-line"></div>
            <div class="tl-body">
              <div class="tl-top">
                <span class="tl-label" [style.color]="labelFor(ev.event_type).color">
                  {{ labelFor(ev.event_type).label }}
                </span>
                <span class="tl-seq">#{{ ev.sequence }}</span>
              </div>
              <div class="tl-time">{{ ev.occurred_at | date:'dd MMM yyyy HH:mm:ss' }}</div>

              <!-- Key payload fields rendered per event type -->
              @if (summaryLines(ev).length) {
                <ul class="tl-details">
                  @for (line of summaryLines(ev); track line) {
                    <li>{{ line }}</li>
                  }
                </ul>
              }

              <div class="tl-hash" title="Chain hash prefix (SHA-256 tamper evidence)">
                🔗 <code>{{ ev.chain_hash_prefix }}…</code>
              </div>
            </div>
          </div>
        }
      </div>

      <div class="chain-footer">
        <span class="chain-badge" [ngClass]="stream()!.chain_valid ? 'chain-ok' : 'chain-broken'">
          {{ stream()!.chain_message }}
        </span>
        <span style="font-size:0.75rem;color:var(--clr-gray-400);margin-left:8px">
          ADR-0012 · Hash-chained event store
        </span>
      </div>
    }
  `,
  styles: [`
    .timeline-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }
    .section-title {
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--clr-gray-700);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .event-count {
      font-size: 0.75rem;
      color: var(--clr-gray-400);
      font-weight: 400;
      background: var(--clr-gray-100);
      padding: 2px 8px;
      border-radius: 20px;
    }
    .chain-badge {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 20px;
    }
    .chain-ok { background: #d1fae5; color: #065f46; }
    .chain-broken { background: #fee2e2; color: #991b1b; }
    .timeline-loading, .timeline-empty { color: var(--clr-gray-400); font-size: 0.875rem; padding: 12px 0; }
    .timeline { position: relative; padding-left: 0; }
    .tl-item {
      display: flex;
      gap: 12px;
      position: relative;
      padding-bottom: 20px;
    }
    .tl-item:last-child { padding-bottom: 0; }
    .tl-item:last-child .tl-line { display: none; }
    .tl-dot {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.9rem;
      flex-shrink: 0;
      color: #fff;
      position: relative;
      z-index: 1;
    }
    .tl-line {
      position: absolute;
      left: 15px;
      top: 32px;
      width: 2px;
      bottom: 0;
      background: var(--clr-gray-200);
    }
    .tl-body { flex: 1; padding-top: 4px; }
    .tl-top { display: flex; align-items: center; gap: 8px; }
    .tl-label { font-weight: 600; font-size: 0.875rem; }
    .tl-seq { font-size: 0.7rem; color: var(--clr-gray-400); background: var(--clr-gray-50); border: 1px solid var(--clr-gray-200); padding: 1px 6px; border-radius: 10px; }
    .tl-time { font-size: 0.75rem; color: var(--clr-gray-400); margin-top: 2px; }
    .tl-details {
      list-style: none;
      padding: 6px 0 0;
      margin: 0;
      font-size: 0.8rem;
      color: var(--clr-gray-600);
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .tl-details li::before { content: '· '; color: var(--clr-gray-400); }
    .tl-hash { margin-top: 6px; font-size: 0.7rem; color: var(--clr-gray-400); }
    .tl-hash code { background: var(--clr-gray-100); padding: 1px 4px; border-radius: 3px; }
    .chain-footer { margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--clr-gray-200); }
    .tl-item.tl-terminal .tl-dot { box-shadow: 0 0 0 4px rgba(16,185,129,0.2); }
  `],
})
export class EncounterTimelineComponent implements OnInit {
  encounterId = input.required<string>();
  private readonly svc = inject(EncounterService);

  stream = signal<EncounterEventStream | null>(null);
  loading = signal(true);

  ngOnInit(): void {
    this.svc.getEventStream(this.encounterId()).subscribe({
      next: s => { this.stream.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  readonly labelFor = labelFor;

  summaryLines(ev: EncounterEventRecord): string[] {
    const p = ev.payload;
    switch (ev.event_type) {
      case 'clinical.encounter.started.v1':
        return [`Patient: ${p['patient_id']}`, `Doctor: ${p['doctor_id']}`];
      case 'clinical.encounter.vital_signs_recorded.v1':
        return Object.entries(p)
          .filter(([k]) => !['encounter_id','aggregate_id'].includes(k) && p[k] != null)
          .map(([k, v]) => `${k.replace(/_/g,' ')}: ${v}`);
      case 'clinical.encounter.diagnosis_recorded.v1':
        return [`ICD-10: ${(p as any)?.icd10_code ?? (p as any)?.code ?? ''}  ${(p as any)?.description ?? ''}`];
      case 'clinical.encounter.prescription_issued.v1': {
        const lines = (p['lines'] as any[]) ?? [];
        return lines.map((l: any) => `${l.drug_name} ${l.dose} ${l.frequency}`);
      }
      case 'clinical.encounter.lab_order_placed.v1': {
        const tests = (p['tests'] as any[]) ?? [];
        return tests.map((t: any) => `${t.test_code} (${t.urgency ?? 'routine'})`);
      }
      case 'clinical.encounter.closed.v1':
        return [`Primary ICD-10: ${p['primary_icd10'] ?? 'none'}`, `Prescription: ${p['has_prescription'] ? 'yes' : 'no'}`, `Lab order: ${p['has_lab_order'] ? 'yes' : 'no'}`];
      default:
        return [];
    }
  }
}
