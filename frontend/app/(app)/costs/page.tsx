"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Settings2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { emptyParams, ParamsForm, paramsPayload, type ParamsState } from "@/components/costs/params-form";
import {
  Alert, Badge, Button, Card, CardHeader, DecimalInput, Dialog, Empty, Field, Input, PageHeader, Select, Spinner, Stat, statusTone, Table, Td, Textarea, Th,
} from "@/components/ui";
import { api, engineTrace, errorText } from "@/lib/api";
import { describeCost } from "@/lib/cost-format";
import { money, today } from "@/lib/format";
import { useHelp } from "@/lib/help";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { useDrivers } from "@/lib/queries";
import type { Behavior, CostItem, CostPreview } from "@/lib/types";

const CATEGORIES = ["FIXED_OPERATING", "ADMINISTRATIVE", "SELLING", "DISTRIBUTION", "PRODUCTION_OVERHEAD", "DIRECT_LABOR", "DIRECT_MATERIAL", "VARIABLE_OPERATING", "FINANCIAL", "TAX_STATUTORY", "OTHER"];
const BEHAVIORS: Behavior[] = ["FIXED", "VARIABLE", "SEMI_VARIABLE", "STEP_FIXED", "PERCENTAGE"];
const SCOPES = ["PERIOD", "ALLOCATION_POOL", "PRODUCT"] as const;
const DRIVER_TYPES = ["SALES_UNITS", "PRODUCTION_UNITS", "REVENUE", "LABOR_HOURS", "MACHINE_HOURS", "CUSTOM"];

