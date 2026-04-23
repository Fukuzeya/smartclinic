import { Component, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { EncounterService, AISuggestionResponse } from '../../shared/api/encounter.service';

@Component({
  selector: 'app-ai-soap-copilot',
  standalone: true,
  imports: [DatePipe],
  template: `
    <div class="copilot-card">
      <div class="copilot-header">
        <span class="copilot-icon">🤖</span>
        <div>
          <div class="copilot-title">AI Clinical Copilot</div>
          <div class="copilot-subtitle">SOAP Note Assistant — ADR 0013</div>
        </div>
        @if (!suggestion()) {
          <button class="btn-ai" [disabled]="loading()" (click)="draft()">
            {{ loading() ? 'Generating…' : '✦ Draft SOAP Note' }}
          </button>
        }
      </div>

      @if (error()) {
        <div class="ai-error">{{ error() }}</div>
      }

      @if (suggestion()) {
        <div class="disclaimer-banner">
          ⚠ {{ suggestion()!.disclaimer }}
        </div>

        <pre class="soap-text">{{ suggestion()!.suggestion_text }}</pre>

        <div class="ai-meta">
          Model: <code>{{ suggestion()!.model_id }}</code> ·
          Generated: {{ suggestion()!.generated_at | date:'HH:mm:ss' }}
        </div>

        @if (!decision()) {
          <div class="action-row">
            <button class="btn-accept" (click)="decide('accepted')">✓ Accept into SOAP</button>
            <button class="btn-discard" (click)="decide('discarded')">✕ Discard</button>
          </div>
        } @else {
          <div class="decision-badge" [class.accepted]="decision() === 'accepted'"
               [class.discarded]="decision() === 'discarded'">
            {{ decision() === 'accepted' ? '✓ Accepted by clinician' : '✕ Discarded' }}
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .copilot-card {
      border: 2px solid var(--clr-brand);
      border-radius: 10px;
      padding: 16px;
      background: linear-gradient(135deg, #fafafa 0%, #f0f0ff 100%);
    }
    .copilot-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
    }
    .copilot-icon { font-size: 1.5rem; }
    .copilot-title { font-weight: 700; color: #1255A1; font-size: .95rem; }
    .copilot-subtitle { font-size: .7rem; color: var(--clr-gray-400); }
    .btn-ai {
      margin-left: auto;
      background: var(--clr-brand);
      color: #fff;
      border: none;
      border-radius: 4px;
      padding: 7px 14px;
      font-size: .8rem;
      font-weight: 600;
      cursor: pointer;
      transition: background .15s;
    }
    .btn-ai:hover:not(:disabled) { background: var(--clr-brand-dark); }
    .btn-ai:disabled { opacity: .6; cursor: default; }
    .disclaimer-banner {
      background: #fef9c3;
      border: 1px solid #fde047;
      color: #854d0e;
      border-radius: 6px;
      padding: 8px 12px;
      font-size: .75rem;
      margin-bottom: 12px;
    }
    .soap-text {
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 12px 14px;
      font-size: .82rem;
      font-family: 'Courier New', monospace;
      white-space: pre-wrap;
      line-height: 1.6;
      margin: 0 0 10px;
    }
    .ai-meta { font-size: .7rem; color: #94a3b8; margin-bottom: 10px; }
    .action-row { display: flex; gap: 8px; }
    .btn-accept {
      flex: 1;
      background: #d1fae5;
      color: #065f46;
      border: 1px solid #6ee7b7;
      border-radius: 6px;
      padding: 7px 14px;
      font-size: .8rem;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-accept:hover { background: #a7f3d0; }
    .btn-discard {
      flex: 1;
      background: #fee2e2;
      color: #991b1b;
      border: 1px solid #fca5a5;
      border-radius: 6px;
      padding: 7px 14px;
      font-size: .8rem;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-discard:hover { background: #fecaca; }
    .decision-badge {
      text-align: center;
      padding: 8px;
      border-radius: 6px;
      font-size: .8rem;
      font-weight: 600;
    }
    .decision-badge.accepted { background: #d1fae5; color: #065f46; }
    .decision-badge.discarded { background: #f1f5f9; color: #475569; }
    .ai-error { color: #991b1b; font-size: .8rem; margin-top: 8px; }
  `],
})
export class AiSoapCopilotComponent {
  encounterId = input.required<string>();

  private readonly svc = inject(EncounterService);

  suggestion = signal<AISuggestionResponse | null>(null);
  loading = signal(false);
  error = signal('');
  decision = signal<'accepted' | 'discarded' | null>(null);

  draft(): void {
    this.loading.set(true);
    this.error.set('');
    this.svc.draftSoapNote(this.encounterId()).subscribe({
      next: r => { this.suggestion.set(r); this.loading.set(false); },
      error: e => {
        this.error.set(e.error?.detail ?? 'AI draft failed — check service logs');
        this.loading.set(false);
      },
    });
  }

  decide(d: 'accepted' | 'discarded'): void {
    const s = this.suggestion();
    if (!s) return;
    this.svc.recordAIDecision(s.suggestion_id, d).subscribe();
    this.decision.set(d);
  }
}
