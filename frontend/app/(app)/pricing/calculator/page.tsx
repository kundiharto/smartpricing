"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { Alert, Button, Card, CardHeader, DecimalInput, Field, Input, PageHeader, Select, Stat, Trace } from "@/components/ui";
import { api, engineTrace, errorText } from "@/lib/api";
import { money, pct, percentToFraction, today } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { useAllProducts } from "@/lib/queries";
import type { PriceSummary, Recommendation } from "@/lib/types";

const METHODS = [
  "TARGET_CONTRIBUTION_MARGIN",
  "TARGET_GROSS_MARGIN",
  "MARKUP",
  "MINIMUM_VIABLE",
  "BREAK_EVEN",
  "TARGET_OPERATING_PROFIT",
  "COMPETITIVE",
  "VALUE_BASED",
] as const;
type Method = (typeof METHODS)[number];
type Fee = { name: string; rate: string; base: string };

const NEEDS: Record<Method, string[]> = {
  TARGET_CONTRIBUTION_MARGIN: ["margin"],
  TARGET_GROSS_MARGIN: ["margin"],
  MARKUP: ["markup"],
  MINIMUM_VIABLE: [],
  BREAK_EVEN: ["fixed", "volume"],
  TARGET_OPERATING_PROFIT: ["fixed", "volume", "top"],
  COMPETITIVE: ["reference", "adjust"],
  VALUE_BASED: ["reference"],
};

