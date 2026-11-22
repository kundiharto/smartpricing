"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Dialog, Empty, Field, Input, PageHeader, Select, Spinner, statusTone, Table, Td, Textarea, Th } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { date } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { byId, useCategories, useUnits } from "@/lib/queries";
import type { Product } from "@/lib/types";

const TYPES = ["FINISHED_GOOD", "MATERIAL", "TRADED_GOOD", "SERVICE"] as const;
const PAGE = 25;

export default function ProductsPage() {
  const { t, lang } = useI18n();
  const { orgId, org, can } = useOrg();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [adding, setAdding] = useState(false);
  const units = useUnits();
  const categories = useCategories();
  const unitMap = byId(units.data);
  const catMap = byId(categories.data);

  useEffect(() => {
    const h = setTimeout(() => {
      setDebounced(q);
      setOffset(0);
    }, 250);
    return () => clearTimeout(h);
  }, [q]);

  const list = useQuery({
    queryKey: ["products", orgId, debounced, type, status, offset],
    queryFn: () => api.page<Product[]>("/products", { query: { q: debounced, product_type: type, status, limit: PAGE, offset, sort: "name" } }),
    placeholderData: keepPreviousData,
  });
  const total = list.data?.meta.total ?? 0;

  return (
    <>
      <PageHeader
        title={t("prod.title")}
        action={
          can("products.write") && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="size-4" /> {t("prod.add")}
            </Button>
          )
        }
      />
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-line p-4">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute top-3 left-3 size-4 text-muted" />
            <Input aria-label={t("common.search")} placeholder={t("prod.searchPh")} value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
          </div>
          <Select aria-label={t("prod.type")} value={type} onChange={(e) => { setType(e.target.value); setOffset(0); }} className="sm:!w-52">
            <option value="">{t("prod.type")}: {t("common.all")}</option>
            {TYPES.map((x) => (
              <option key={x} value={x}>{t(`pt.${x}`)}</option>
            ))}
          </Select>
          <Select aria-label={t("common.status")} value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} className="sm:!w-60">
            <option value="">{t("common.status")}: {t("status.ACTIVE")} + {t("status.INACTIVE")}</option>
            {["ACTIVE", "INACTIVE", "ARCHIVED"].map((x) => (
              <option key={x} value={x}>{t(`status.${x}`)}</option>
            ))}
          </Select>
        </div>
        {list.isLoading ? (
          <Spinner />
        ) : list.error ? (
          <div className="p-4"><Alert>{errorText(list.error)}</Alert></div>
        ) : !list.data?.data.length ? (
          <Empty>{t("common.empty")}</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>{t("prod.sku")}</Th>
                <Th>{t("common.name")}</Th>
                <Th>{t("prod.type")}</Th>
                <Th>{t("prod.category")}</Th>
                <Th>{t("prod.unit")}</Th>
                <Th>{t("common.status")}</Th>
                <Th align="right">{t("common.date")}</Th>
              </tr>
            </thead>
            <tbody>
              {list.data.data.map((p) => (
                <tr key={p.id} className="hover:bg-surface-2">
                  <Td className="font-mono text-xs whitespace-nowrap">{p.sku}</Td>
                  <Td>
                    <Link href={`/products/${p.id}`} className="font-medium text-ink hover:text-accent hover:underline">{p.name}</Link>
                  </Td>
                  <Td><Badge>{t(`pt.${p.product_type}`)}</Badge></Td>
                  <Td className="text-muted">{p.category_id ? catMap[p.category_id]?.name : "—"}</Td>
                  <Td className="text-muted">{unitMap[p.base_unit_id]?.code}</Td>
                  <Td><Badge tone={statusTone(p.status)}>{t(`status.${p.status}`)}</Badge></Td>
                  <Td align="right" className="whitespace-nowrap text-muted">{date(p.updated_at, lang)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
        {total > PAGE && (
          <div className="flex items-center justify-between px-4 py-3 text-sm text-muted">
            <span className="num">{offset + 1}–{Math.min(offset + PAGE, total)} {t("common.of")} {total}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>{t("common.prev")}</Button>
              <Button size="sm" variant="secondary" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>{t("common.next")}</Button>
            </div>
          </div>
        )}
      </Card>
      <ProductDialog open={adding} onClose={() => setAdding(false)} defaultModel={org?.primary_business_model ?? "MANUFACTURING"} businessModels={org?.business_models ?? []} />
    </>
  );
}

function ProductDialog({ open, onClose, defaultModel, businessModels }: { open: boolean; onClose: () => void; defaultModel: string; businessModels: string[] }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const router = useRouter();
  const units = useUnits();
  const categories = useCategories();
  const empty = { sku: "", name: "", product_type: "FINISHED_GOOD", business_model: defaultModel, base_unit_id: "", category_id: "", description: "" };
  const [form, setForm] = useState(empty);

  useEffect(() => {
    if (open) setForm({ ...empty, base_unit_id: units.data?.[0]?.id ?? "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, units.data]);

  const create = useMutation({
    mutationFn: () =>
      api.post<Product>("/products", { ...form, category_id: form.category_id || null, description: form.description || null }),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["products-all"] });
      onClose();
      router.push(`/products/${p.id}`);
    },
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <Dialog open={open} onClose={onClose} title={t("prod.add")}>
      {!units.data?.length ? (
        <Alert tone="warn">
          {t("prod.needUnit")}{" "}
          <Link href="/settings/catalog" className="font-medium underline">{t("nav.catalog")}</Link>
        </Alert>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="space-y-4">
          {create.error && <Alert>{errorText(create.error)}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("prod.sku")}>{(id) => <Input id={id} required value={form.sku} onChange={set("sku")} />}</Field>
            <Field label={t("prod.type")}>
              {(id) => (
                <Select id={id} value={form.product_type} onChange={set("product_type")}>
                  {TYPES.map((x) => <option key={x} value={x}>{t(`pt.${x}`)}</option>)}
                </Select>
              )}
            </Field>
            <Field label={t("common.name")} className="sm:col-span-2">{(id) => <Input id={id} required value={form.name} onChange={set("name")} />}</Field>
            <Field label={t("prod.unit")}>
              {(id) => (
                <Select id={id} value={form.base_unit_id} onChange={set("base_unit_id")} required>
                  {units.data.map((u) => <option key={u.id} value={u.id}>{u.code} — {u.name}</option>)}
                </Select>
              )}
            </Field>
            <Field label={t("prod.model")}>
              {(id) => (
                <Select id={id} value={form.business_model} onChange={set("business_model")}>
                  {(businessModels.length ? businessModels : [defaultModel]).map((m) => <option key={m} value={m}>{t(`bm.${m}`)}</option>)}
                </Select>
              )}
            </Field>
            <Field label={`${t("prod.category")} (${t("common.optional")})`} className="sm:col-span-2">
              {(id) => (
                <Select id={id} value={form.category_id} onChange={set("category_id")}>
                  <option value="">—</option>
                  {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              )}
            </Field>
            <Field label={`${t("prod.description")} (${t("common.optional")})`} className="sm:col-span-2">
              {(id) => <Textarea id={id} value={form.description} onChange={set("description")} />}
            </Field>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
            <Button type="submit" loading={create.isPending}>{t("common.save")}</Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
