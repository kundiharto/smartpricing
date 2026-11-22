"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Copy, Play, Plus, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useMemo, useState } from "react";
import { PlanResults } from "@/components/planning/results";
import {
  Alert, Badge, Button, Card, CardHeader, DecimalInput, Dialog, Field, HelpPanel, Input, LegendWithHelp, PageHeader, Select, Spinner, Trace,
} from "@/components/ui";
import { api, engineTrace, errorText } from "@/lib/api";
import { date, fractionToPercent, money, percentToFraction, trimDecimal } from "@/lib/format";
import { useHelp } from "@/lib/help";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { useAllProducts, useDrivers } from "@/lib/queries";
import type { CostItem, Recommendation, Run, RunSummary, Scenario } from "@/lib/types";

type Line = { product_id: string; unit_price: string; volume: string; unit_cost_override: string };
type Form = {
  name: string; description: string; scenario_type: string; period_start: string; period_months: string;
  price: string; volume: string; unit_cost: string; variable: string; fixed: string;
  item_changes: { code: string; pct: string }[];
  other_activity: { code: string; qty: string }[];
  tax_regime: string; tax_rate: string; exempt: string;
  target_kind: string; target_amount: string; data_nature: string;
};

const pctStr = (v: string | null | undefined) => (v ? fractionToPercent(v) : "0");

function toForm(s: Scenario): Form {
  const a = s.assumptions;
  return {
    name: s.name, description: s.description ?? "", scenario_type: s.scenario_type, period_start: s.period_start, period_months: String(s.period_months),
    price: pctStr(a.price_change), volume: pctStr(a.volume_change), unit_cost: pctStr(a.unit_cost_change),
    variable: pctStr(a.variable_cost_change), fixed: pctStr(a.fixed_cost_change),
    item_changes: Object.entries(a.item_changes ?? {}).map(([code, v]) => ({ code, pct: fractionToPercent(v) })),
    other_activity: Object.entries(a.other_activity ?? {}).map(([code, v]) => ({ code, qty: trimDecimal(v) })),
    tax_regime: a.tax_regime ?? "NONE", tax_rate: pctStr(a.tax_rate), exempt: trimDecimal(a.exempt_turnover ?? "0"),
    target_kind: a.target_kind ?? "", target_amount: a.target_amount ? trimDecimal(a.target_amount) : "", data_nature: a.data_nature ?? "STANDARD",
  };
}

function toPayload(f: Form, lines: Line[], rowVersion: number) {
  const frac = (x: string) => percentToFraction(x || "0");
  return {
    row_version: rowVersion,
    name: f.name, description: f.description || null, scenario_type: f.scenario_type, period_start: f.period_start, period_months: Number(f.period_months),
    assumptions: {
      price_change: frac(f.price), volume_change: frac(f.volume), unit_cost_change: frac(f.unit_cost),
      variable_cost_change: frac(f.variable), fixed_cost_change: frac(f.fixed),
      item_changes: Object.fromEntries(f.item_changes.filter((x) => x.code && x.pct).map((x) => [x.code, frac(x.pct)])),
      other_activity: Object.fromEntries(f.other_activity.filter((x) => x.code && x.qty).map((x) => [x.code, x.qty])),
      tax_regime: f.tax_regime, tax_rate: frac(f.tax_rate), exempt_turnover: f.exempt || "0",
      target_kind: f.target_kind || null, target_amount: f.target_kind && f.target_amount ? f.target_amount : null, data_nature: f.data_nature,
    },
    lines: lines.filter((l) => l.product_id).map((l) => ({
      product_id: l.product_id, unit_price: l.unit_price || "0", volume: l.volume || "0", unit_cost_override: l.unit_cost_override || null,
    })),
  };
}

