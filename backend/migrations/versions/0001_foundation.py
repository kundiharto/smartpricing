"""Foundation: users, organizations, RBAC, audit, products, BOM, costing, pricing.

Mengikuti docs/DATABASE_SPEC.md:
- composite foreign key (organization_id, id) untuk mencegah referensi lintas tenant
- Row-Level Security (FORCE) pada seluruh tabel tenant
- tabel effective-dated dengan exclusion constraint
- snapshot costing immutable

Revision ID: 0001
Revises:
Create Date: 2026-11-22
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "spe_app"

# Tabel tenant yang memakai policy standar organization_id = app_current_org()
STANDARD_TENANT_TABLES = [
    "organization_business_models",
    "audit_logs",
    "product_categories",
    "units_of_measure",
    "products",
    "material_prices",
    "bill_of_materials",
    "bom_items",
    "costing_versions",
    "pricing_recommendations",
]

PERMISSIONS = {
    "org.read": "Melihat profil organisasi",
    "org.manage": "Mengubah profil dan konfigurasi organisasi",
    "members.manage": "Mengelola anggota dan role",
    "products.read": "Melihat produk, satuan, kategori",
    "products.write": "Membuat dan mengubah produk, BOM, harga material",
    "costing.read": "Melihat hasil costing",
    "costing.write": "Menjalankan dan menyimpan costing",
    "pricing.read": "Melihat rekomendasi harga",
    "pricing.calculate": "Menjalankan kalkulator harga",
    "pricing.recommend": "Menyimpan rekomendasi harga",
    "pricing.approve": "Menyetujui rekomendasi harga",
    "audit.read": "Melihat audit log",
}

ROLES = {
    "OWNER": ("Organization Owner", list(PERMISSIONS)),
    "DIRECTOR": (
        "Director",
        ["org.read", "products.read", "costing.read", "pricing.read", "pricing.calculate", "pricing.approve", "audit.read"],
    ),
    "FINANCE_MANAGER": (
        "Finance Manager",
        ["org.read", "products.read", "products.write", "costing.read", "costing.write",
         "pricing.read", "pricing.calculate", "pricing.recommend"],
    ),
    "FINANCIAL_ANALYST": (
        "Financial Analyst",
        ["org.read", "products.read", "products.write", "costing.read", "costing.write", "pricing.read", "pricing.calculate"],
    ),
    "OPERATIONS_MANAGER": (
        "Operations Manager",
        ["org.read", "products.read", "products.write", "costing.read", "costing.write"],
    ),
    "SALES_MANAGER": ("Sales Manager", ["org.read", "products.read", "pricing.read", "pricing.calculate"]),
    "VIEWER": ("Viewer", ["org.read", "products.read", "costing.read", "pricing.read"]),
}

SCHEMA = r"""
-- ---------------------------------------------------------------------------
-- Konteks sesi (diatur backend per transaksi dengan set_config(..., true))
-- ---------------------------------------------------------------------------
CREATE FUNCTION app_current_org() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.current_org_id', true), '')::uuid $$;

CREATE FUNCTION app_current_user() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.current_user_id', true), '')::uuid $$;

CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- ---------------------------------------------------------------------------
-- Users (global)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email              citext NOT NULL UNIQUE,
  password_hash      text NOT NULL,
  full_name          text NOT NULL,
  preferred_language text NOT NULL DEFAULT 'id' CHECK (preferred_language IN ('id', 'en')),
  status             text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DISABLED')),
  is_platform_admin  boolean NOT NULL DEFAULT false,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN users.email IS 'PII';
COMMENT ON COLUMN users.full_name IS 'PII';

-- ---------------------------------------------------------------------------
-- Organizations & membership
-- ---------------------------------------------------------------------------
CREATE TABLE organizations (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                    text NOT NULL,
  slug                    citext NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$'),
  default_currency        char(3) NOT NULL DEFAULT 'IDR',
  default_language        text NOT NULL DEFAULT 'id' CHECK (default_language IN ('id', 'en')),
  fiscal_year_start_month smallint NOT NULL DEFAULT 1 CHECK (fiscal_year_start_month BETWEEN 1 AND 12),
  timezone                text NOT NULL DEFAULT 'Asia/Jakarta',
  status                  text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED')),
  created_at              timestamptz NOT NULL DEFAULT now(),
  created_by              uuid REFERENCES users(id),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  row_version             integer NOT NULL DEFAULT 1
);

