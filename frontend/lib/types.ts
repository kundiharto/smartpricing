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

// --- Biaya & perencanaan ---------------------------------------------------

export type DriverType = "SALES_UNITS" | "PRODUCTION_UNITS" | "REVENUE" | "LABOR_HOURS" | "MACHINE_HOURS" | "CUSTOM";
export type CostDriver = { id: string; code: string; name: string; driver_type: DriverType; unit_label: string | null };
export type Behavior = "FIXED" | "VARIABLE" | "SEMI_VARIABLE" | "STEP_FIXED" | "PERCENTAGE";
export type CostScope = "PRODUCT" | "PERIOD" | "ALLOCATION_POOL";
export type TierRow = { from_activity: Dec; to_activity: Dec; amount: Dec };

export type CostVersion = {
  id: string;
  version_number: number;
  effective_from: string;
  effective_to: string | null;
  data_nature: string;
  base_amount: Dec | null;
  rate: Dec | null;
  percentage: Dec | null;
  percentage_base: "REVENUE" | "COGS" | null;
  step_mode: "TABLE" | "CEILING" | null;
  tiers: TierRow[] | null;
  capacity_per_resource: Dec | null;
  cost_per_resource: Dec | null;
  max_resources: Dec | null;
  minimum_amount: Dec | null;
  maximum_amount: Dec | null;
  escalation_type: "NOMINAL" | "SIMPLE_PCT" | "COMPOUND_PCT" | null;
  escalation_rate: Dec | null;
  escalation_amount: Dec | null;
  escalation_frequency: string | null;
  escalation_cap: Dec | null;
  source_reference: string | null;
  created_at: string;
};

export type CostItem = {
  id: string;
  code: string;
  name: string;
  category: string;
  behavior_type: Behavior;
  cost_scope: CostScope;
  driver_id: string | null;
  period_months: number;
  description: string | null;
  status: string;
  row_version: number;
  updated_at: string;
  driver: CostDriver | null;
  current_version: CostVersion | null;
  has_allocation: boolean;
  versions?: CostVersion[];
  allocation?: { basis: string; driver_label: string | null; allow_unallocated: boolean; targets: { product_id: string; value: Dec | null }[] } | null;
};

export type CostPreviewRow = { code: string; name: string; category: string; behavior: string; scope: string; fixed: Dec; variable: Dec; total: Dec; tier?: Dec[]; resource_count?: Dec; capacity_exceeded?: boolean; escalation?: string };
export type CostPreview = EngineResult & { values: { items: CostPreviewRow[]; fixed_total: Dec; variable_total: Dec; total: Dec }; items_without_version: string[]; excluded_product_scope: string[] };

export type Assumptions = {
  price_change: Dec;
  volume_change: Dec;
  unit_cost_change: Dec;
  variable_cost_change: Dec;
  fixed_cost_change: Dec;
  item_changes: Record<string, Dec>;
  product_volume_changes: Record<string, Dec>;
  other_activity: Record<string, Dec>;
  tax_regime: "NONE" | "PROFIT_BASED" | "TURNOVER_FINAL";
  tax_rate: Dec;
  exempt_turnover: Dec;
  target_kind: "OPERATING_PROFIT" | "NET_PROFIT" | null;
  target_amount: Dec | null;
  data_nature: string;
};

export type SalesLine = { product_id: string; unit_price: Dec; volume: Dec; unit_cost_override: Dec | null; sku: string; product_name: string; active_unit_cost: Dec | null };
export type RunSummary = { id: string; created_at: string; status: string; revenue: Dec | null; operating_profit: Dec | null; net_profit: Dec | null; break_even_units: Dec | null; warnings: Warning[] };

export type Scenario = {
  id: string;
  name: string;
  description: string | null;
  scenario_type: "BASE" | "OPTIMISTIC" | "PESSIMISTIC" | "CUSTOM";
  base_scenario_id: string | null;
  period_start: string;
  period_months: number;
  assumptions: Assumptions;
  status: string;
  row_version: number;
  updated_at: string;
  lines: SalesLine[];
  latest_run: RunSummary | null;
};

export type Pnl = {
  revenue: Dec; cogs: Dec; gross_profit: Dec; gross_margin: Dec; variable_costs: Dec; contribution: Dec; contribution_margin: Dec;
  fixed_costs: Dec; operating_profit: Dec; operating_margin: Dec; income_tax: Dec; net_profit: Dec; net_margin: Dec;
};
export type BreakEven = {
  status: string; units: Dec | null; revenue: Dec | null; margin_of_safety: Dec | null; average_price: Dec; average_unit_cost: Dec;
  unit_contribution: Dec; profitable_ranges: Dec[][]; modeled_up_to_units: Dec; assumption: string;
};
export type PlanTarget = { kind: string; amount: Dec; status: string; units: Dec | null; revenue: Dec | null; change_vs_plan: Dec | null; achieved: boolean; capacity_exceeded_items?: string[] };
export type PlanLine = {
  product: string; unit_price: Dec; unit_cost: Dec; volume: Dec; revenue: Dec; cogs: Dec; variable_costs: Dec; contribution: Dec;
  contribution_margin: Dec | null; allocated_costs: Dec; profit_after_allocation: Dec;
};
export type PlanValues = {
  period_months: number; pnl: Pnl; units: Dec; lines: PlanLine[]; costs: CostPreviewRow[]; costs_by_category: Record<string, Dec>;
  excluded_product_scope: string[]; break_even: BreakEven; target: PlanTarget | null; company_level_costs: Dec; unattributed_variable_costs: Dec;
};
export type Run = {
  id: string; scenario_id: string; engine_version: string; input_hash: string; status: string; created_at: string;
  input_snapshot: Record<string, unknown>;
  result_snapshot: EngineResult & { values: PlanValues; products: Record<string, { sku: string; name: string }>; items_without_version: string[] };
};
export type CompareEntry = {
  scenario_id: string; name: string; scenario_type: string; period_start: string; period_months: number; status: string;
  message?: string | null; pnl?: Pnl; break_even?: BreakEven; target?: PlanTarget | null; units?: Dec; warnings?: Warning[];
};