function Calculator() {
  const { t, lang } = useI18n();
  const { org, can } = useOrg();
  const params = useSearchParams();
  const qc = useQueryClient();
  const products = useAllProducts();
  const pricable = useMemo(() => (products.data ?? []).filter((p) => p.product_type !== "MATERIAL"), [products.data]);

  const [productId, setProductId] = useState(params.get("product") ?? "");
  const [method, setMethod] = useState<Method>("TARGET_CONTRIBUTION_MARGIN");
  const [v, setV] = useState({ unit_cost: "", variable_cost: "0", margin: "30", markup: "25", discount: "0", fixed: "", volume: "", top: "", reference: "", adjust: "0", tax: "0" });
  const [fees, setFees] = useState<Fee[]>([]);
  const [rounding, setRounding] = useState({ enabled: true, increment: "500", mode: "NEAREST", apply_to: "LIST_PRICE", margin_guard: true });
  const [effective, setEffective] = useState(today());
  const [savedId, setSavedId] = useState<string | null>(null);
  const currency = org?.default_currency ?? "IDR";
  const needs = NEEDS[method];

  const body = () => ({
    method,
    product_id: productId || null,
    unit_cost: productId ? null : v.unit_cost,
    variable_cost: v.variable_cost || "0",
    discount: percentToFraction(v.discount || "0"),
    fees: fees.filter((f) => f.name && f.rate).map((f) => ({ ...f, rate: percentToFraction(f.rate) })),
    turnover_tax_load: percentToFraction(v.tax || "0"),
    target_margin: needs.includes("margin") ? percentToFraction(v.margin) : null,
    markup: needs.includes("markup") ? percentToFraction(v.markup) : null,
    fixed_cost: needs.includes("fixed") ? v.fixed : null,
    volume: needs.includes("volume") ? v.volume : null,
    target_operating_profit: needs.includes("top") ? v.top : null,
    reference_price: needs.includes("reference") ? v.reference : null,
    adjustment: needs.includes("adjust") ? percentToFraction(v.adjust || "0") : "0",
    rounding: rounding.enabled
      ? { increment: rounding.increment, mode: rounding.mode, apply_to: rounding.apply_to, margin_guard: rounding.margin_guard }
      : null,
  });

  const calc = useMutation({ mutationFn: () => api.post<PriceSummary>("/pricing/calculate", body()), onSuccess: () => setSavedId(null) });
  const save = useMutation({
    mutationFn: () => api.post<Recommendation>("/pricing/recommend", { ...body(), effective_date: effective }),
    onSuccess: (r) => {
      setSavedId(r.id);
      qc.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
  const r = calc.data;
  const trace = engineTrace(calc.error);

  const input = (key: keyof typeof v, label: string, suffix?: string, hint?: string) => (
    <Field label={label} hint={hint}>{(id) => <DecimalInput id={id} suffix={suffix} value={v[key]} onChange={(x) => setV({ ...v, [key]: x })} required />}</Field>
  );

  return (
    <>
      <PageHeader title={t("nav.calculator")} description={t("price.marginDefHint")} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card>
          <form
            className="space-y-5 p-5"
            onSubmit={(e) => {
              e.preventDefault();
              calc.mutate();
            }}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("price.product")} className="sm:col-span-2">
                {(id) => (
                  <Select id={id} value={productId} onChange={(e) => setProductId(e.target.value)}>
                    <option value="">{t("price.manual")}</option>
                    {pricable.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                  </Select>
                )}
              </Field>
              {!productId && input("unit_cost", `${t("price.unitCost")} (${currency})`)}
              {input("variable_cost", `${t("price.variable")} (${currency})`)}
              <Field label={t("price.method")} className="sm:col-span-2">
                {(id) => (
                  <Select id={id} value={method} onChange={(e) => setMethod(e.target.value as Method)}>
                    {METHODS.map((m) => <option key={m} value={m}>{t(`method.${m}`)}</option>)}
                  </Select>
                )}
              </Field>
              {needs.includes("margin") && input("margin", t("price.margin"), "%")}
              {needs.includes("markup") && input("markup", t("price.markup"), "%")}
              {needs.includes("fixed") && input("fixed", `${t("price.fixed")} (${currency})`)}
              {needs.includes("volume") && input("volume", t("price.volume"))}
              {needs.includes("top") && input("top", `${t("price.top")} (${currency})`)}
              {needs.includes("reference") && input("reference", `${t("price.reference")} (${currency})`)}
              {needs.includes("adjust") && input("adjust", t("price.adjust"), "%")}
              {input("discount", t("price.discount"), "%")}
              {input("tax", t("price.taxLoad"), "%")}
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">{t("price.fees")}</legend>
              {fees.map((f, i) => (
                <div key={i} className="grid grid-cols-[1fr_6rem_9rem_auto] gap-2">
                  <Input aria-label={t("price.feeName")} placeholder={t("price.feeName")} value={f.name} onChange={(e) => setFees(fees.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
                  <DecimalInput aria-label={t("price.feeRate")} suffix="%" value={f.rate} onChange={(val) => setFees(fees.map((x, j) => (j === i ? { ...x, rate: val } : x)))} />
                  <Select aria-label={t("price.feeBase")} value={f.base} onChange={(e) => setFees(fees.map((x, j) => (j === i ? { ...x, base: e.target.value } : x)))}>
                    {["NET_PRICE", "LIST_PRICE", "PRODUCT_COST"].map((b) => <option key={b} value={b}>{t(`base.${b}`)}</option>)}
                  </Select>
                  <Button type="button" variant="ghost" size="sm" onClick={() => setFees(fees.filter((_, j) => j !== i))} aria-label={t("common.remove")}><Trash2 className="size-4" /></Button>
                </div>
              ))}
              <Button type="button" variant="secondary" size="sm" onClick={() => setFees([...fees, { name: "", rate: "", base: "NET_PRICE" }])}>
                <Plus className="size-4" /> {t("price.addFee")}
              </Button>
            </fieldset>

            <fieldset className="space-y-3 rounded-lg border border-line p-4">
              <legend className="px-1 text-sm font-medium">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={rounding.enabled} onChange={(e) => setRounding({ ...rounding, enabled: e.target.checked })} className="accent-[var(--accent)]" />
                  {t("price.rounding")}
                </label>
              </legend>
              {rounding.enabled && (
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label={t("price.increment")}>{(id) => <DecimalInput id={id} value={rounding.increment} onChange={(x) => setRounding({ ...rounding, increment: x })} />}</Field>
                  <Field label={t("price.mode")}>
                    {(id) => (
                      <Select id={id} value={rounding.mode} onChange={(e) => setRounding({ ...rounding, mode: e.target.value })}>
                        <option value="NEAREST">NEAREST</option>
                        <option value="UP">UP</option>
                        <option value="DOWN">DOWN</option>
                      </Select>
                    )}
                  </Field>
                  <Field label={t("price.applyTo")}>
                    {(id) => (
                      <Select id={id} value={rounding.apply_to} onChange={(e) => setRounding({ ...rounding, apply_to: e.target.value })}>
                        <option value="LIST_PRICE">{t("base.LIST_PRICE")}</option>
                        <option value="NET_PRICE">{t("base.NET_PRICE")}</option>
                      </Select>
                    )}
                  </Field>
                  <label className="flex items-center gap-2 text-sm sm:col-span-3">
                    <input type="checkbox" checked={rounding.margin_guard} onChange={(e) => setRounding({ ...rounding, margin_guard: e.target.checked })} className="accent-[var(--accent)]" />
                    {t("price.guard")}
                  </label>
                </div>
              )}
            </fieldset>

            <Button type="submit" className="w-full" loading={calc.isPending}>{t("price.calculate")}</Button>
          </form>
        </Card>

        <div className="space-y-5">
          {calc.error && <Alert title={errorText(calc.error)}>{trace.length > 0 && <div className="mt-2"><Trace lines={trace} /></div>}</Alert>}
          {!r && !calc.error && (
            <Card><p className="p-8 text-center text-sm text-muted">{t("price.empty")}</p></Card>
          )}
          {r && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <Stat tone="accent" label={t("price.list")} value={money(r.list_price, r.currency, lang)} sub={`${t("price.net")}: ${money(r.recommended_price, r.currency, lang)}`} />
                <Stat label={t("price.minimum")} value={money(r.minimum_price, r.currency, lang)} sub={`${t("price.unitCost")}: ${money(r.unit_cost, r.currency, lang, true)}`} />
                <Stat label={t("price.cm")} value={pct(r.contribution_margin, lang)} sub={`${t("price.contribution")}: ${money(r.contribution, r.currency, lang)}`} />
                <Stat label={t("price.gm")} value={pct(r.gross_margin, lang)} sub={`${t("price.feeTotal")}: ${money(r.fee_total, r.currency, lang)}`} />
              </div>
              {r.warnings.map((w) => (
                <Alert key={w.code} tone="warn" title={t(`warn.${w.code}`)}>{w.message}</Alert>
              ))}
              <Card>
                <CardHeader title={t("cost.explain")} description={`${t("price.target")}: ${r.target_price}`} />
                <div className="space-y-3 p-5">
                  <Trace lines={[...r.engine.price.trace, ...(r.engine.rounding?.trace ?? [])]} />
                </div>
              </Card>
              {productId && can("pricing.recommend") && (
                <Card>
                  <div className="flex flex-wrap items-end gap-3 p-5">
                    <Field label={t("price.effective")} className="w-48">
                      {(id) => <Input id={id} type="date" value={effective} onChange={(e) => setEffective(e.target.value)} />}
                    </Field>
                    <Button onClick={() => save.mutate()} loading={save.isPending} disabled={Boolean(savedId)}>
                      <Save className="size-4" /> {t("price.save")}
                    </Button>
                    {savedId && (
                      <Link href={`/pricing/recommendations/${savedId}`} className="text-sm font-medium text-accent hover:underline">
                        {t("price.saved")} →
                      </Link>
                    )}
                  </div>
                  {save.error && <div className="px-5 pb-5"><Alert>{errorText(save.error)}</Alert></div>}
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

export default function CalculatorPage() {
  return (
    <Suspense>
      <Calculator />
    </Suspense>
  );
}