CREATE TABLE organization_business_models (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  business_model  text NOT NULL CHECK (business_model IN ('MANUFACTURING', 'TRADING', 'DISTRIBUTION', 'RETAIL', 'SERVICES')),
  is_primary      boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, business_model)
);
CREATE UNIQUE INDEX uq_org_primary_business_model ON organization_business_models (organization_id) WHERE is_primary;

CREATE TABLE organization_members (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  user_id         uuid NOT NULL REFERENCES users(id),
  status          text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED')),
  joined_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, user_id),
  UNIQUE (organization_id, id)
);
CREATE INDEX ix_members_user ON organization_members (user_id);

-- ---------------------------------------------------------------------------
-- RBAC
-- ---------------------------------------------------------------------------
CREATE TABLE permissions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  permission_key text NOT NULL UNIQUE,
  description    text NOT NULL
);

CREATE TABLE roles (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid REFERENCES organizations(id),  -- NULL = role sistem
  code            text NOT NULL,
  name            text NOT NULL,
  description     text,
  is_system       boolean NOT NULL DEFAULT false,
  CHECK (is_system = (organization_id IS NULL)),
  UNIQUE NULLS NOT DISTINCT (organization_id, code)
);

CREATE TABLE role_permissions (
  role_id       uuid NOT NULL REFERENCES roles(id),
  permission_id uuid NOT NULL REFERENCES permissions(id),
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE member_roles (
  organization_id uuid NOT NULL,
  member_id       uuid NOT NULL,
  role_id         uuid NOT NULL REFERENCES roles(id),
  PRIMARY KEY (member_id, role_id),
  FOREIGN KEY (organization_id, member_id) REFERENCES organization_members (organization_id, id)
);

CREATE FUNCTION check_member_role_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE role_org uuid;
BEGIN
  SELECT organization_id INTO role_org FROM roles WHERE id = NEW.role_id;
  IF role_org IS NOT NULL AND role_org <> NEW.organization_id THEN
    RAISE EXCEPTION 'role % milik organisasi lain', NEW.role_id USING ERRCODE = 'foreign_key_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_member_role_scope BEFORE INSERT OR UPDATE ON member_roles
  FOR EACH ROW EXECUTE FUNCTION check_member_role_scope();

-- ---------------------------------------------------------------------------
-- Audit (append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE audit_logs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  user_id         uuid REFERENCES users(id),
  action          text NOT NULL,
  entity_type     text NOT NULL,
  entity_id       uuid,
  old_values      jsonb,
  new_values      jsonb,
  request_id      text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_org_created ON audit_logs (organization_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Products
-- ---------------------------------------------------------------------------
CREATE TABLE product_categories (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  name            text NOT NULL,
  parent_id       uuid,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, name),
  FOREIGN KEY (organization_id, parent_id) REFERENCES product_categories (organization_id, id)
);

CREATE TABLE units_of_measure (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  code            text NOT NULL,
  name            text NOT NULL,
  dimension       text NOT NULL CHECK (dimension IN ('COUNT', 'MASS', 'VOLUME', 'LENGTH', 'AREA', 'TIME', 'OTHER')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code)
);

CREATE TABLE products (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id    uuid NOT NULL REFERENCES organizations(id),
  category_id        uuid,
  sku                text NOT NULL,
  name               text NOT NULL,
  product_type       text NOT NULL CHECK (product_type IN ('FINISHED_GOOD', 'MATERIAL', 'TRADED_GOOD', 'SERVICE')),
  business_model     text NOT NULL CHECK (business_model IN ('MANUFACTURING', 'TRADING', 'DISTRIBUTION', 'RETAIL', 'SERVICES')),
  pricing_model_type text NOT NULL DEFAULT 'STANDARD' CHECK (pricing_model_type IN ('STANDARD', 'PROJECT_BASED')),
  base_unit_id       uuid NOT NULL,
  description        text,
  status             text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')),
  created_at         timestamptz NOT NULL DEFAULT now(),
  created_by         uuid REFERENCES users(id),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  row_version        integer NOT NULL DEFAULT 1,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, sku),
  FOREIGN KEY (organization_id, category_id) REFERENCES product_categories (organization_id, id),
  FOREIGN KEY (organization_id, base_unit_id) REFERENCES units_of_measure (organization_id, id)
);
CREATE INDEX ix_products_org_status ON products (organization_id, status);

-- ---------------------------------------------------------------------------
-- Material prices (effective-dated)
-- ---------------------------------------------------------------------------
CREATE TABLE material_prices (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id     uuid NOT NULL REFERENCES organizations(id),
  material_product_id uuid NOT NULL,
  supplier_name       text,
  currency            char(3) NOT NULL DEFAULT 'IDR',
  unit_price          numeric(20,4) NOT NULL CHECK (unit_price >= 0),
  effective_from      date NOT NULL,
  effective_to        date,
  data_nature         text NOT NULL DEFAULT 'STANDARD' CHECK (data_nature IN ('ACTUAL', 'STANDARD', 'ESTIMATE', 'SCENARIO')),
  source_reference    text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  created_by          uuid REFERENCES users(id),
  UNIQUE (organization_id, id),
  CHECK (effective_to IS NULL OR effective_to > effective_from),
  FOREIGN KEY (organization_id, material_product_id) REFERENCES products (organization_id, id),
  EXCLUDE USING gist (
    organization_id WITH =, material_product_id WITH =, data_nature WITH =,
    daterange(effective_from, effective_to, '[)') WITH &&
  )
);
CREATE INDEX ix_material_prices_lookup ON material_prices (organization_id, material_product_id, effective_from DESC);

-- ---------------------------------------------------------------------------
-- BOM
-- ---------------------------------------------------------------------------
CREATE TABLE bill_of_materials (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id    uuid NOT NULL REFERENCES organizations(id),
  product_id         uuid NOT NULL,
  version_number     integer NOT NULL CHECK (version_number > 0),
  planned_output_qty numeric(20,6) NOT NULL CHECK (planned_output_qty > 0),
  process_yield_rate numeric(12,6) NOT NULL DEFAULT 1 CHECK (process_yield_rate > 0 AND process_yield_rate <= 1),
  status             text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED')),
  effective_from     date NOT NULL,
  effective_to       date,
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  created_by         uuid REFERENCES users(id),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, product_id, version_number),
  FOREIGN KEY (organization_id, product_id) REFERENCES products (organization_id, id)
);
CREATE UNIQUE INDEX uq_bom_one_active ON bill_of_materials (organization_id, product_id) WHERE status = 'ACTIVE';

