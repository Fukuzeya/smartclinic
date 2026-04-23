import { Component, inject, signal, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { StockService } from '../../shared/api/stock.service';
import { DrugStock } from '../../shared/models/stock.model';

@Component({
  selector: 'app-stock-list',
  standalone: true,
  imports: [DatePipe, FormsModule],
  template: `
    <div class="page-header">
      <h1 class="page-title">Drug Stock Management</h1>
      <button class="btn-primary" (click)="showAddForm = !showAddForm">
        {{ showAddForm ? '✕ Cancel' : '+ Add Drug' }}
      </button>
    </div>

    <!-- Add New Drug Form -->
    @if (showAddForm) {
      <div class="card add-form-card">
        <h3 class="card-title">Add New Drug to Inventory</h3>
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Drug Name</label>
            <input class="form-control" [(ngModel)]="newDrug.drug_name" placeholder="e.g. Amoxicillin" />
          </div>
          <div class="form-group">
            <label class="form-label">Initial Qty</label>
            <input class="form-control" type="number" [(ngModel)]="newDrug.quantity" placeholder="0" />
          </div>
          <div class="form-group">
            <label class="form-label">Unit</label>
            <select class="form-control" [(ngModel)]="newDrug.unit">
              <option value="tablets">Tablets</option>
              <option value="capsules">Capsules</option>
              <option value="inhalers">Inhalers</option>
              <option value="vials">Vials</option>
              <option value="bottles">Bottles</option>
              <option value="tubes">Tubes</option>
              <option value="ampoules">Ampoules</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Reorder Threshold</label>
            <input class="form-control" type="number" [(ngModel)]="newDrug.reorder_threshold" placeholder="50" />
          </div>
        </div>
        <button class="btn-primary" style="margin-top:12px" [disabled]="!newDrug.drug_name"
                (click)="addDrug()">Add to Inventory</button>
        @if (addError()) { <div class="alert-error" style="margin-top:8px">{{ addError() }}</div> }
      </div>
    }

    <!-- Filter bar -->
    <div class="filter-bar">
      <div class="search-box">
        <input class="form-control" placeholder="Search drugs…" [(ngModel)]="searchTerm"
               (ngModelChange)="onSearch()" />
      </div>
      <label class="low-stock-toggle">
        <input type="checkbox" [(ngModel)]="lowStockOnly" (ngModelChange)="load()" />
        <span class="toggle-label">Low stock only</span>
        @if (lowStockCount() > 0) {
          <span class="low-count-badge">{{ lowStockCount() }}</span>
        }
      </label>
    </div>

    @if (loading()) {
      <div class="loading">Loading inventory…</div>
    } @else if (drugs().length === 0) {
      <div class="empty-state">No drugs found.</div>
    } @else {
      <!-- Stats bar -->
      <div class="stats-bar">
        <div class="stat-item">
          <span class="stat-value">{{ drugs().length }}</span>
          <span class="stat-label">Total drugs</span>
        </div>
        <div class="stat-item stat-warn">
          <span class="stat-value">{{ lowStockCount() }}</span>
          <span class="stat-label">Low stock</span>
        </div>
        <div class="stat-item stat-danger">
          <span class="stat-value">{{ outOfStockCount() }}</span>
          <span class="stat-label">Out of stock</span>
        </div>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>Drug Name</th>
            <th>On Hand</th>
            <th>Unit</th>
            <th>Reorder At</th>
            <th>Status</th>
            <th>Last Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          @for (drug of drugs(); track drug.id) {
            <tr [class.low-stock-row]="drug.is_low_stock" [class.oos-row]="drug.quantity_on_hand <= 0">
              <td class="drug-name-cell">{{ drug.drug_name }}</td>
              <td class="qty-cell">
                <span class="qty-value" [class.qty-low]="drug.is_low_stock" [class.qty-oos]="drug.quantity_on_hand <= 0">
                  {{ drug.quantity_on_hand }}
                </span>
              </td>
              <td>{{ drug.unit }}</td>
              <td>{{ drug.reorder_threshold }}</td>
              <td>
                @if (drug.quantity_on_hand <= 0) {
                  <span class="badge badge-oos">Out of Stock</span>
                } @else if (drug.is_low_stock) {
                  <span class="badge badge-low">Low Stock</span>
                } @else {
                  <span class="badge badge-ok">In Stock</span>
                }
              </td>
              <td class="date-cell">{{ drug.last_updated_at | date:'dd MMM HH:mm' }}</td>
              <td class="actions-cell">
                <button class="btn-action btn-receive" title="Receive stock"
                        (click)="openReceive(drug)">+ Receive</button>
                <button class="btn-action btn-adjust" title="Adjust quantity"
                        (click)="openAdjust(drug)">✎ Adjust</button>
              </td>
            </tr>

            <!-- Receive stock inline form -->
            @if (activeReceive()?.id === drug.id) {
              <tr class="inline-form-row">
                <td colspan="7">
                  <div class="inline-form-content">
                    <strong>Receive stock for {{ drug.drug_name }}</strong>
                    <div class="inline-fields">
                      <input class="form-control" type="number" [(ngModel)]="receiveQty"
                             placeholder="Quantity received" min="1" />
                      <input class="form-control" [(ngModel)]="receiveReason"
                             placeholder="Reason (e.g. Supplier delivery)" />
                      <button class="btn-primary btn-sm" [disabled]="!receiveQty || receiveQty <= 0"
                              (click)="submitReceive(drug)">Confirm</button>
                      <button class="btn-secondary btn-sm" (click)="cancelAction()">Cancel</button>
                    </div>
                    @if (actionError()) { <div class="alert-error" style="margin-top:6px">{{ actionError() }}</div> }
                  </div>
                </td>
              </tr>
            }

            <!-- Adjust stock inline form -->
            @if (activeAdjust()?.id === drug.id) {
              <tr class="inline-form-row">
                <td colspan="7">
                  <div class="inline-form-content">
                    <strong>Adjust stock for {{ drug.drug_name }}</strong>
                    <span class="current-qty">Current: {{ drug.quantity_on_hand }} {{ drug.unit }}</span>
                    <div class="inline-fields">
                      <input class="form-control" type="number" [(ngModel)]="adjustQty"
                             placeholder="New quantity" min="0" />
                      <input class="form-control" [(ngModel)]="adjustReason"
                             placeholder="Reason for adjustment (required)" />
                      <button class="btn-primary btn-sm"
                              [disabled]="adjustQty == null || !adjustReason"
                              (click)="submitAdjust(drug)">Confirm</button>
                      <button class="btn-secondary btn-sm" (click)="cancelAction()">Cancel</button>
                    </div>
                    @if (actionError()) { <div class="alert-error" style="margin-top:6px">{{ actionError() }}</div> }
                  </div>
                </td>
              </tr>
            }
          }
        </tbody>
      </table>
    }
  `,
  styles: [`
    .add-form-card { margin-bottom: 16px; border: 2px solid var(--clr-accent); }
    .form-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 12px; }
    @media (max-width: 768px) { .form-grid { grid-template-columns: 1fr 1fr; } }
    .form-group { display: flex; flex-direction: column; gap: 4px; }
    .form-label { font-size: 0.78rem; font-weight: 600; color: var(--clr-gray-500); text-transform: uppercase; letter-spacing: 0.05em; }

    .filter-bar { display: flex; gap: 16px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
    .search-box { flex: 1; min-width: 200px; }
    .search-box .form-control { width: 100%; }
    .low-stock-toggle { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: var(--clr-gray-700); cursor: pointer; white-space: nowrap; }
    .toggle-label { font-weight: 500; }
    .low-count-badge { background: #fef3c7; color: #92400e; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 10px; }

    .stats-bar { display: flex; gap: 16px; margin-bottom: 16px; }
    .stat-item { background: #fff; border: 1px solid var(--clr-gray-200); border-radius: 8px; padding: 12px 20px; display: flex; flex-direction: column; align-items: center; min-width: 100px; }
    .stat-value { font-size: 1.4rem; font-weight: 700; color: var(--clr-gray-800); }
    .stat-label { font-size: 0.72rem; color: var(--clr-gray-500); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500; }
    .stat-warn .stat-value { color: #d97706; }
    .stat-danger .stat-value { color: #dc2626; }

    .drug-name-cell { font-weight: 600; color: var(--clr-gray-800); }
    .qty-cell { font-variant-numeric: tabular-nums; }
    .qty-value { font-weight: 700; font-size: 0.95rem; }
    .qty-low { color: #d97706; }
    .qty-oos { color: #dc2626; }
    .date-cell { font-size: 0.8rem; color: var(--clr-gray-500); }

    .badge-ok { background: #d1fae5; color: #065f46; }
    .badge-low { background: #fef3c7; color: #92400e; }
    .badge-oos { background: #fee2e2; color: #991b1b; }

    .low-stock-row { background: #fffbeb; }
    .oos-row { background: #fef2f2; }

    .actions-cell { display: flex; gap: 6px; }
    .btn-action { padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid; transition: background 0.15s; }
    .btn-receive { background: #ecfdf5; color: #059669; border-color: #a7f3d0; }
    .btn-receive:hover { background: #d1fae5; }
    .btn-adjust { background: #f0f9ff; color: #0284c7; border-color: #bae6fd; }
    .btn-adjust:hover { background: #e0f2fe; }

    .inline-form-row td { background: #f8fafc; padding: 12px 16px !important; }
    .inline-form-content { display: flex; flex-direction: column; gap: 8px; }
    .inline-fields { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .inline-fields .form-control { min-width: 120px; flex: 1; }
    .current-qty { font-size: 0.82rem; color: var(--clr-gray-500); }
    .btn-sm { padding: 6px 14px; font-size: 0.8rem; }
  `],
})
export class StockListComponent implements OnInit {
  private readonly svc = inject(StockService);

  drugs = signal<DrugStock[]>([]);
  allDrugs = signal<DrugStock[]>([]);
  loading = signal(true);
  lowStockOnly = false;
  searchTerm = '';
  showAddForm = false;

  activeReceive = signal<DrugStock | null>(null);
  activeAdjust = signal<DrugStock | null>(null);
  actionError = signal('');
  addError = signal('');

  receiveQty: number | null = null;
  receiveReason = 'Received from supplier';
  adjustQty: number | null = null;
  adjustReason = '';

  newDrug = { drug_name: '', quantity: 0, unit: 'tablets', reorder_threshold: 50 };

  lowStockCount = signal(0);
  outOfStockCount = signal(0);

  private searchTimeout: any;

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.svc.list(this.lowStockOnly, this.searchTerm || undefined).subscribe({
      next: r => {
        this.drugs.set(r.items);
        this.loading.set(false);
        // Always compute stats from unfiltered list
        if (!this.lowStockOnly && !this.searchTerm) {
          this.allDrugs.set(r.items);
          this.computeStats(r.items);
        }
      },
      error: () => this.loading.set(false),
    });
    // If filtered, also fetch all for stats
    if (this.lowStockOnly || this.searchTerm) {
      this.svc.list(false).subscribe(r => {
        this.allDrugs.set(r.items);
        this.computeStats(r.items);
      });
    }
  }

  private computeStats(items: DrugStock[]): void {
    this.lowStockCount.set(items.filter(d => d.is_low_stock).length);
    this.outOfStockCount.set(items.filter(d => d.quantity_on_hand <= 0).length);
  }

  onSearch(): void {
    clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => this.load(), 300);
  }

  openReceive(drug: DrugStock): void {
    this.cancelAction();
    this.activeReceive.set(drug);
    this.receiveQty = null;
    this.receiveReason = 'Received from supplier';
  }

  openAdjust(drug: DrugStock): void {
    this.cancelAction();
    this.activeAdjust.set(drug);
    this.adjustQty = drug.quantity_on_hand;
    this.adjustReason = '';
  }

  cancelAction(): void {
    this.activeReceive.set(null);
    this.activeAdjust.set(null);
    this.actionError.set('');
  }

  submitReceive(drug: DrugStock): void {
    if (!this.receiveQty || this.receiveQty <= 0) return;
    this.actionError.set('');
    this.svc.receiveStock(drug.drug_name, this.receiveQty, this.receiveReason).subscribe({
      next: () => { this.cancelAction(); this.load(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Failed to receive stock'),
    });
  }

  submitAdjust(drug: DrugStock): void {
    if (this.adjustQty == null || !this.adjustReason) return;
    this.actionError.set('');
    this.svc.adjustStock(drug.drug_name, this.adjustQty, this.adjustReason).subscribe({
      next: () => { this.cancelAction(); this.load(); },
      error: e => this.actionError.set(e.error?.detail ?? 'Failed to adjust stock'),
    });
  }

  addDrug(): void {
    if (!this.newDrug.drug_name) return;
    this.addError.set('');
    this.svc.addDrug(
      this.newDrug.drug_name,
      this.newDrug.quantity,
      this.newDrug.unit,
      this.newDrug.reorder_threshold,
    ).subscribe({
      next: () => {
        this.showAddForm = false;
        this.newDrug = { drug_name: '', quantity: 0, unit: 'tablets', reorder_threshold: 50 };
        this.load();
      },
      error: e => this.addError.set(e.error?.detail ?? 'Failed to add drug'),
    });
  }
}
