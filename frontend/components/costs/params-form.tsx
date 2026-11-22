"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button, DecimalInput, Field, HelpPanel, Input, LegendWithHelp, Select } from "@/components/ui";
import { fractionToPercent, percentToFraction, today, trimDecimal } from "@/lib/format";
import { useHelp } from "@/lib/help";
import { useI18n } from "@/lib/i18n";
import type { Behavior, CostVersion } from "@/lib/types";

export type ParamsState = {
  effective_from: string;
  data_nature: string;
  base_amount: string;
  rate: string;
  percentage: string; // dalam persen
  percentage_base: "REVENUE" | "COGS";
  step_mode: "TABLE" | "CEILING";
  tiers: { from_activity: string; to_activity: string; amount: string }[];
  capacity_per_resource: string;
  cost_per_resource: string;
  max_resources: string;
  minimum_amount: string;
  maximum_amount: string;
  escalation_type: "" | "NOMINAL" | "SIMPLE_PCT" | "COMPOUND_PCT";
  escalation_rate: string; // persen
  escalation_amount: string;
  escalation_frequency: string;
  escalation_cap: string;
  source_reference: string;
};

export function emptyParams(): ParamsState {
  return {
    effective_from: today(),
    data_nature: "STANDARD",
    base_amount: "",
    rate: "",
    percentage: "",
    percentage_base: "REVENUE",
    step_mode: "TABLE",
    tiers: [{ from_activity: "0", to_activity: "", amount: "" }],
    capacity_per_resource: "",
    cost_per_resource: "",
    max_resources: "",
    minimum_amount: "",
    maximum_amount: "",
    escalation_type: "",
    escalation_rate: "",
    escalation_amount: "",
    escalation_frequency: "ANNUAL",
    escalation_cap: "",
    source_reference: "",
  };
}

const s = (v: string | null | undefined) => (v === null || v === undefined ? "" : trimDecimal(v));

export function paramsFromVersion(v: CostVersion): ParamsState {
  return {
    ...emptyParams(),
    data_nature: v.data_nature,
    base_amount: s(v.base_amount),
    rate: s(v.rate),
    percentage: v.percentage ? fractionToPercent(v.percentage) : "",
    percentage_base: v.percentage_base ?? "REVENUE",
    step_mode: v.step_mode ?? "TABLE",
    tiers: v.tiers?.length ? v.tiers.map((t) => ({ from_activity: s(t.from_activity), to_activity: s(t.to_activity), amount: s(t.amount) })) : emptyParams().tiers,
    capacity_per_resource: s(v.capacity_per_resource),
    cost_per_resource: s(v.cost_per_resource),
    max_resources: s(v.max_resources),
    minimum_amount: s(v.minimum_amount),
    maximum_amount: s(v.maximum_amount),
    escalation_type: v.escalation_type ?? "",
    escalation_rate: v.escalation_rate ? fractionToPercent(v.escalation_rate) : "",
    escalation_amount: s(v.escalation_amount),
    escalation_frequency: v.escalation_frequency ?? "ANNUAL",
    escalation_cap: s(v.escalation_cap),
    source_reference: v.source_reference ?? "",
  };
}

const opt = (v: string) => (v.trim() === "" ? null : v.trim());