CREATE TABLE bom_items (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id     uuid NOT NULL REFERENCES organizations(id),
  bom_id              uuid NOT NULL,
  line_no             integer NOT NULL CHECK (line_no > 0),
  material_product_id uuid NOT NULL,
  net_quantity        numeric(20,6) NOT NULL CHECK (net_quantity >= 0),
  material_waste_rate numeric(12,6) NOT NULL DEFAULT 0 CHECK (material_waste_rate >= 0 AND material_waste_rate < 1),
  UNIQUE (organization_id, id),
  UNIQUE (bom_id, material_product_id),
  UNIQUE (bom_id, line_no),
  FOREIGN KEY (organization_id, bom_id) REFERENCES bill_of_materials (organization_id, id),
  FOREIGN KEY (organization_id, material_product_id) REFERENCES products (organization_id, id)
);

-- ---------------------------------------------------------------------------
-- Costing versions (immutable setelah ACTIVE)
-- ---------------------------------------------------------------------------
CREATE TABLE costing_versions (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id      uuid NOT NULL REFERENCES organizations(id),
  product_id           uuid NOT NULL,
  version_number       integer NOT NULL CHECK (version_number > 0),
  costing_method       text NOT NULL CHECK (costing_method IN ('STANDARD', 'ACTUAL', 'ESTIMATED')),
  costing_structure    text NOT NULL CHECK (costing_structure IN ('BOM_BASED', 'PROCESS_BASED', 'LANDED_COST', 'SERVICE', 'DIRECT_INPUT')),
  data_nature          text NOT NULL CHECK (data_nature IN ('ACTUAL', 'STANDARD', 'ESTIMATE', 'SCENARIO')),
  bom_id               uuid,
  scrap_rate           numeric(12,6) NOT NULL DEFAULT 0,
  rework_rate          numeric(12,6) NOT NULL DEFAULT 0,
  rework_cost_per_unit numeric(20,4) NOT NULL DEFAULT 0,
  calculated_unit_cost numeric(20,4) NOT NULL CHECK (calculated_unit_cost >= 0),
  currency             char(3) NOT NULL,
  as_of_date           date NOT NULL,
  effective_from       date NOT NULL,
  effective_to         date,
  status               text NOT NULL CHECK (status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED')),
  engine_version       text NOT NULL,
  input_snapshot       jsonb NOT NULL,
  calculation_snapshot jsonb NOT NULL,
  input_hash           char(64) NOT NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  created_by           uuid REFERENCES users(id),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, product_id, version_number),
  FOREIGN KEY (organization_id, product_id) REFERENCES products (organization_id, id),
  FOREIGN KEY (organization_id, bom_id) REFERENCES bill_of_materials (organization_id, id)
);
CREATE UNIQUE INDEX uq_costing_one_active ON costing_versions (organization_id, product_id) WHERE status = 'ACTIVE';

