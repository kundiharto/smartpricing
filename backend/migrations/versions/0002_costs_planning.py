"""Cost management, allocation rules, scenarios and simulation runs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP_ROLE = "spe_app"

TENANT_TABLES = [
    "cost_drivers",
    "cost_items",
    "cost_item_versions",
    "cost_allocation_rules",
    "cost_allocation_targets",
    "scenarios",
    "scenario_sales_lines",
    "simulation_runs",
]

NEW_PERMISSIONS = {
    "costs.read": "Melihat struktur biaya",
    "costs.write": "Mengelola biaya, driver, dan alokasi",
    "planning.read": "Melihat skenario dan hasil simulasi",
    "planning.write": "Membuat dan menjalankan skenario",
}

GRANTS = {
    "OWNER": ["costs.read", "costs.write", "planning.read", "planning.write"],
    "DIRECTOR": ["costs.read", "planning.read", "planning.write"],
    "FINANCE_MANAGER": ["costs.read", "costs.write", "planning.read", "planning.write"],
    "FINANCIAL_ANALYST": ["costs.read", "costs.write", "planning.read", "planning.write"],
    "OPERATIONS_MANAGER": ["costs.read", "costs.write", "planning.read"],
    "SALES_MANAGER": ["planning.read"],
    "VIEWER": ["costs.read", "planning.read"],
}

SCHEMA = r"""
CREATE TABLE cost_drivers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  code            text NOT NULL,
  name            text NOT NULL,
  driver_type     text NOT NULL CHECK (driver_type IN ('SALES_UNITS', 'PRODUCTION_UNITS', 'REVENUE', 'LABOR_HOURS', 'MACHINE_HOURS', 'CUSTOM')),
  unit_label      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code)
);

CREATE TABLE cost_items (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  code            text NOT NULL,
  name            text NOT NULL,
  category        text NOT NULL CHECK (category IN (
                    'DIRECT_MATERIAL', 'DIRECT_LABOR', 'PRODUCTION_OVERHEAD', 'FIXED_OPERATING', 'VARIABLE_OPERATING',
                    'SELLING', 'DISTRIBUTION', 'ADMINISTRATIVE', 'FINANCIAL', 'TAX_STATUTORY', 'OTHER')),
  behavior_type   text NOT NULL CHECK (behavior_type IN ('FIXED', 'VARIABLE', 'SEMI_VARIABLE', 'STEP_FIXED', 'PERCENTAGE')),
  cost_scope      text NOT NULL CHECK (cost_scope IN ('PRODUCT', 'PERIOD', 'ALLOCATION_POOL')),
  driver_id       uuid,
  period_months   smallint NOT NULL DEFAULT 1 CHECK (period_months IN (1, 3, 6, 12)),
  description     text,
  status          text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      uuid REFERENCES users(id),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  row_version     integer NOT NULL DEFAULT 1,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code),
  FOREIGN KEY (organization_id, driver_id) REFERENCES cost_drivers (organization_id, id),
  CHECK (behavior_type IN ('FIXED', 'PERCENTAGE') OR driver_id IS NOT NULL)
);
CREATE INDEX ix_cost_items_org_status ON cost_items (organization_id, status);
CREATE TRIGGER trg_cost_item_touch BEFORE UPDATE ON cost_items FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Parameter biaya berversi tanggal. Nilai tidak pernah diubah; versi baru menutup versi lama.
CREATE TABLE cost_item_versions (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id       uuid NOT NULL REFERENCES organizations(id),
  cost_item_id          uuid NOT NULL,
  version_number        integer NOT NULL CHECK (version_number > 0),
  effective_from        date NOT NULL,
  effective_to          date,
  data_nature           text NOT NULL DEFAULT 'STANDARD' CHECK (data_nature IN ('ACTUAL', 'STANDARD', 'ESTIMATE', 'SCENARIO')),
  base_amount           numeric(20,4) CHECK (base_amount >= 0),
  rate                  numeric(20,6) CHECK (rate >= 0),
  percentage            numeric(12,6) CHECK (percentage >= 0 AND percentage < 1),
  percentage_base       text CHECK (percentage_base IN ('REVENUE', 'COGS')),
  step_mode             text CHECK (step_mode IN ('TABLE', 'CEILING')),
  tiers                 jsonb,
  capacity_per_resource numeric(20,6) CHECK (capacity_per_resource > 0),
  cost_per_resource     numeric(20,4) CHECK (cost_per_resource >= 0),
  max_resources         numeric(20,6),
  minimum_amount        numeric(20,4),
  maximum_amount        numeric(20,4),
  escalation_type       text CHECK (escalation_type IN ('NOMINAL', 'SIMPLE_PCT', 'COMPOUND_PCT')),
  escalation_rate       numeric(12,6),
  escalation_amount     numeric(20,4),
  escalation_frequency  text CHECK (escalation_frequency IN ('MONTHLY', 'QUARTERLY', 'SEMIANNUAL', 'ANNUAL')),
  escalation_cap        numeric(20,4),
  source_reference      text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  created_by            uuid REFERENCES users(id),
  UNIQUE (organization_id, id),
  UNIQUE (cost_item_id, version_number),
  CHECK (effective_to IS NULL OR effective_to > effective_from),
  FOREIGN KEY (organization_id, cost_item_id) REFERENCES cost_items (organization_id, id),
  EXCLUDE USING gist (
    organization_id WITH =, cost_item_id WITH =, data_nature WITH =,
    daterange(effective_from, effective_to, '[)') WITH &&
  )
);