export default function CostsPage() {
  const { t, lang } = useI18n();
  const { orgId, org, can } = useOrg();
  const currency = org?.default_currency ?? "IDR";
  const [adding, setAdding] = useState(false);
  const [driversOpen, setDriversOpen] = useState(false);
  const q = useQuery({ queryKey: ["costs", orgId], queryFn: () => api.get<CostItem[]>("/costs") });

  const groups = SCOPES.map((scope) => ({ scope, items: (q.data ?? []).filter((c) => c.cost_scope === scope) })).filter((g) => g.items.length);

  return (
    <>
      <PageHeader
        title={t("costs.title")}
        description={t("costs.subtitle")}
        action={
          can("costs.write") && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setDriversOpen(true)}><Settings2 className="size-4" /> {t("costs.drivers")}</Button>
              <Button onClick={() => setAdding(true)}><Plus className="size-4" /> {t("costs.add")}</Button>
            </div>
          )
        }
      />

      <CostSimulator currency={currency} />

      {q.isLoading ? (
        <Spinner />
      ) : !q.data?.length ? (
        <Card className="mt-6"><Empty>{t("costs.empty")}</Empty></Card>
      ) : (
        groups.map((g) => (
          <Card key={g.scope} className="mt-6">
            <CardHeader title={t(`scope.${g.scope}`)} />
            <Table>
              <thead>
                <tr>
                  <Th>{t("costs.code")}</Th>
                  <Th>{t("common.name")}</Th>
                  <Th>{t("costs.behavior")}</Th>
                  <Th>{t("costs.category")}</Th>
                  <Th>{t("costs.params")}</Th>
                  <Th>{t("common.status")}</Th>
                </tr>
              </thead>
              <tbody>
                {g.items.map((c) => (
                  <tr key={c.id} className="hover:bg-surface-2">
                    <Td className="font-mono text-xs whitespace-nowrap">{c.code}</Td>
                    <Td><Link href={`/costs/${c.id}`} className="font-medium hover:text-accent hover:underline">{c.name}</Link></Td>
                    <Td><Badge>{t(`beh.${c.behavior_type}`)}</Badge></Td>
                    <Td className="text-muted">{t(`cat.${c.category}`)}</Td>
                    <Td className="num text-sm">{describeCost(c, t, lang, currency)}</Td>
                    <Td>
                      <div className="flex items-center gap-1.5">
                        <Badge tone={statusTone(c.status)}>{t(`status.${c.status}`)}</Badge>
                        {c.cost_scope === "ALLOCATION_POOL" && !c.has_allocation && <Badge tone="warn">{t("costs.allocation")}?</Badge>}
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        ))
      )}

      <AddCostDialog open={adding} onClose={() => setAdding(false)} currency={currency} />
      <DriversDialog open={driversOpen} onClose={() => setDriversOpen(false)} />
    </>
  );
}

function CostSimulator({ currency }: { currency: string }) {
  const { t, lang } = useI18n();
  const [v, setV] = useState({ units: "", revenue: "", cogs: "", months: "1", date: today() });
  const preview = useMutation({
    mutationFn: () =>
      api.post<CostPreview>("/costs/preview", {
        units: v.units || "0", revenue: v.revenue || "0", cogs: v.cogs || "0", period_months: Number(v.months) || 1, as_of_date: v.date,
      }),
  });
  const r = preview.data?.values;
  return (
    <Card>
      <CardHeader title={t("costs.simulate")} description={t("costs.simulateHint")} />
      <form className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3" onSubmit={(e) => { e.preventDefault(); preview.mutate(); }}>
        <Field label={t("costs.units")} help="costs.simulate">{(id) => <DecimalInput id={id} value={v.units} onChange={(x) => setV({ ...v, units: x })} />}</Field>
        <Field label={`${t("costs.revenue")} (${currency})`}>{(id) => <DecimalInput id={id} value={v.revenue} onChange={(x) => setV({ ...v, revenue: x })} />}</Field>
        <Field label={`${t("costs.cogs")} (${currency})`}>{(id) => <DecimalInput id={id} value={v.cogs} onChange={(x) => setV({ ...v, cogs: x })} />}</Field>
        <Field label={t("costs.months")}>
          {(id) => (
            <Select id={id} value={v.months} onChange={(e) => setV({ ...v, months: e.target.value })}>
              {[1, 3, 6, 12].map((m) => <option key={m} value={m}>{m}</option>)}
            </Select>
          )}
        </Field>
        <Field label={t("common.date")}>{(id) => <Input id={id} type="date" value={v.date} onChange={(e) => setV({ ...v, date: e.target.value })} />}</Field>
        <div className="flex justify-end sm:col-span-2 xl:col-span-3"><Button type="submit" loading={preview.isPending}>{t("costs.simulate")}</Button></div>
      </form>
      {preview.error && <div className="px-5 pb-5"><Alert>{errorText(preview.error)}</Alert></div>}
      {r && (
        <div className="space-y-3 px-5 pb-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label={t("costs.fixed")} value={money(r.fixed_total, currency, lang)} />
            <Stat label={t("costs.variable")} value={money(r.variable_total, currency, lang)} />
            <Stat tone="accent" label={t("costs.total")} value={money(r.total, currency, lang)} />
          </div>
          {preview.data!.warnings.map((w, i) => <Alert key={i} tone="warn">{w.message}</Alert>)}
          {preview.data!.excluded_product_scope?.length > 0 && (
            <Alert tone="info">{t("plan.excluded")}: {preview.data!.excluded_product_scope.join(", ")}</Alert>
          )}
          {preview.data!.items_without_version.length > 0 && (
            <Alert tone="info">{t("costs.noVersion")}: {preview.data!.items_without_version.join(", ")}</Alert>
          )}
        </div>
      )}
    </Card>
  );
}

function AddCostDialog({ open, onClose, currency }: { open: boolean; onClose: () => void; currency: string }) {
  const { t } = useI18n();
  const { behavior: behaviorHelp } = useHelp();
  const qc = useQueryClient();
  const router = useRouter();
  const drivers = useDrivers();
  const [head, setHead] = useState({ code: "", name: "", category: "FIXED_OPERATING", behavior_type: "FIXED" as Behavior, cost_scope: "PERIOD", driver_id: "", period_months: "1", description: "" });
  const [params, setParams] = useState<ParamsState>(emptyParams());
  const needsDriver = !["FIXED", "PERCENTAGE"].includes(head.behavior_type);

  const create = useMutation({
    mutationFn: () =>
      api.post<CostItem>("/costs", {
        ...head,
        driver_id: needsDriver ? head.driver_id || null : null,
        period_months: Number(head.period_months),
        description: head.description || null,
        params: paramsPayload(head.behavior_type, params),
      }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["costs"] });
      onClose();
      setHead({ ...head, code: "", name: "", description: "" });
      setParams(emptyParams());
      router.push(`/costs/${c.id}`);
    },
  });
  const trace = engineTrace(create.error);

  return (
    <Dialog open={open} onClose={onClose} title={t("costs.add")} wide>
      <form className="space-y-5" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
        {create.error && <Alert title={errorText(create.error)}>{trace.length > 0 && <span className="text-xs">{trace.at(-1)}</span>}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("costs.code")} help="cost.code">{(id) => <Input id={id} required value={head.code} onChange={(e) => setHead({ ...head, code: e.target.value.toUpperCase().replace(/\s+/g, "-") })} />}</Field>
          <Field label={t("common.name")} help="cost.name">{(id) => <Input id={id} required value={head.name} onChange={(e) => setHead({ ...head, name: e.target.value })} />}</Field>
          <Field label={t("costs.category")} help="cost.category">
            {(id) => (
              <Select id={id} value={head.category} onChange={(e) => setHead({ ...head, category: e.target.value })}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{t(`cat.${c}`)}</option>)}
              </Select>
            )}
          </Field>
          <Field label={t("costs.scope")} help="cost.scope">
            {(id) => (
              <Select id={id} value={head.cost_scope} onChange={(e) => setHead({ ...head, cost_scope: e.target.value })}>
                {SCOPES.map((s) => <option key={s} value={s}>{t(`scope.${s}`)}</option>)}
              </Select>
            )}
          </Field>
          <div className="space-y-2 sm:col-span-2">
            <Field label={t("costs.behavior")} help="cost.behavior">
              {(id) => (
                <Select id={id} value={head.behavior_type} onChange={(e) => setHead({ ...head, behavior_type: e.target.value as Behavior })}>
                  {BEHAVIORS.map((b) => <option key={b} value={b}>{t(`beh.${b}`)}</option>)}
                </Select>
              )}
            </Field>
            <Alert tone="info" title={t(`beh.${head.behavior_type}`)}>{behaviorHelp(head.behavior_type)}</Alert>
          </div>
          {needsDriver && (
            <Field label={t("costs.driver")} help="cost.driver">
              {(id) =>
                drivers.data?.length ? (
                  <Select id={id} required value={head.driver_id} onChange={(e) => setHead({ ...head, driver_id: e.target.value })}>
                    <option value="">—</option>
                    {drivers.data.map((d) => <option key={d.id} value={d.id}>{d.name} ({t(`drv.${d.driver_type}`)})</option>)}
                  </Select>
                ) : (
                  <Alert tone="warn">{t("costs.driverEmpty")}</Alert>
                )
              }
            </Field>
          )}
          {head.behavior_type !== "VARIABLE" && head.behavior_type !== "PERCENTAGE" && (
            <Field label={t("costs.period")} help="cost.period">
              {(id) => (
                <Select id={id} value={head.period_months} onChange={(e) => setHead({ ...head, period_months: e.target.value })}>
                  {[1, 3, 6, 12].map((m) => <option key={m} value={m}>{t(`period.${m}`)}</option>)}
                </Select>
              )}
            </Field>
          )}
        </div>
        <ParamsForm behavior={head.behavior_type} value={params} onChange={setParams} currency={currency} />
        <Field label={`${t("prod.description")} (${t("common.optional")})`}>
          {(id) => <Textarea id={id} value={head.description} onChange={(e) => setHead({ ...head, description: e.target.value })} />}
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" loading={create.isPending}>{t("common.save")}</Button>
        </div>
      </form>
    </Dialog>
  );
}

function DriversDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const drivers = useDrivers();
  const [d, setD] = useState({ code: "", name: "", driver_type: "SALES_UNITS", unit_label: "" });
  const add = useMutation({
    mutationFn: () => api.post("/cost-drivers", { ...d, unit_label: d.unit_label || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["drivers"] });
      setD({ code: "", name: "", driver_type: d.driver_type, unit_label: "" });
    },
  });
  return (
    <Dialog open={open} onClose={onClose} title={t("costs.drivers")} wide>
      <div className="space-y-4">
        {!drivers.data?.length ? <Alert tone="info">{t("costs.driverEmpty")}</Alert> : (
          <Table>
            <thead><tr><Th>{t("costs.code")}</Th><Th>{t("common.name")}</Th><Th>{t("prod.type")}</Th><Th>{t("prod.unit")}</Th></tr></thead>
            <tbody>
              {drivers.data.map((x) => (
                <tr key={x.id}><Td className="font-mono text-xs">{x.code}</Td><Td>{x.name}</Td><Td className="text-muted">{t(`drv.${x.driver_type}`)}</Td><Td className="text-muted">{x.unit_label ?? "—"}</Td></tr>
              ))}
            </tbody>
          </Table>
        )}
        <form className="grid gap-4 border-t border-line pt-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          {add.error && <div className="sm:col-span-2"><Alert>{errorText(add.error)}</Alert></div>}
          <Field label={t("costs.code")} help="drv.code">{(id) => <Input id={id} required value={d.code} onChange={(e) => setD({ ...d, code: e.target.value.toUpperCase().replace(/\s+/g, "-") })} />}</Field>
          <Field label={t("common.name")}>{(id) => <Input id={id} required value={d.name} placeholder={t("drv.MACHINE_HOURS")} onChange={(e) => setD({ ...d, name: e.target.value })} />}</Field>
          <Field label={t("prod.type")} help="drv.type">
            {(id) => (
              <Select id={id} value={d.driver_type} onChange={(e) => setD({ ...d, driver_type: e.target.value })}>
                {DRIVER_TYPES.map((x) => <option key={x} value={x}>{t(`drv.${x}`)}</option>)}
              </Select>
            )}
          </Field>
          <Field label={`${t("prod.unit")} (${t("common.optional")})`}>{(id) => <Input id={id} value={d.unit_label} placeholder="unit, jam, kg" onChange={(e) => setD({ ...d, unit_label: e.target.value })} />}</Field>
          <div className="flex justify-end sm:col-span-2"><Button type="submit" loading={add.isPending}><Plus className="size-4" /> {t("costs.addDriver")}</Button></div>
        </form>
      </div>
    </Dialog>
  );
}
