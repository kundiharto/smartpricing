"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { emptyParams, ParamsForm, paramsFromVersion, paramsPayload, type ParamsState } from "@/components/costs/params-form";
import {
  Alert, Badge, Button, Card, CardHeader, DecimalInput, Dialog, Field, Input, LegendWithHelp, PageHeader, Select, Spinner, statusTone, Table, Td, Th,
} from "@/components/ui";
import { api, engineTrace, errorText } from "@/lib/api";
import { describeCost } from "@/lib/cost-format";
import { date, money, num, pct, percentToFraction, fractionToPercent, today, trimDecimal } from "@/lib/format";
import { useHelp } from "@/lib/help";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { useAllProducts } from "@/lib/queries";
import type { CostItem, CostVersion } from "@/lib/types";

export default function CostDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, lang } = useI18n();
  const { orgId, org, can } = useOrg();
  const qc = useQueryClient();
  const currency = org?.default_currency ?? "IDR";
  const [versionOpen, setVersionOpen] = useState(false);
  const q = useQuery({ queryKey: ["cost", orgId, id], queryFn: () => api.get<CostItem>(`/costs/${id}`) });
  const toggle = useMutation({
    mutationFn: (status: string) =>
      status === "ARCHIVED" ? api.del<CostItem>(`/costs/${id}`) : api.patch<CostItem>(`/costs/${id}`, { row_version: q.data!.row_version, status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cost"] });
      qc.invalidateQueries({ queryKey: ["costs"] });
    },
  });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <Alert>{errorText(q.error)}</Alert>;
  const c = q.data;
  const writable = can("costs.write") && c.status !== "ARCHIVED";

  return (
    <>
      <Link href="/costs" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> {t("costs.title")}
      </Link>
      <PageHeader
        title={c.name}
        description={`${c.code} · ${t(`beh.${c.behavior_type}`)} · ${t(`cat.${c.category}`)} · ${t(`scope.${c.cost_scope}`)}`}
        action={
          <div className="flex items-center gap-2">
            <Badge tone={statusTone(c.status)}>{t(`status.${c.status}`)}</Badge>
            {writable && (
              <>
                <Button size="sm" variant="secondary" loading={toggle.isPending} onClick={() => toggle.mutate(c.status === "ACTIVE" ? "INACTIVE" : "ACTIVE")}>
                  {c.status === "ACTIVE" ? t("status.INACTIVE") : t("status.ACTIVE")}
                </Button>
                <Button size="sm" variant="danger" onClick={() => window.confirm(t("prod.archiveConfirm")) && toggle.mutate("ARCHIVED")}>{t("prod.archive")}</Button>
              </>
            )}
          </div>
        }
      />
      {toggle.error && <div className="mb-4"><Alert>{errorText(toggle.error)}</Alert></div>}

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="min-w-0 lg:col-span-3">
          <CardHeader
            title={t("costs.versions")}
            description={c.driver ? `${t("costs.driver")}: ${c.driver.name} (${t(`drv.${c.driver.driver_type}`)})` : undefined}
            action={writable && <Button size="sm" onClick={() => setVersionOpen(true)}><Plus className="size-4" /> {t("costs.newVersion")}</Button>}
          />
          <Table>
            <thead>
              <tr>
                <Th>{t("common.version")}</Th>
                <Th>{t("mp.nature")}</Th>
                <Th>{t("mp.from")} – {t("mp.to")}</Th>
                <Th>{t("costs.params")}</Th>
              </tr>
            </thead>
            <tbody>
              {c.versions?.map((v) => (
                <tr key={v.id}>
                  <Td>v{v.version_number}</Td>
                  <Td><Badge tone={v.effective_to ? "neutral" : "ok"}>{t(`nature.${v.data_nature}`)}</Badge></Td>
                  <Td className="whitespace-nowrap text-muted">{date(v.effective_from, lang)} – {v.effective_to ? date(v.effective_to, lang) : "…"}</Td>
                  <Td className="num text-sm">
                    {describeCost({ ...c, current_version: v }, t, lang, currency)}
                    {v.escalation_type && <span className="block text-xs text-muted">{t("costs.escalation")}: {escText(v, t, lang, currency)}</span>}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <p className="px-5 py-3 text-xs text-muted">{t("costs.newVersionHint")}</p>
        </Card>
        <Card className="min-w-0 lg:col-span-2">
          <CardHeader title={t("costs.params")} />
          <dl className="divide-y divide-line text-sm">
            {[
              [t("costs.behavior"), t(`beh.${c.behavior_type}`)],
              [t("costs.scope"), t(`scope.${c.cost_scope}`)],
              [t("costs.period"), t(`period.${c.period_months}`)],
              [t("costs.driver"), c.driver ? `${c.driver.name} · ${t(`drv.${c.driver.driver_type}`)}` : "—"],
              [t("prod.description"), c.description || "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 px-5 py-2.5"><dt className="text-muted">{k}</dt><dd className="text-right font-medium">{v}</dd></div>
            ))}
          </dl>
        </Card>
      </div>

      {c.cost_scope === "ALLOCATION_POOL" && <AllocationEditor item={c} writable={writable} />}

      <NewVersionDialog open={versionOpen} onClose={() => setVersionOpen(false)} item={c} currency={currency} />
    </>
  );
}

function escText(v: CostVersion, t: (k: string) => string, lang: "id" | "en", currency: string) {
  const inc = v.escalation_type === "NOMINAL" ? money(v.escalation_amount, currency, lang) : pct(v.escalation_rate, lang);
  return `+${inc} / ${t(`freq.${v.escalation_frequency ?? "ANNUAL"}`)}${v.escalation_cap ? ` (max ${money(v.escalation_cap, currency, lang)})` : ""}`;
}

function NewVersionDialog({ open, onClose, item, currency }: { open: boolean; onClose: () => void; item: CostItem; currency: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [params, setParams] = useState<ParamsState>(emptyParams());
  useEffect(() => {
    if (open) setParams(item.current_version ? { ...paramsFromVersion(item.current_version), effective_from: today() } : emptyParams());
  }, [open, item.current_version]);
  const save = useMutation({
    mutationFn: () => api.post<CostItem>(`/costs/${item.id}/versions`, paramsPayload(item.behavior_type, params)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cost"] });
      qc.invalidateQueries({ queryKey: ["costs"] });
      onClose();
    },
  });
  const trace = engineTrace(save.error);
  return (
    <Dialog open={open} onClose={onClose} title={`${t("costs.newVersion")} · ${item.name}`} wide>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <Alert tone="info">{t("costs.newVersionHint")}</Alert>
        {save.error && <Alert title={errorText(save.error)}>{trace.length > 0 && <span className="text-xs">{trace.at(-1)}</span>}</Alert>}
        <ParamsForm behavior={item.behavior_type} value={params} onChange={setParams} currency={currency} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" loading={save.isPending}>{t("common.save")}</Button>
        </div>
      </form>
    </Dialog>
  );
}

function AllocationEditor({ item, writable }: { item: CostItem; writable: boolean }) {
  const { t, lang } = useI18n();
  const { allocation: allocHelp } = useHelp();
  const qc = useQueryClient();
  const products = useAllProducts();
  const sellable = (products.data ?? []).filter((p) => p.product_type !== "MATERIAL");
  const [basis, setBasis] = useState(item.allocation?.basis ?? "REVENUE");
  const [label, setLabel] = useState(item.allocation?.driver_label ?? "");
  const [rows, setRows] = useState<{ product_id: string; value: string }[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setBasis(item.allocation?.basis ?? "REVENUE");
    setLabel(item.allocation?.driver_label ?? "");
    setRows(
      (item.allocation?.targets ?? []).map((x) => ({
        product_id: x.product_id,
        value: x.value === null ? "" : item.allocation?.basis === "PERCENTAGE" ? fractionToPercent(x.value) : trimDecimal(x.value),
      })),
    );
  }, [item.allocation]);

  const needsValue = basis === "PERCENTAGE" || basis === "DRIVER";
  const save = useMutation({
    mutationFn: () =>
      api.put(`/costs/${item.id}/allocation`, {
        basis,
        driver_label: basis === "DRIVER" ? label || null : null,
        targets: rows.filter((r) => r.product_id).map((r) => ({
          product_id: r.product_id,
          value: needsValue ? (basis === "PERCENTAGE" ? percentToFraction(r.value || "0") : r.value || "0") : null,
        })),
      }),
    onSuccess: () => {
      setSaved(true);
      qc.invalidateQueries({ queryKey: ["cost"] });
      qc.invalidateQueries({ queryKey: ["costs"] });
    },
  });

  return (
    <Card className="mt-6">
      <CardHeader title={t("costs.allocation")} description={t("costs.allocationHint")} />
      <form className="space-y-4 p-5" onSubmit={(e) => { e.preventDefault(); setSaved(false); save.mutate(); }}>
        {save.error && <Alert>{errorText(save.error)}</Alert>}
        {saved && <Alert tone="ok">{t("org.saved")}</Alert>}
        {!item.allocation && <Alert tone="warn">{t("plan.companyCosts")}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Field label={t("costs.basis")} help="cost.allocBasis">
              {(id) => (
                <Select id={id} value={basis} disabled={!writable} onChange={(e) => setBasis(e.target.value)}>
                  {["REVENUE", "UNITS", "EQUAL", "PERCENTAGE", "DRIVER"].map((b) => <option key={b} value={b}>{t(`alloc.${b}`)}</option>)}
                </Select>
              )}
            </Field>
            <p className="text-xs text-muted">{allocHelp(basis)}</p>
          </div>
          {basis === "DRIVER" && (
            <Field label={`${t("costs.driver")} (${t("common.optional")})`}>
              {(id) => <Input id={id} value={label} disabled={!writable} placeholder={t("drv.MACHINE_HOURS")} onChange={(e) => setLabel(e.target.value)} />}
            </Field>
          )}
        </div>
        <fieldset className="space-y-2">
          <legend className="mb-1"><LegendWithHelp label={t("costs.targets")} help="cost.allocBasis" /></legend>
          {!needsValue && <p className="text-xs text-muted">{t("costs.allProducts")}</p>}
          {rows.map((r, i) => (
            <div key={i} className="grid grid-cols-[1fr_9rem_2.5rem] gap-2">
              <Select aria-label={t("nav.products")} value={r.product_id} disabled={!writable} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, product_id: e.target.value } : x)))}>
                <option value="">—</option>
                {sellable.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
              </Select>
              {needsValue ? (
                <DecimalInput aria-label={t("costs.value")} suffix={basis === "PERCENTAGE" ? "%" : undefined} value={r.value} disabled={!writable}
                  onChange={(v) => setRows(rows.map((x, j) => (j === i ? { ...x, value: v } : x)))} />
              ) : <span />}
              <Button type="button" variant="ghost" size="sm" disabled={!writable} onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label={t("common.remove")}><Trash2 className="size-4" /></Button>
            </div>
          ))}
          {writable && (
            <Button type="button" size="sm" variant="secondary" onClick={() => setRows([...rows, { product_id: "", value: "" }])}>
              <Plus className="size-4" /> {t("plan.addLine")}
            </Button>
          )}
          {basis === "PERCENTAGE" && rows.length > 0 && (
            <p className="num text-xs text-muted">Σ = {num(String(rows.reduce((a, r) => a + Number(r.value || 0), 0)), lang)}%</p>
          )}
        </fieldset>
        {writable && <div className="flex justify-end"><Button type="submit" loading={save.isPending}>{t("costs.saveAllocation")}</Button></div>}
      </form>
    </Card>
  );
}
