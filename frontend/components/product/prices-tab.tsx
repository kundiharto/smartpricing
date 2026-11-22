"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, DecimalInput, Dialog, Empty, Field, Input, Select, Spinner, Table, Td, Th } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { date, money, today } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { MaterialPrice, Product } from "@/lib/types";

const NATURES = ["STANDARD", "ACTUAL", "ESTIMATE", "SCENARIO"] as const;

export function PricesTab({ product }: { product: Product }) {
  const { t, lang } = useI18n();
  const { orgId, org, can } = useOrg();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ unit_price: "", effective_from: today(), data_nature: "STANDARD", supplier_name: "", source_reference: "" });

  const q = useQuery({
    queryKey: ["material-prices", orgId, product.id],
    queryFn: () => api.get<MaterialPrice[]>(`/products/${product.id}/material-prices`),
  });
  const add = useMutation({
    mutationFn: () =>
      api.post(`/products/${product.id}/material-prices`, {
        ...form,
        supplier_name: form.supplier_name || null,
        source_reference: form.source_reference || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["material-prices"] });
      setOpen(false);
      setForm({ ...form, unit_price: "", supplier_name: "", source_reference: "" });
    },
  });

  return (
    <Card>
      <CardHeader
        title={t("prod.tab.prices")}
        description={t("mp.hint")}
        action={
          can("products.write") && (
            <Button size="sm" onClick={() => setOpen(true)}>
              <Plus className="size-4" /> {t("mp.add")}
            </Button>
          )
        }
      />
      {q.isLoading ? (
        <Spinner />
      ) : !q.data?.length ? (
        <Empty>{t("common.empty")}</Empty>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>{t("mp.nature")}</Th>
              <Th align="right">{t("mp.price")}</Th>
              <Th>{t("mp.from")}</Th>
              <Th>{t("mp.to")}</Th>
              <Th>{t("mp.supplier")}</Th>
              <Th>{t("mp.source")}</Th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((p) => (
              <tr key={p.id}>
                <Td>
                  <Badge tone={p.effective_to ? "neutral" : "ok"}>{t(`nature.${p.data_nature}`)}</Badge>
                </Td>
                <Td align="right" className="font-medium">{money(p.unit_price, p.currency, lang, true)}</Td>
                <Td>{date(p.effective_from, lang)}</Td>
                <Td className="text-muted">{p.effective_to ? date(p.effective_to, lang) : "—"}</Td>
                <Td className="text-muted">{p.supplier_name ?? "—"}</Td>
                <Td className="text-muted">{p.source_reference ?? "—"}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title={t("mp.add")}>
        <form onSubmit={(e) => { e.preventDefault(); add.mutate(); }} className="space-y-4">
          {add.error && <Alert>{errorText(add.error)}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={`${t("mp.price")} (${org?.default_currency})`} help="mp.price">
              {(id) => <DecimalInput id={id} required value={form.unit_price} onChange={(v) => setForm({ ...form, unit_price: v })} />}
            </Field>
            <Field label={t("mp.from")} help="mp.from">
              {(id) => <Input id={id} type="date" required value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />}
            </Field>
            <Field label={t("mp.nature")} help="mp.nature">
              {(id) => (
                <Select id={id} value={form.data_nature} onChange={(e) => setForm({ ...form, data_nature: e.target.value })}>
                  {NATURES.map((n) => <option key={n} value={n}>{t(`nature.${n}`)}</option>)}
                </Select>
              )}
            </Field>
            <Field label={`${t("mp.supplier")} (${t("common.optional")})`} help="mp.supplier">
              {(id) => <Input id={id} value={form.supplier_name} onChange={(e) => setForm({ ...form, supplier_name: e.target.value })} />}
            </Field>
            <Field label={`${t("mp.source")} (${t("common.optional")})`} help="mp.source" className="sm:col-span-2">
              {(id) => <Input id={id} value={form.source_reference} onChange={(e) => setForm({ ...form, source_reference: e.target.value })} />}
            </Field>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button type="submit" loading={add.isPending}>{t("common.save")}</Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}
