"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Alert, Button, Card, CardHeader, Field, Input, Select, Textarea } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { byId, useCategories, useUnits } from "@/lib/queries";
import type { Product } from "@/lib/types";

export function GeneralTab({ product }: { product: Product }) {
  const { t, lang } = useI18n();
  const { can } = useOrg();
  const qc = useQueryClient();
  const units = useUnits();
  const categories = useCategories();
  const editable = can("products.write") && product.status !== "ARCHIVED";
  const [form, setForm] = useState({ name: product.name, category_id: product.category_id ?? "", description: product.description ?? "", status: product.status });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setForm({ name: product.name, category_id: product.category_id ?? "", description: product.description ?? "", status: product.status });
  }, [product]);

  const save = useMutation({
    mutationFn: () =>
      api.patch<Product>(`/products/${product.id}`, {
        row_version: product.row_version,
        name: form.name,
        category_id: form.category_id || null,
        description: form.description || null,
        status: form.status === "ARCHIVED" ? undefined : form.status,
      }),
    onSuccess: () => {
      setSaved(true);
      qc.invalidateQueries({ queryKey: ["product"] });
      qc.invalidateQueries({ queryKey: ["products"] });
    },
  });
  const archive = useMutation({
    mutationFn: () => api.del<Product>(`/products/${product.id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["product"] });
      qc.invalidateQueries({ queryKey: ["products"] });
    },
  });

  return (
    <Card>
      <CardHeader title={t("prod.tab.general")} description={`${t("common.version")} ${product.row_version} · ${dateTime(product.updated_at, lang)}`} />
      <form
        className="space-y-4 p-5"
        onSubmit={(e) => {
          e.preventDefault();
          setSaved(false);
          save.mutate();
        }}
      >
        {save.error && <Alert>{errorText(save.error)}</Alert>}
        {archive.error && <Alert>{errorText(archive.error)}</Alert>}
        {saved && <Alert tone="ok">{t("org.saved")}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("common.name")} help="prod.name" className="sm:col-span-2">
            {(id) => <Input id={id} value={form.name} disabled={!editable} required onChange={(e) => setForm({ ...form, name: e.target.value })} />}
          </Field>
          <Field label={t("prod.sku")} help="prod.sku">{(id) => <Input id={id} value={product.sku} disabled />}</Field>
          <Field label={t("prod.unit")}>{(id) => <Input id={id} value={byId(units.data)[product.base_unit_id]?.code ?? ""} disabled />}</Field>
          <Field label={t("prod.category")} help="prod.category">
            {(id) => (
              <Select id={id} value={form.category_id} disabled={!editable} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
                <option value="">—</option>
                {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            )}
          </Field>
          <Field label={t("common.status")} help="prod.status">
            {(id) => (
              <Select id={id} value={form.status} disabled={!editable} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                {product.status === "ARCHIVED" && <option value="ARCHIVED">{t("status.ARCHIVED")}</option>}
                <option value="ACTIVE">{t("status.ACTIVE")}</option>
                <option value="INACTIVE">{t("status.INACTIVE")}</option>
              </Select>
            )}
          </Field>
          <Field label={t("prod.description")} help="prod.description" className="sm:col-span-2">
            {(id) => <Textarea id={id} value={form.description} disabled={!editable} onChange={(e) => setForm({ ...form, description: e.target.value })} />}
          </Field>
        </div>
        {editable && (
          <div className="flex flex-wrap justify-between gap-2">
            <Button
              type="button"
              variant="danger"
              loading={archive.isPending}
              onClick={() => {
                if (window.confirm(t("prod.archiveConfirm"))) archive.mutate();
              }}
            >
              {t("prod.archive")}
            </Button>
            <Button type="submit" loading={save.isPending}>{t("common.save")}</Button>
          </div>
        )}
      </form>
    </Card>
  );
}
