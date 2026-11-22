"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Badge, Button, Card, CardHeader, DecimalInput, Dialog, Empty, Field, HelpPanel, Input, LegendWithHelp, Select, Spinner, Stat, statusTone, Table, Td, Textarea, Th, Trace } from "@/components/ui";
import { useHelp } from "@/lib/help";
import { api, engineTrace, errorText } from "@/lib/api";
import { date, dateTime, money, num, percentToFraction, today } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { CostingVersion, Product } from "@/lib/types";

type Resource = { name: string; hours: string; hourly_rate: string };

export function CostingTab({ product }: { product: Product }) {
  const { t, lang } = useI18n();
  const { orgId, can } = useOrg();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const list = useQuery({ queryKey: ["costing", orgId, product.id], queryFn: () => api.get<CostingVersion[]>(`/products/${product.id}/costing`) });
  const active = list.data?.find((v) => v.status === "ACTIVE");
  const selectedId = selected ?? active?.id ?? list.data?.[0]?.id ?? null;
  const detail = useQuery({
    queryKey: ["costing-detail", orgId, selectedId],
    queryFn: () => api.get<CostingVersion>(`/products/${product.id}/costing/${selectedId}`),
    enabled: Boolean(selectedId),
  });

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat tone="accent" label={t("cost.active")} value={active ? money(active.calculated_unit_cost, active.currency, lang, true) : "—"} sub={active ? `v${active.version_number} · ${t(`cost.${active.costing_structure}`)}` : undefined} />
        <Stat label={t("cost.asOf")} value={active ? date(active.as_of_date, lang) : "—"} />
        <Stat label={t("common.version")} value={list.data?.length ?? 0} />
      </div>

      <Card>
        <CardHeader
          title={t("cost.history")}
          action={can("costing.write") && <Button size="sm" onClick={() => setOpen(true)}><Plus className="size-4" /> {t("cost.run")}</Button>}
        />
        {list.isLoading ? (
          <Spinner />
        ) : !list.data?.length ? (
          <Empty>{t("cost.none")}</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>{t("common.version")}</Th>
                <Th>{t("cost.structure")}</Th>
                <Th>{t("common.status")}</Th>
                <Th>{t("cost.asOf")}</Th>
                <Th>{t("mp.from")} – {t("mp.to")}</Th>
                <Th align="right">{t("cost.unitCost")}</Th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((v) => (
                <tr
                  key={v.id}
                  onClick={() => setSelected(v.id)}
                  className={v.id === selectedId ? "cursor-pointer bg-accent-soft/50" : "cursor-pointer hover:bg-surface-2"}
                >
                  <Td className="font-medium">v{v.version_number}</Td>
                  <Td>{t(`cost.${v.costing_structure}`)}</Td>
                  <Td><Badge tone={statusTone(v.status)}>{t(`status.${v.status}`)}</Badge></Td>
                  <Td>{date(v.as_of_date, lang)}</Td>
                  <Td className="text-muted">{date(v.effective_from, lang)} – {v.effective_to ? date(v.effective_to, lang) : "…"}</Td>
                  <Td align="right" className="font-medium">{money(v.calculated_unit_cost, v.currency, lang, true)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {detail.data && <CostingDetail version={detail.data} />}

      <RunCostingDialog open={open} onClose={() => setOpen(false)} product={product} onDone={(id) => setSelected(id)} />
    </div>
  );
}

function CostingDetail({ version }: { version: CostingVersion }) {
  const { t, lang } = useI18n();
  const snap = version.calculation_snapshot;
  const values = (snap?.values ?? {}) as Record<string, unknown>;
  const breakdown = values.breakdown as Record<string, string> | undefined;
  const labels: Record<string, string> = {
    material: t("bom.material"),
    labor: t("cost.labor"),
    machine: t("cost.machines"),
    overhead: "Overhead",
    packaging: "Packaging",
    other_direct: t("cost.other"),
    rework: "Rework",
  };
  const chart = breakdown
    ? Object.entries(labels)
        .map(([k, label]) => ({ label, value: Number(breakdown[k] ?? 0) }))
        .filter((r) => r.value > 0)
    : [];

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader
          title={`${t("cost.breakdown")} · v${version.version_number}`}
          description={`${t(`cost.${version.costing_structure}`)} · ${dateTime(version.created_at, lang)}`}
        />
        <div className="p-5">
          {chart.length ? (
            <>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <CartesianGrid horizontal={false} stroke="var(--border)" />
                    <XAxis type="number" tickFormatter={(v) => new Intl.NumberFormat(lang === "id" ? "id-ID" : "en-US", { notation: "compact" }).format(v)} fontSize={12} stroke="var(--muted)" />
                    <YAxis type="category" dataKey="label" width={130} fontSize={12} stroke="var(--muted)" />
                    <Tooltip formatter={(v: number) => money(String(v), version.currency, lang)} cursor={{ fill: "var(--surface-2)" }} />
                    <Bar dataKey="value" fill="var(--accent)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-muted">{t("cost.batchCost")}</dt><dd className="num font-medium">{money(values.batch_cost as string, version.currency, lang)}</dd></div>
                <div><dt className="text-muted">{t("cost.goodUnits")}</dt><dd className="num font-medium">{num(values.good_units as string, lang)}</dd></div>
              </dl>
            </>
          ) : (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {Object.entries(values)
                .filter(([, v]) => typeof v === "string")
                .map(([k, v]) => (
                  <div key={k}><dt className="text-muted">{k}</dt><dd className="num font-medium">{num(v as string, lang)}</dd></div>
                ))}
            </dl>
          )}
        </div>
      </Card>
      <Card>
        <CardHeader title={t("cost.explain")} description={`${t("rec.engine")} ${version.engine_version} · ${version.input_hash.slice(0, 12)}…`} />
        <div className="p-5">
          {snap?.trace?.length ? (
            <Trace lines={snap.trace} />
          ) : (
            <p className="text-sm text-muted">
              {t("cost.justification")}: {(version.input_snapshot as { request?: { justification?: string } } | undefined)?.request?.justification ?? "—"}
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}

function ResourceRows({ label, help, rows, onChange }: { label: string; help: string; rows: Resource[]; onChange: (r: Resource[]) => void }) {
  const { t } = useI18n();
  const { help: getHelp, exampleLabel } = useHelp();
  const entry = getHelp(help);
  return (
    <fieldset className="group/field space-y-2">
      <legend className="mb-2"><LegendWithHelp label={label} help={help} /></legend>
      {rows.length > 0 && (
        <div className="grid grid-cols-[1fr_6rem_9rem_2.5rem] gap-2 text-xs text-muted">
          <span>{t("common.name")}</span><span className="text-right">{t("cost.hours")}</span><span className="text-right">{t("cost.rate")}</span>
        </div>
      )}
      {rows.map((r, i) => (
        <div key={i} className="grid grid-cols-[1fr_6rem_9rem_2.5rem] gap-2">
          <Input aria-label={t("common.name")} placeholder={t("common.name")} value={r.name} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} required />
          <DecimalInput aria-label={t("cost.hours")} placeholder={t("cost.hours")} value={r.hours} onChange={(v) => onChange(rows.map((x, j) => (j === i ? { ...x, hours: v } : x)))} required />
          <DecimalInput aria-label={t("cost.rate")} placeholder={t("cost.rate")} value={r.hourly_rate} onChange={(v) => onChange(rows.map((x, j) => (j === i ? { ...x, hourly_rate: v } : x)))} required />
          <Button type="button" variant="ghost" size="sm" onClick={() => onChange(rows.filter((_, j) => j !== i))} aria-label={t("common.remove")}><Trash2 className="size-4" /></Button>
        </div>
      ))}
      {entry && <HelpPanel text={entry.text} example={entry.example} exampleLabel={exampleLabel} />}
      <Button type="button" size="sm" variant="secondary" onClick={() => onChange([...rows, { name: "", hours: "", hourly_rate: "" }])}><Plus className="size-4" /> {t("common.add")}</Button>
    </fieldset>
  );
}

function RunCostingDialog({ open, onClose, product, onDone }: { open: boolean; onClose: () => void; product: Product; onDone: (id: string) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const defaultStructure = product.product_type === "FINISHED_GOOD" ? "BOM_BASED" : product.product_type === "TRADED_GOOD" ? "LANDED_COST" : "DIRECT_INPUT";
  const [structure, setStructure] = useState(defaultStructure);
  const [method, setMethod] = useState("STANDARD");
  const [nature, setNature] = useState("STANDARD");
  const [asOf, setAsOf] = useState(today());
  const [activate, setActivate] = useState(true);
  const [labor, setLabor] = useState<Resource[]>([]);
  const [machines, setMachines] = useState<Resource[]>([]);
  const [m, setM] = useState({ overhead: "0", packaging: "0", other_direct: "0", scrap: "0", rework: "0", rework_cost: "0" });
  const [landed, setLanded] = useState({ quantity: "", unit_purchase_price: "", fx_rate: "1", freight: "0", insurance: "0", duty: "0", handling: "0", other_acquisition: "0", qty_received_good: "" });
  const [direct, setDirect] = useState({ unit_cost: "", justification: "" });
  const { structure: structureHelp } = useHelp();

  useEffect(() => {
    if (open) setStructure(defaultStructure);
  }, [open, defaultStructure]);

  const run = useMutation({
    mutationFn: () => {
      const base = { costing_structure: structure, costing_method: method, data_nature: nature, as_of_date: asOf, activate };
      if (structure === "BOM_BASED")
        return api.post<CostingVersion>(`/products/${product.id}/costing`, {
          ...base,
          labor,
          machines,
          overhead: m.overhead || "0",
          packaging: m.packaging || "0",
          other_direct: m.other_direct || "0",
          scrap_rate: percentToFraction(m.scrap || "0"),
          rework_rate: percentToFraction(m.rework || "0"),
          rework_cost_per_unit: m.rework_cost || "0",
        });
      if (structure === "LANDED_COST")
        return api.post<CostingVersion>(`/products/${product.id}/costing`, {
          ...base,
          landed: {
            quantity: landed.quantity,
            unit_purchase_price: landed.unit_purchase_price,
            fx_rate: landed.fx_rate || "1",
            freight: landed.freight || "0",
            insurance: landed.insurance || "0",
            import_duty_rate: percentToFraction(landed.duty || "0"),
            handling: landed.handling || "0",
            other_acquisition: landed.other_acquisition || "0",
            qty_received_good: landed.qty_received_good || null,
          },
        });
      return api.post<CostingVersion>(`/products/${product.id}/costing`, { ...base, unit_cost: direct.unit_cost, justification: direct.justification });
    },
    onSuccess: (v) => {
      qc.invalidateQueries({ queryKey: ["costing"] });
      onDone(v.id);
      onClose();
    },
  });

  const trace = engineTrace(run.error);
  const dec = (obj: Record<string, string>, set: (o: never) => void, key: string, label: string, suffix?: string, help?: string) => (
    <Field label={label} help={help}>{(id) => <DecimalInput id={id} suffix={suffix} value={obj[key]} onChange={(v) => set({ ...obj, [key]: v } as never)} />}</Field>
  );

  return (
    <Dialog open={open} onClose={onClose} title={t("cost.run")} wide>
      <form onSubmit={(e) => { e.preventDefault(); run.mutate(); }} className="space-y-5">
        {run.error && (
          <Alert title={errorText(run.error)}>{trace.length > 0 && <div className="mt-2"><Trace lines={trace} /></div>}</Alert>
        )}
        <div className="grid gap-4 sm:grid-cols-4">
          <Field label={t("cost.structure")} help="cost.structure" className="sm:col-span-2">
            {(id) => (
              <Select id={id} value={structure} onChange={(e) => setStructure(e.target.value)}>
                {product.product_type === "FINISHED_GOOD" && <option value="BOM_BASED">{t("cost.BOM_BASED")}</option>}
                <option value="LANDED_COST">{t("cost.LANDED_COST")}</option>
                <option value="DIRECT_INPUT">{t("cost.DIRECT_INPUT")}</option>
              </Select>
            )}
          </Field>
          <Field label={t("cost.asOf")} help="cost.asOf">{(id) => <Input id={id} type="date" required value={asOf} onChange={(e) => setAsOf(e.target.value)} />}</Field>
          <Field label={t("mp.nature")} help="cost.nature">
            {(id) => (
              <Select id={id} value={nature} onChange={(e) => { setNature(e.target.value); setMethod(e.target.value === "ACTUAL" ? "ACTUAL" : e.target.value === "ESTIMATE" ? "ESTIMATED" : "STANDARD"); }}>
                {["STANDARD", "ACTUAL", "ESTIMATE"].map((n) => <option key={n} value={n}>{t(`nature.${n}`)}</option>)}
              </Select>
            )}
          </Field>
        </div>

        <Alert tone="info" title={t(`cost.${structure}`)}>{structureHelp(structure)}</Alert>

        {structure === "BOM_BASED" && (
          <div className="space-y-5">
            <ResourceRows label={t("cost.labor")} help="cost.labor" rows={labor} onChange={setLabor} />
            <ResourceRows label={t("cost.machines")} help="cost.machines" rows={machines} onChange={setMachines} />
            <div className="grid gap-4 sm:grid-cols-3">
              {dec(m, setM as never, "overhead", t("cost.overhead"), undefined, "cost.overhead")}
              {dec(m, setM as never, "packaging", t("cost.packaging"), undefined, "cost.packaging")}
              {dec(m, setM as never, "other_direct", t("cost.other"), undefined, "cost.other")}
              {dec(m, setM as never, "scrap", t("cost.scrap"), "%", "cost.scrap")}
              {dec(m, setM as never, "rework", t("cost.rework"), "%", "cost.rework")}
              {dec(m, setM as never, "rework_cost", t("cost.reworkCost"), undefined, "cost.reworkCost")}
            </div>
          </div>
        )}

        {structure === "LANDED_COST" && (
          <div className="grid gap-4 sm:grid-cols-3">
            {dec(landed, setLanded as never, "quantity", t("cost.qty"), undefined, "cost.qty")}
            {dec(landed, setLanded as never, "unit_purchase_price", t("cost.purchasePrice"), undefined, "cost.purchasePrice")}
            {dec(landed, setLanded as never, "fx_rate", t("cost.fx"), undefined, "cost.fx")}
            {dec(landed, setLanded as never, "freight", t("cost.freight"), undefined, "cost.freight")}
            {dec(landed, setLanded as never, "insurance", t("cost.insurance"), undefined, "cost.insurance")}
            {dec(landed, setLanded as never, "duty", t("cost.duty"), "%", "cost.duty")}
            {dec(landed, setLanded as never, "handling", t("cost.handling"), undefined, "cost.handling")}
            {dec(landed, setLanded as never, "other_acquisition", t("cost.otherAcq"), undefined, "cost.otherAcq")}
            {dec(landed, setLanded as never, "qty_received_good", `${t("cost.goodQty")} (${t("common.optional")})`, undefined, "cost.goodQty")}
          </div>
        )}

        {structure === "DIRECT_INPUT" && (
          <div className="grid gap-4">
            <Field label={t("cost.unitCost")} help="cost.unitCost">{(id) => <DecimalInput id={id} required value={direct.unit_cost} onChange={(v) => setDirect({ ...direct, unit_cost: v })} />}</Field>
            <Field label={t("cost.justification")} help="cost.justification">{(id) => <Textarea id={id} required value={direct.justification} onChange={(e) => setDirect({ ...direct, justification: e.target.value })} />}</Field>
          </div>
        )}

        <div className="flex items-center gap-1.5">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={activate} onChange={(e) => setActivate(e.target.checked)} className="accent-[var(--accent)]" />
            {t("cost.activate")}
          </label>
          <LegendWithHelp label={t("cost.activate")} help="cost.activate" iconOnly />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" loading={run.isPending}>{t("cost.run")}</Button>
        </div>
      </form>
    </Dialog>
  );
}