/** Hanya kirim parameter yang relevan untuk perilaku biaya; validasi akhir oleh engine di backend. */
export function paramsPayload(behavior: Behavior, p: ParamsState) {
  const out: Record<string, unknown> = {
    effective_from: p.effective_from,
    data_nature: p.data_nature,
    minimum_amount: opt(p.minimum_amount),
    maximum_amount: opt(p.maximum_amount),
    source_reference: opt(p.source_reference),
  };
  if (behavior === "FIXED" || behavior === "SEMI_VARIABLE") out.base_amount = opt(p.base_amount);
  if (behavior === "VARIABLE" || behavior === "SEMI_VARIABLE") out.rate = opt(p.rate);
  if (behavior === "PERCENTAGE") {
    out.percentage = p.percentage ? percentToFraction(p.percentage) : null;
    out.percentage_base = p.percentage_base;
  }
  if (behavior === "STEP_FIXED") {
    out.step_mode = p.step_mode;
    if (p.step_mode === "TABLE") out.tiers = p.tiers.filter((t) => t.to_activity || t.amount);
    else {
      out.capacity_per_resource = opt(p.capacity_per_resource);
      out.cost_per_resource = opt(p.cost_per_resource);
      out.max_resources = opt(p.max_resources);
    }
  }
  if (p.escalation_type) {
    out.escalation_type = p.escalation_type;
    out.escalation_frequency = p.escalation_frequency;
    if (p.escalation_type === "NOMINAL") out.escalation_amount = opt(p.escalation_amount);
    else out.escalation_rate = p.escalation_rate ? percentToFraction(p.escalation_rate) : null;
    out.escalation_cap = opt(p.escalation_cap);
  }
  return out;
}