CREATE FUNCTION protect_immutable_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('ACTIVE', 'SUPERSEDED')
     AND (to_jsonb(NEW) - 'status' - 'effective_to') IS DISTINCT FROM (to_jsonb(OLD) - 'status' - 'effective_to') THEN
    RAISE EXCEPTION 'snapshot % bersifat immutable; hanya status dan effective_to yang boleh berubah', OLD.id
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF OLD.status = 'SUPERSEDED' AND NEW.status <> 'SUPERSEDED' THEN
    RAISE EXCEPTION 'versi SUPERSEDED tidak dapat diaktifkan kembali' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_costing_immutable BEFORE UPDATE ON costing_versions
  FOR EACH ROW EXECUTE FUNCTION protect_immutable_snapshot();

-- ---------------------------------------------------------------------------
-- Pricing recommendations
-- ---------------------------------------------------------------------------
CREATE TABLE pricing_recommendations (
  id                           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id              uuid NOT NULL REFERENCES organizations(id),
  product_id                   uuid NOT NULL,
  costing_version_id           uuid NOT NULL,
  pricing_method               text NOT NULL,
  margin_definition            text NOT NULL CHECK (margin_definition IN ('GROSS', 'CONTRIBUTION')),
  minimum_price                numeric(20,4),
  target_price                 numeric(20,4) NOT NULL,
  recommended_price            numeric(20,4) NOT NULL,
  list_price                   numeric(20,4) NOT NULL,
  expected_gross_margin        numeric(12,6),
  expected_contribution_margin numeric(12,6),
  currency                     char(3) NOT NULL,
  effective_date               date NOT NULL,
  warnings                     jsonb NOT NULL DEFAULT '[]',
  engine_version               text NOT NULL,
  input_snapshot               jsonb NOT NULL,
  calculation_snapshot         jsonb NOT NULL,
  input_hash                   char(64) NOT NULL,
  status                       text NOT NULL DEFAULT 'DRAFT'
                               CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'PUBLISHED')),
  created_at                   timestamptz NOT NULL DEFAULT now(),
  created_by                   uuid REFERENCES users(id),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, product_id) REFERENCES products (organization_id, id),
  FOREIGN KEY (organization_id, costing_version_id) REFERENCES costing_versions (organization_id, id)
);
CREATE INDEX ix_recommendations_org_created ON pricing_recommendations (organization_id, created_at DESC);