export default function ScenarioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, lang } = useI18n();
  const { orgId, org, can } = useOrg();
  const { help, exampleLabel } = useHelp();
  const qc = useQueryClient();
  const router = useRouter();
  const currency = org?.default_currency ?? "IDR";
  const writable = can("planning.write");

  const q = useQuery({ queryKey: ["scenario", orgId, id], queryFn: () => api.get<Scenario>(`/scenarios/${id}`) });
  const products = useAllProducts();
  const sellable = useMemo(() => (products.data ?? []).filter((p) => p.product_type !== "MATERIAL"), [products.data]);
  const recs = useQuery({ queryKey: ["recommendations", orgId, "plan"], queryFn: () => api.get<Recommendation[]>("/pricing/recommendations", { query: { limit: 200 } }) });
  const costs = useQuery({ queryKey: ["costs", orgId], queryFn: () => api.get<CostItem[]>("/costs"), enabled: can("costs.read") });
  const drivers = useDrivers();
  const manualDrivers = (drivers.data ?? []).filter((d) => !["SALES_UNITS", "PRODUCTION_UNITS", "REVENUE"].includes(d.driver_type));

  const [form, setForm] = useState<Form | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [dupOpen, setDupOpen] = useState(false);
  const [dupName, setDupName] = useState("");

  useEffect(() => {
    if (!q.data) return;
    setForm(toForm(q.data));
    setLines(q.data.lines.map((l) => ({ product_id: l.product_id, unit_price: trimDecimal(l.unit_price), volume: trimDecimal(l.volume), unit_cost_override: l.unit_cost_override ? trimDecimal(l.unit_cost_override) : "" })));
  }, [q.data]);

  const latestId = q.data?.latest_run?.id;
  const latest = useQuery({
    queryKey: ["run", orgId, latestId],
    queryFn: () => api.get<Run>(`/simulation-runs/${latestId}`),
    enabled: Boolean(latestId) && !run,
  });
  const history = useQuery({ queryKey: ["runs", orgId, id, latestId], queryFn: () => api.get<RunSummary[]>(`/scenarios/${id}/runs`) });
  const shown = run ?? latest.data ?? null;

  const save = useMutation({
    mutationFn: () => api.patch<Scenario>(`/scenarios/${id}`, toPayload(form!, lines, q.data!.row_version)),
    onSuccess: (s) => qc.setQueryData(["scenario", orgId, id], s),
  });
  const runMut = useMutation({
    mutationFn: async () => {
      const s = await api.patch<Scenario>(`/scenarios/${id}`, toPayload(form!, lines, q.data!.row_version));
      qc.setQueryData(["scenario", orgId, id], s);
      return api.post<Run>(`/scenarios/${id}/run`);
    },
    onSuccess: (r) => {
      setRun(r);
      qc.invalidateQueries({ queryKey: ["scenario", orgId, id] });
      qc.invalidateQueries({ queryKey: ["scenarios"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
  const dup = useMutation({
    mutationFn: () => api.post<Scenario>(`/scenarios/${id}/duplicate`, { name: dupName, scenario_type: "CUSTOM" }),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["scenarios"] });
      setDupOpen(false);
      router.push(`/planning/${s.id}`);
    },
  });
  const archive = useMutation({
    mutationFn: () => api.del(`/scenarios/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scenarios"] });
      router.push("/planning");
    },
  });

  if (q.isLoading || !form) return <Spinner />;
  if (q.error || !q.data) return <Alert>{errorText(q.error)}</Alert>;
  const s = q.data;

  const latestPrice = (productId: string) => recs.data?.find((r) => r.product_id === productId)?.recommended_price;
  const lineInfo = (productId: string) => s.lines.find((l) => l.product_id === productId);
  const set = (patch: Partial<Form>) => setForm({ ...form, ...patch });
  const pctField = (key: "price" | "volume" | "unit_cost" | "variable" | "fixed", label: string) => (
    <Field label={label} help="plan.change">{(fid) => <DecimalInput id={fid} suffix="%" value={form[key]} disabled={!writable} onChange={(v) => set({ [key]: v } as Partial<Form>)} />}</Field>
  );
  const linesHelp = help("plan.lines");
  const err = runMut.error ?? save.error;
  const trace = engineTrace(err);

  return (
    <>
      <Link href="/planning" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> {t("plan.title")}
      </Link>
      <PageHeader
        title={s.name}
        description={`${date(s.period_start, lang)} · ${s.period_months} ${t("plan.monthsShort")}`}
        action={
          writable && (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => { setDupName(`${s.name} (2)`); setDupOpen(true); }}><Copy className="size-4" /> {t("plan.duplicate")}</Button>
              <Button variant="danger" onClick={() => window.confirm(`${t("plan.archive")}?`) && archive.mutate()}>{t("plan.archive")}</Button>
            </div>
          )
        }
      />

      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault();
          runMut.mutate();
        }}
      >
        <Card>
          <CardHeader title={t("plan.lines")} description={linesHelp?.text} />
          <div className="group/field space-y-2 p-5">
            <div className="hidden grid-cols-[minmax(12rem,2fr)_8rem_8rem_8rem_8rem_2.5rem] gap-2 text-xs text-muted xl:grid">
              <span>{t("nav.products")}</span>
              <span className="text-right">{t("plan.price")} ({currency})</span>
              <span className="text-right">{t("plan.volume")}</span>
              <span className="text-right">{t("plan.activeCost")}</span>
              <span className="text-right">{t("plan.costOverride")}</span>
            </div>
            {lines.map((l, i) => {
              const active = lineInfo(l.product_id)?.active_unit_cost;
              return (
                <div key={i} className="grid grid-cols-2 gap-2 border-b border-line pb-3 sm:grid-cols-4 xl:grid-cols-[minmax(12rem,2fr)_8rem_8rem_8rem_8rem_2.5rem] xl:border-0 xl:pb-0">
                  <Select className="col-span-2 sm:col-span-4 xl:col-span-1" aria-label={t("nav.products")} value={l.product_id} disabled={!writable}
                    onChange={(e) => {
                      const pid = e.target.value;
                      const price = latestPrice(pid);
                      setLines(lines.map((x, j) => (j === i ? { ...x, product_id: pid, unit_price: x.unit_price || (price ? trimDecimal(price) : "") } : x)));
                    }}>
                    <option value="">—</option>
                    {sellable.map((p) => <option key={p.id} value={p.id} disabled={lines.some((x, j) => j !== i && x.product_id === p.id)}>{p.name} ({p.sku})</option>)}
                  </Select>
                  <DecimalInput aria-label={t("plan.price")} placeholder={t("plan.price")} suffix={currency} value={l.unit_price} disabled={!writable} onChange={(v) => setLines(lines.map((x, j) => (j === i ? { ...x, unit_price: v } : x)))} />
                  <DecimalInput aria-label={t("plan.volume")} placeholder={t("plan.volume")} suffix="unit" value={l.volume} disabled={!writable} onChange={(v) => setLines(lines.map((x, j) => (j === i ? { ...x, volume: v } : x)))} />
                  <div className="num flex h-10 items-center justify-end px-2 text-sm text-muted" title={t("plan.activeCost")}><span className="mr-auto text-xs xl:hidden">{t("plan.activeCost")}</span>{active ? money(active, currency, lang) : "—"}</div>
                  <DecimalInput aria-label={t("plan.costOverride")} placeholder={t("common.optional")} value={l.unit_cost_override} disabled={!writable} onChange={(v) => setLines(lines.map((x, j) => (j === i ? { ...x, unit_cost_override: v } : x)))} />
                  <Button type="button" variant="ghost" size="sm" disabled={!writable} onClick={() => setLines(lines.filter((_, j) => j !== i))} aria-label={t("common.remove")}><Trash2 className="size-4" /></Button>
                </div>
              );
            })}
            {linesHelp && <HelpPanel text={linesHelp.text} example={linesHelp.example} exampleLabel={exampleLabel} />}
            {writable && (
              <Button type="button" size="sm" variant="secondary" onClick={() => setLines([...lines, { product_id: "", unit_price: "", volume: "", unit_cost_override: "" }])}>
                <Plus className="size-4" /> {t("plan.addLine")}
              </Button>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title={t("plan.assumptions")} />
          <div className="space-y-6 p-5">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Field label={t("common.name")} help="plan.name" className="sm:col-span-2">{(fid) => <Input id={fid} required value={form.name} disabled={!writable} onChange={(e) => set({ name: e.target.value })} />}</Field>
              <Field label={t("plan.start")} help="plan.start">{(fid) => <Input id={fid} type="date" required value={form.period_start} disabled={!writable} onChange={(e) => set({ period_start: e.target.value })} />}</Field>
              <Field label={t("plan.months")} help="plan.months">
                {(fid) => (
                  <Select id={fid} value={form.period_months} disabled={!writable} onChange={(e) => set({ period_months: e.target.value })}>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{m}</option>)}
                  </Select>
                )}
              </Field>
            </div>

            <fieldset>
              <legend className="mb-3"><LegendWithHelp label={t("plan.changes")} help="plan.change" /></legend>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                {pctField("price", t("plan.priceChange"))}
                {pctField("volume", t("plan.volumeChange"))}
                {pctField("unit_cost", t("plan.unitCostChange"))}
                {pctField("variable", t("plan.variableChange"))}
                {pctField("fixed", t("plan.fixedChange"))}
              </div>
            </fieldset>

            <div className="grid gap-6 lg:grid-cols-2">
              <fieldset className="space-y-2">
                <legend className="mb-1"><LegendWithHelp label={t("plan.itemChanges")} help="plan.itemChanges" /></legend>
                {form.item_changes.map((x, i) => (
                  <div key={i} className="grid grid-cols-[1fr_7rem_2.5rem] gap-2">
                    <Select aria-label={t("costs.code")} value={x.code} disabled={!writable} onChange={(e) => set({ item_changes: form.item_changes.map((y, j) => (j === i ? { ...y, code: e.target.value } : y)) })}>
                      <option value="">—</option>
                      {(costs.data ?? []).filter((c) => c.cost_scope !== "PRODUCT").map((c) => <option key={c.id} value={c.code}>{c.code} · {c.name}</option>)}
                    </Select>
                    <DecimalInput aria-label="%" suffix="%" value={x.pct} disabled={!writable} onChange={(v) => set({ item_changes: form.item_changes.map((y, j) => (j === i ? { ...y, pct: v } : y)) })} />
                    <Button type="button" variant="ghost" size="sm" disabled={!writable} onClick={() => set({ item_changes: form.item_changes.filter((_, j) => j !== i) })} aria-label={t("common.remove")}><Trash2 className="size-4" /></Button>
                  </div>
                ))}
                {writable && <Button type="button" size="sm" variant="secondary" onClick={() => set({ item_changes: [...form.item_changes, { code: "", pct: "" }] })}><Plus className="size-4" /> {t("common.add")}</Button>}
              </fieldset>

              {manualDrivers.length > 0 && (
                <fieldset className="space-y-2">
                  <legend className="mb-1"><LegendWithHelp label={t("plan.otherActivity")} help="plan.otherActivity" /></legend>
                  {manualDrivers.map((d) => {
                    const row = form.other_activity.find((x) => x.code === d.code);
                    return (
                      <div key={d.id} className="grid grid-cols-[1fr_9rem] items-center gap-2">
                        <span className="text-sm">{d.name} <span className="text-xs text-muted">({d.unit_label ?? t(`drv.${d.driver_type}`)})</span></span>
                        <DecimalInput aria-label={d.name} value={row?.qty ?? ""} disabled={!writable}
                          onChange={(v) => set({ other_activity: [...form.other_activity.filter((x) => x.code !== d.code), { code: d.code, qty: v }] })} />
                      </div>
                    );
                  })}
                </fieldset>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Field label={t("plan.taxRegime")} help="plan.taxRegime">
                {(fid) => (
                  <Select id={fid} value={form.tax_regime} disabled={!writable} onChange={(e) => set({ tax_regime: e.target.value })}>
                    {["NONE", "PROFIT_BASED", "TURNOVER_FINAL"].map((x) => <option key={x} value={x}>{t(`tax.${x}`)}</option>)}
                  </Select>
                )}
              </Field>
              {form.tax_regime !== "NONE" && (
                <Field label={t("plan.taxRate")} help="plan.taxRate">{(fid) => <DecimalInput id={fid} suffix="%" value={form.tax_rate} disabled={!writable} onChange={(v) => set({ tax_rate: v })} />}</Field>
              )}
              {form.tax_regime === "TURNOVER_FINAL" && (
                <Field label={`${t("plan.exempt")} (${currency})`} help="plan.exempt">{(fid) => <DecimalInput id={fid} value={form.exempt} disabled={!writable} onChange={(v) => set({ exempt: v })} />}</Field>
              )}
              <Field label={t("plan.targetKind")} help="plan.target">
                {(fid) => (
                  <Select id={fid} value={form.target_kind} disabled={!writable} onChange={(e) => set({ target_kind: e.target.value })}>
                    <option value="">{t("costs.none")}</option>
                    {["OPERATING_PROFIT", "NET_PROFIT"].map((x) => <option key={x} value={x}>{t(`target.${x}`)}</option>)}
                  </Select>
                )}
              </Field>
              {form.target_kind && (
                <Field label={`${t("plan.targetAmount")} (${currency})`} help="plan.target">{(fid) => <DecimalInput id={fid} required value={form.target_amount} disabled={!writable} onChange={(v) => set({ target_amount: v })} />}</Field>
              )}
            </div>
          </div>
        </Card>

        {err && <Alert title={errorText(err)}>{trace.length > 0 && <div className="mt-2"><Trace lines={trace} /></div>}</Alert>}
        {writable && (
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="secondary" loading={save.isPending} onClick={() => save.mutate()}><Save className="size-4" /> {t("plan.save")}</Button>
            <Button type="submit" loading={runMut.isPending}><Play className="size-4" /> {t("plan.run")}</Button>
          </div>
        )}
      </form>

      <div className="mt-8">
        <h2 className="mb-4 text-lg font-semibold">{t("plan.result")}</h2>
        {shown ? <PlanResults run={shown} currency={currency} /> : latest.isLoading ? <Spinner /> : <Card><p className="p-8 text-center text-sm text-muted">{t("plan.noRun")}</p></Card>}
      </div>

      {(history.data?.length ?? 0) > 1 && (
        <Card className="mt-6">
          <CardHeader title={t("plan.history")} />
          <ul className="divide-y divide-line text-sm">
            {history.data!.map((h) => (
              <li key={h.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5">
                <span className="text-muted">{date(h.created_at, lang)} · {new Date(h.created_at).toLocaleTimeString(lang === "id" ? "id-ID" : "en-US", { hour: "2-digit", minute: "2-digit" })}</span>
                <span className="num">{t("plan.operating")}: <span className="font-medium">{money(h.operating_profit, currency, lang)}</span></span>
                <Badge tone={h.status === "OK" ? "ok" : "warn"}>{h.status}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Dialog open={dupOpen} onClose={() => setDupOpen(false)} title={t("plan.duplicate")}>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); dup.mutate(); }}>
          {dup.error && <Alert>{errorText(dup.error)}</Alert>}
          <Field label={t("plan.duplicateName")} help="plan.name">{(fid) => <Input id={fid} required value={dupName} onChange={(e) => setDupName(e.target.value)} />}</Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setDupOpen(false)}>{t("common.cancel")}</Button>
            <Button type="submit" loading={dup.isPending}>{t("common.save")}</Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
