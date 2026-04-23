import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env';
import { DrugStock, DrugStockListResponse } from '../models/stock.model';

@Injectable({ providedIn: 'root' })
export class StockService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.api.pharmacy}/drug-stock`;

  list(lowStockOnly = false, search?: string): Observable<DrugStockListResponse> {
    let params = new HttpParams().set('limit', 200);
    if (lowStockOnly) params = params.set('low_stock_only', true);
    if (search) params = params.set('search', search);
    return this.http.get<DrugStockListResponse>(this.base, { params });
  }

  get(drugName: string): Observable<DrugStock> {
    return this.http.get<DrugStock>(`${this.base}/${encodeURIComponent(drugName)}`);
  }

  receiveStock(drugName: string, quantity: number, reason = 'Received from supplier'): Observable<DrugStock> {
    return this.http.post<DrugStock>(
      `${this.base}/${encodeURIComponent(drugName)}/receive`,
      { quantity, reason },
    );
  }

  adjustStock(drugName: string, newQuantity: number, reason: string): Observable<DrugStock> {
    return this.http.post<DrugStock>(
      `${this.base}/${encodeURIComponent(drugName)}/adjust`,
      { new_quantity: newQuantity, reason },
    );
  }

  addDrug(drugName: string, quantityOnHand: number, unit: string, reorderThreshold: number): Observable<DrugStock> {
    return this.http.post<DrugStock>(this.base, {
      drug_name: drugName,
      quantity_on_hand: quantityOnHand,
      unit,
      reorder_threshold: reorderThreshold,
    });
  }
}