export function ParamsForm({ behavior, value, onChange, currency }: { behavior: Behavior; value: ParamsState; onChange: (p: ParamsState) => void; currency: string }) {
  const { t } = useI18n();
  const { help, exampleLabel } = useHelp();
  const p = value;
  const set = (patch: Partial<ParamsState>) => onChange({ ...p, ...patch });
  const dec = (key: keyof ParamsState, label: string, helpKey?: string, suffix?: string) => (
    <Field label={label} help={helpKey}>
      {(id) => <DecimalInput id={id} suffix={suffix} value={p[key] as string} onChange={(v) => set({ [key]: v } as Partial<ParamsState>)} />}
    </Field>
  );
  const tiersHelp = help("cost.tiers");

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("mp.from")} help="cost.effective">
          {(id) => <Input id={id} type="date" required value={p.effective_from} onChange={(e) => set({ effective_from: e.target.value })} />}
        </Field>
        <Field label={t("mp.nature")} help="plan.dataNature">
          {(id) => (
            <Select id={id} value={p.data_nature} onChange={(e) => set({ data_nature: e.target.value })}>
              {["STANDARD", "ACTUAL", "ESTIMATE"].map((n) => <option key={n} value={n}>{t(`nature.${n}`)}</option>)}
            </Select>
          )}
        </Field>
        {(behavior === "FIXED" || behavior === "SEMI_VARIABLE") && dec("base_amount", `${t("costs.baseAmount")} (${currency})`, "cost.baseAmount")}
        {(behavior === "VARIABLE" || behavior === "SEMI_VARIABLE") && dec("rate", `${t("costs.rate")} (${currency})`, "cost.rate")}
        {behavior === "PERCENTAGE" && (
          <>
            {dec("percentage", t("costs.percentage"), "cost.percentage", "%")}
            <Field label={t("costs.percentageBase")} help="cost.percentageBase">
              {(id) => (
                <Select id={id} value={p.percentage_base} onChange={(e) => set({ percentage_base: e.target.value as "REVENUE" | "COGS" })}>
                  <option value="REVENUE">{t("costs.revenue")}</option>
                  <option value="COGS">{t("costs.cogs")}</option>
                </Select>
              )}
            </Field>
          </>
        )}
        {behavior === "STEP_FIXED" && (
          <Field label={t("costs.stepMode")} help="cost.stepMode" className="sm:col-span-2">
            {(id) => (
              <Select id={id} value={p.step_mode} onChange={(e) => set({ step_mode: e.target.value as "TABLE" | "CEILING" })}>
                <option value="TABLE">{t("costs.tiers")}</option>
                <option value="CEILING">{t("costs.capacity")}</option>
              </Select>
            )}
          </Field>
        )}
      </div>

      {behavior === "STEP_FIXED" && p.step_mode === "TABLE" && (
        <fieldset className="group/field space-y-2">
          <legend className="mb-2"><LegendWithHelp label={t("costs.tiers")} help="cost.tiers" /></legend>
          <div className="grid grid-cols-[1fr_1fr_1fr_2.5rem] gap-2 text-xs text-muted">
            <span>{t("costs.from")}</span><span>{t("costs.to")}</span><span>{t("costs.amount")} ({currency})</span>
          </div>
          {p.tiers.map((tier, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_2.5rem] gap-2">
              {(["from_activity", "to_activity", "amount"] as const).map((k) => (
                <DecimalInput key={k} aria-label={t(k === "amount" ? "costs.amount" : k === "from_activity" ? "costs.from" : "costs.to")} value={tier[k]}
                  onChange={(v) => set({ tiers: p.tiers.map((x, j) => (j === i ? { ...x, [k]: v } : x)) })} />
              ))}
              <Button type="button" variant="ghost" size="sm" disabled={p.tiers.length === 1} onClick={() => set({ tiers: p.tiers.filter((_, j) => j !== i) })} aria-label={t("common.remove")}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          {tiersHelp && <HelpPanel text={tiersHelp.text} example={tiersHelp.example} exampleLabel={exampleLabel} />}
          <Button type="button" size="sm" variant="secondary" onClick={() => {
            const last = p.tiers[p.tiers.length - 1];
            const next = last?.to_activity ? String(BigInt(last.to_activity.split(".")[0] || "0") + BigInt(1)) : "";
            set({ tiers: [...p.tiers, { from_activity: next, to_activity: "", amount: "" }] });
          }}>
            <Plus className="size-4" /> {t("costs.addTier")}
          </Button>
        </fieldset>
      )}

      {behavior === "STEP_FIXED" && p.step_mode === "CEILING" && (
        <div className="grid gap-4 sm:grid-cols-3">
          {dec("capacity_per_resource", t("costs.capacity"), "cost.capacity")}
          {dec("cost_per_resource", `${t("costs.costPerResource")} (${currency})`, "cost.costPerResource")}
          {dec("max_resources", `${t("costs.maxResources")} (${t("common.optional")})`, "cost.maxResources")}
        </div>
      )}

      <details className="rounded-lg border border-line p-4 [&[open]>summary]:mb-4">
        <summary className="cursor-pointer text-sm font-medium">{t("costs.escalation")} · {t("costs.minimum")} / {t("costs.maximum")}</summary>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("costs.escType")} help="cost.escalation">
            {(id) => (
              <Select id={id} value={p.escalation_type} onChange={(e) => set({ escalation_type: e.target.value as ParamsState["escalation_type"] })}>
                <option value="">{t("costs.none")}</option>
                {(["SIMPLE_PCT", "COMPOUND_PCT", "NOMINAL"] as const).map((x) => <option key={x} value={x}>{t(`esc.${x}`)}</option>)}
              </Select>
            )}
          </Field>
          {p.escalation_type && (
            <Field label={t("costs.escFreq")}>
              {(id) => (
                <Select id={id} value={p.escalation_frequency} onChange={(e) => set({ escalation_frequency: e.target.value })}>
                  {["MONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL"].map((f) => <option key={f} value={f}>{t(`freq.${f}`)}</option>)}
                </Select>
              )}
            </Field>
          )}
          {p.escalation_type && p.escalation_type !== "NOMINAL" && dec("escalation_rate", t("costs.escRate"), undefined, "%")}
          {p.escalation_type === "NOMINAL" && dec("escalation_amount", `${t("costs.escAmount")} (${currency})`)}
          {p.escalation_type && dec("escalation_cap", `${t("costs.escCap")} (${t("common.optional")})`)}
          {dec("minimum_amount", `${t("costs.minimum")} (${t("common.optional")})`, "cost.minmax")}
          {dec("maximum_amount", `${t("costs.maximum")} (${t("common.optional")})`, "cost.minmax")}
          <Field label={`${t("mp.source")} (${t("common.optional")})`} help="cost.source" className="sm:col-span-2">
            {(id) => <Input id={id} value={p.source_reference} onChange={(e) => set({ source_reference: e.target.value })} />}
          </Field>
        </div>
      </details>
    </div>
  );
}