CREATE FUNCTION protect_cost_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW) - 'effective_to') IS DISTINCT FROM (to_jsonb(OLD) - 'effective_to') THEN
    RAISE EXCEPTION 'versi biaya % bersifat immutable; hanya effective_to yang boleh berubah', OLD.id
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_cost_version_immutable BEFORE UPDATE ON cost_item_versions
  FOR EACH ROW EXECUTE FUNCTION protect_cost_version();

CREATE TABLE cost_allocation_rules (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id   uuid NOT NULL REFERENCES organizations(id),
  cost_item_id      uuid NOT NULL,
  basis             text NOT NULL CHECK (basis IN ('EQUAL', 'PERCENTAGE', 'DRIVER', 'REVENUE', 'UNITS')),
  driver_label      text,
  allow_unallocated boolean NOT NULL DEFAULT false,
  updated_at        timestamptz NOT NULL DEFAULT now(),
  updated_by        uuid REFERENCES users(id),
  UNIQUE (organization_id, id),
  UNIQUE (cost_item_id),
  FOREIGN KEY (organization_id, cost_item_id) REFERENCES cost_items (organization_id, id)
);

CREATE TABLE cost_allocation_targets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  rule_id         uuid NOT NULL,
  product_id      uuid NOT NULL,
  value           numeric(20,6),
  UNIQUE (rule_id, product_id),
  FOREIGN KEY (organization_id, rule_id) REFERENCES cost_allocation_rules (organization_id, id),
  FOREIGN KEY (organization_id, product_id) REFERENCES products (organization_id, id)
);

CREATE TABLE scenarios (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  name            text NOT NULL,
  description     text,
  scenario_type   text NOT NULL DEFAULT 'CUSTOM' CHECK (scenario_type IN ('BASE', 'OPTIMISTIC', 'PESSIMISTIC', 'CUSTOM')),
  base_scenario_id uuid,
  period_start    date NOT NULL,
  period_months   smallint NOT NULL CHECK (period_months BETWEEN 1 AND 12),
  assumptions     jsonb NOT NULL DEFAULT '{}',
  status          text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      uuid REFERENCES users(id),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  row_version     integer NOT NULL DEFAULT 1,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, name),
  FOREIGN KEY (organization_id, base_scenario_id) REFERENCES scenarios (organization_id, id)
);
CREATE TRIGGER trg_scenario_touch BEFORE UPDATE ON scenarios FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE scenario_sales_lines (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id    uuid NOT NULL REFERENCES organizations(id),
  scenario_id        uuid NOT NULL,
  product_id         uuid NOT NULL,
  unit_price         numeric(20,4) NOT NULL CHECK (unit_price >= 0),
  volume             numeric(20,6) NOT NULL CHECK (volume >= 0),
  unit_cost_override numeric(20,4) CHECK (unit_cost_override >= 0),
  UNIQUE (scenario_id, product_id),
  FOREIGN KEY (organization_id, scenario_id) REFERENCES scenarios (organization_id, id),
  FOREIGN KEY (organization_id, product_id) REFERENCES products (organization_id, id)
);

-- Hasil simulasi: append-only, input & hasil lengkap untuk reproduksi.
CREATE TABLE simulation_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  scenario_id     uuid NOT NULL,
  engine_version  text NOT NULL,
  input_snapshot  jsonb NOT NULL,
  result_snapshot jsonb NOT NULL,
  input_hash      char(64) NOT NULL,
  status          text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      uuid REFERENCES users(id),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, scenario_id) REFERENCES scenarios (organization_id, id)
);
CREATE INDEX ix_runs_scenario_created ON simulation_runs (organization_id, scenario_id, created_at DESC);
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (organization_id = app_current_org()) WITH CHECK (organization_id = app_current_org())"
        )

    # role_permissions & roles memakai FORCE RLS sejak 0001 → nonaktifkan sementara untuk seed.
    op.execute("ALTER TABLE roles NO FORCE ROW LEVEL SECURITY")
    for key, desc in NEW_PERMISSIONS.items():
        op.execute(f"INSERT INTO permissions (permission_key, description) VALUES ('{key}', '{desc}')")
    for code, perms in GRANTS.items():
        keys = ", ".join(f"'{p}'" for p in perms)
        op.execute(
            "INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r, permissions p "
            f"WHERE r.code = '{code}' AND r.organization_id IS NULL AND p.permission_key IN ({keys})"
        )
    op.execute("ALTER TABLE roles FORCE ROW LEVEL SECURITY")

    op.execute(f"GRANT SELECT, INSERT, UPDATE ON cost_drivers, cost_items, cost_item_versions, cost_allocation_rules, "
               f"scenarios, scenario_sales_lines TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, DELETE ON cost_allocation_targets TO {APP_ROLE}")
    op.execute(f"GRANT DELETE ON scenario_sales_lines TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON simulation_runs TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS simulation_runs, scenario_sales_lines, scenarios, cost_allocation_targets,
          cost_allocation_rules, cost_item_versions, cost_items, cost_drivers CASCADE;
        DROP FUNCTION IF EXISTS protect_cost_version();
        """
    )
    op.execute("ALTER TABLE roles NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE permission_key IN "
        "('costs.read', 'costs.write', 'planning.read', 'planning.write'))"
    )
    op.execute("DELETE FROM permissions WHERE permission_key IN ('costs.read', 'costs.write', 'planning.read', 'planning.write')")
    op.execute("ALTER TABLE roles FORCE ROW LEVEL SECURITY")