CREATE TRIGGER trg_org_touch BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_product_touch BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_user_touch BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ---------------------------------------------------------------------------
-- Login lookup: satu-satunya jalan membaca user sebelum identitas diketahui.
-- ---------------------------------------------------------------------------
CREATE FUNCTION auth_lookup_user(p_email text)
RETURNS TABLE (id uuid, password_hash text, status text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT u.id, u.password_hash, u.status FROM users u WHERE u.email = p_email::citext
$$;
CREATE FUNCTION auth_email_exists(p_email text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM users WHERE email = p_email::citext)
$$;
CREATE FUNCTION auth_find_user_id(p_email text) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT id FROM users WHERE email = p_email::citext AND status = 'ACTIVE'
$$;
"""

RLS = r"""
-- users: hanya diri sendiri dan anggota organisasi aktif. (Tidak FORCE: fungsi
-- SECURITY DEFINER auth_* milik owner perlu membaca saat login.)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_visible ON users
  USING (id = app_current_user()
         OR id IN (SELECT m.user_id FROM organization_members m WHERE m.organization_id = app_current_org()))
  WITH CHECK (id = app_current_user());

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY org_visible ON organizations
  USING (id = app_current_org()
         OR id IN (SELECT m.organization_id FROM organization_members m
                   WHERE m.user_id = app_current_user() AND m.status = 'ACTIVE'))
  WITH CHECK (id = app_current_org());

ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members FORCE ROW LEVEL SECURITY;
CREATE POLICY members_visible ON organization_members
  USING (organization_id = app_current_org() OR user_id = app_current_user())
  WITH CHECK (organization_id = app_current_org());

-- member_roles: role milik organisasi aktif, atau role keanggotaan pengguna sendiri (untuk /auth/me).
ALTER TABLE member_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE member_roles FORCE ROW LEVEL SECURITY;
CREATE POLICY member_roles_visible ON member_roles
  USING (organization_id = app_current_org()
         OR member_id IN (SELECT m.id FROM organization_members m WHERE m.user_id = app_current_user()))
  WITH CHECK (organization_id = app_current_org());

ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles FORCE ROW LEVEL SECURITY;
CREATE POLICY roles_visible ON roles
  USING (organization_id IS NULL OR organization_id = app_current_org())
  WITH CHECK (organization_id = app_current_org());
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute(SCHEMA)

    # Seed RBAC (sebelum RLS aktif: FORCE RLS juga berlaku untuk pemilik tabel)
    for key, desc in PERMISSIONS.items():
        op.execute(f"INSERT INTO permissions (permission_key, description) VALUES ('{key}', '{desc}')")
    for code, (name, perms) in ROLES.items():
        op.execute(f"INSERT INTO roles (code, name, is_system) VALUES ('{code}', '{name}', true)")
        keys = ", ".join(f"'{p}'" for p in perms)
        op.execute(
            "INSERT INTO role_permissions (role_id, permission_id) "
            f"SELECT r.id, p.id FROM roles r, permissions p "
            f"WHERE r.code = '{code}' AND r.organization_id IS NULL AND p.permission_key IN ({keys})"
        )

    op.execute(RLS)
    for table in STANDARD_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (organization_id = app_current_org()) "
            "WITH CHECK (organization_id = app_current_org())"
        )

    # Hak role aplikasi: tanpa DELETE (data diarsipkan), audit & snapshot append-only.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT ON permissions, role_permissions TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON roles TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON users, organizations, organization_business_models, "
               f"organization_members, product_categories, units_of_measure, products, bill_of_materials, "
               f"bom_items, costing_versions, pricing_recommendations TO {APP_ROLE}")
    op.execute(f"GRANT DELETE ON organization_business_models, member_roles, bom_items TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON material_prices TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON member_roles, audit_logs TO {APP_ROLE}")
    for fn in ("auth_lookup_user(text)", "auth_email_exists(text)", "auth_find_user_id(text)"):
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS pricing_recommendations, costing_versions, bom_items, bill_of_materials,
          material_prices, products, units_of_measure, product_categories, audit_logs, member_roles,
          role_permissions, roles, permissions, organization_members, organization_business_models,
          organizations, users CASCADE;
        DROP FUNCTION IF EXISTS auth_lookup_user(text), auth_email_exists(text), auth_find_user_id(text),
          protect_immutable_snapshot(), check_member_role_scope(), touch_updated_at(),
          app_current_org(), app_current_user();
        """
    )
