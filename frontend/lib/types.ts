// Angka finansial dari API selalu string desimal; frontend tidak menghitung, hanya menampilkan.
export type Dec = string;

export type User = { id: string; email: string; full_name: string; preferred_language: "id" | "en"; status: string };
export type Membership = { organization_id: string; organization_name: string; roles: string[] };
export type Me = { user: User; memberships: Membership[] };

export type Organization = {
  id: string;
  name: string;
  slug: string;
  default_currency: string;
  default_language: "id" | "en";
  fiscal_year_start_month: number;
  timezone: string;
  status: string;
  row_version: number;
  business_models: string[];
  primary_business_model: string | null;
  is_hybrid: boolean;
  my_roles: string[];
  my_permissions: string[];
};

export type Member = { member_id: string; user_id: string; email: string; full_name: string; status: string; roles: string[] };
export type Unit = { id: string; code: string; name: string; dimension: string };
export type Category = { id: string; name: string; parent_id: string | null };

export type ProductType = "FINISHED_GOOD" | "MATERIAL" | "TRADED_GOOD" | "SERVICE";
export type Product = {
  id: string;
  sku: string;
  name: string;
  product_type: ProductType;
  business_model: string;
  pricing_model_type: string;
  base_unit_id: string;
  category_id: string | null;
  description: string | null;
  status: string;
  row_version: number;
  created_at: string;
  updated_at: string;
};

export type MaterialPrice = {
  id: string;
  material_product_id: string;
  unit_price: Dec;
  currency: string;
  effective_from: string;
  effective_to: string | null;
  data_nature: string;
  supplier_name: string | null;
  source_reference: string | null;
};

export type BomItem = { id: string; line_no: number; material_product_id: string; net_quantity: Dec; material_waste_rate: Dec };
export type Bom = {
  id: string;
  product_id: string;
  version_number: number;
  planned_output_qty: Dec;
  process_yield_rate: Dec;
  status: string;
  effective_from: string;
  effective_to: string | null;
  notes: string | null;
  items: BomItem[];
};

export type EngineResult = {
  calculation: string;
  status: string;
  values: Record<string, unknown>;
  warnings: { code: string; message: string }[];
  trace: string[];
  message: string | null;
  engine_version: string;
  input_hash: string;
};

export type CostingVersion = {
  id: string;
  product_id: string;
  version_number: number;
  costing_method: string;
  costing_structure: string;
  data_nature: string;
  calculated_unit_cost: Dec;
  currency: string;
  as_of_date: string;
  effective_from: string;
  effective_to: string | null;
  status: string;
  engine_version: string;
  input_hash: string;
  created_at: string;
  bom_id?: string | null;
  input_snapshot?: Record<string, unknown>;
  calculation_snapshot?: EngineResult & Record<string, unknown>;
};

export type Warning = { code: string; message: string };

export type PriceSummary = {
  currency: string;
  unit_cost: Dec;
  costing_version_id: string | null;
  minimum_price: Dec | null;
  target_price: Dec;
  recommended_price: Dec;
  list_price: Dec;
  gross_margin: Dec;
  contribution_margin: Dec;
  fee_total: Dec;
  contribution: Dec;
  warnings: Warning[];
  engine: { price: EngineResult; rounding: EngineResult | null; final: EngineResult };
};

export type Recommendation = {
  id: string;
  product_id: string;
  costing_version_id: string;
  pricing_method: string;
  margin_definition: string;
  minimum_price: Dec | null;
  target_price: Dec;
  recommended_price: Dec;
  list_price: Dec;
  expected_gross_margin: Dec | null;
  expected_contribution_margin: Dec | null;
  currency: string;
  effective_date: string;
  warnings: Warning[];
  unit_cost: Dec | null;
  engine_version: string;
  input_hash: string;
  status: string;
  created_at: string;
  input_snapshot?: Record<string, unknown>;
  calculation_snapshot?: PriceSummary;
};

export type AuditLog = {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  request_id: string | null;
  created_at: string;
};
