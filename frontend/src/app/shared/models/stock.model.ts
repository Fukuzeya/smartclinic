export interface DrugStock {
  id: string;
  drug_name: string;
  quantity_on_hand: number;
  unit: string;
  reorder_threshold: number;
  is_low_stock: boolean;
  last_updated_at: string;
}

export interface DrugStockListResponse {
  items: DrugStock[];
  total: number;
  limit: number;
  offset: number;
}
