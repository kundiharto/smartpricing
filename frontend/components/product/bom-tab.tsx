"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, DecimalInput, Dialog, Empty, Field, HelpPanel, Input, LegendWithHelp, Select, Spinner, statusTone, Table, Td, Th } from "@/components/ui";
import { useHelp } from "@/lib/help";
import { api, errorText } from "@/lib/api";
import { date, fractionToPercent, num, pct, percentToFraction, today, trimDecimal } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { byId, useAllProducts, useUnits } from "@/lib/queries";
import type { Bom, Product } from "@/lib/types";

type Line = { material_product_id: string; net_quantity: string; waste_pct: string };

export function BomTab({ product }: { product: Product }) {
  const { t, lang } = useI18n();
  const { orgId, can } = useOrg();
  const qc = useQueryClient();
  const materials = useAllProducts("MATERIAL");
  const units = byId(useUnits().data);
  const matMap = byId(materials.data);
  const [open, setOpen] = useState(false);
  const [head, setHead] = useState({ planned_output_qty: "", yield_pct: "100", effective_from: today(), notes: "" });
  const [lines, setLines] = useState<Line[]>([]);
  const [lineFocus, setLineFocus] = useState<string | null>(null);
  const { help, exampleLabel } = useHelp();

  const q = useQuery({ queryKey: ["bom", orgId, product.id], queryFn: () => api.get<Bom[]>(`/products/${product.id}/bom`) });
  const active = q.data?.find((b) => b.status === "ACTIVE");

  function startNew() {
    if (active) {
      setHead({ planned_output_qty: trimDecimal(active.planned_output_qty), yield_pct: fractionToPercent(active.process_yield_rate), effective_from: today(), notes: "" });
      setLines(active.items.map((i) => ({ material_product_id: i.material_product_id, net_quantity: trimDecimal(i.net_quantity), waste_pct: fractionToPercent(i.material_waste_rate) })));
    } else {
      setLines([{ material_product_id: materials.data?.[0]?.id ?? "", net_quantity: "", waste_pct: "0" }]);
    }
    setOpen(true);
  }

  const create = useMutation({
    mutationFn: () =>
      api.post(`/products/${product.id}/bom`, {
        planned_output_qty: head.planned_output_qty,
        process_yield_rate: percentToFraction(head.yield_pct),
        effective_from: head.effective_from,
        notes: head.notes || null,
        items: lines.map((l) => ({ material_product_id: l.material_product_id, net_quantity: l.net_quantity, material_waste_rate: percentToFraction(l.waste_pct || "0") })),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bom"] });
      setOpen(false);
    },
  });

  const setLine = (i: number, patch: Partial<Line>) => setLines(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={active ? `BOM ${t("common.version").toLowerCase()} ${active.version_number}` : t("prod.tab.bom")}
          description={
            active
              ? `${t("bom.output")}: ${num(active.planned_output_qty, lang)} · ${t("bom.yield")}: ${pct(active.process_yield_rate, lang)} · ${t("mp.from")} ${date(active.effective_from, lang)}`
              : t("bom.wasteHint")
          }
          action={can("products.write") && <Button size="sm" onClick={startNew}><Plus className="size-4" /> {t("bom.new")}</Button>}
        />
        {q.isLoading ? (
          <Spinner />
        ) : !active ? (
          <Empty>{t("bom.none")}</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>#</Th>
                <Th>{t("bom.material")}</Th>
                <Th align="right">{t("bom.netQty")}</Th>
                <Th align="right">{t("bom.waste")}</Th>
              </tr>
            </thead>
            <tbody>
              {active.items.map((i) => {
                const m = matMap[i.material_product_id];
                return (
                  <tr key={i.id}>
                    <Td className="text-muted">{i.line_no}</Td>
                    <Td><span className="font-medium">{m?.name ?? i.material_product_id}</span> <span className="font-mono text-xs text-muted">{m?.sku}</span></Td>
                    <Td align="right">{num(i.net_quantity, lang)} {m ? units[m.base_unit_id]?.code : ""}</Td>
                    <Td align="right">{pct(i.material_waste_rate, lang)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>

      {q.data && q.data.length > 1 && (
        <Card>
          <CardHeader title={t("common.version")} />
          <Table>
            <thead><tr><Th>{t("common.version")}</Th><Th>{t("common.status")}</Th><Th>{t("mp.from")}</Th><Th>{t("mp.to")}</Th><Th align="right">{t("bom.output")}</Th></tr></thead>
            <tbody>
              {q.data.map((b) => (
                <tr key={b.id}>
                  <Td>v{b.version_number}</Td>
                  <Td><Badge tone={statusTone(b.status)}>{t(`status.${b.status}`)}</Badge></Td>
                  <Td>{date(b.effective_from, lang)}</Td>
                  <Td className="text-muted">{date(b.effective_to, lang)}</Td>
                  <Td align="right">{num(b.planned_output_qty, lang)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title={t("bom.new")} wide>
        {!materials.data?.length ? (
          <Alert tone="warn">{t("bom.needMaterials")}</Alert>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="space-y-4">
            {create.error && <Alert>{errorText(create.error)}</Alert>}
            <Alert tone="info">{t("bom.wasteHint")}</Alert>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label={t("bom.output")} help="bom.output">{(id) => <DecimalInput id={id} required value={head.planned_output_qty} onChange={(v) => setHead({ ...head, planned_output_qty: v })} />}</Field>
              <Field label={t("bom.yield")} help="bom.yield">{(id) => <DecimalInput id={id} required suffix="%" value={head.yield_pct} onChange={(v) => setHead({ ...head, yield_pct: v })} />}</Field>
              <Field label={t("mp.from")} help="mp.from">{(id) => <Input id={id} type="date" required value={head.effective_from} onChange={(e) => setHead({ ...head, effective_from: e.target.value })} />}</Field>
            </div>
            <div className="space-y-2" onBlur={() => setLineFocus(null)}>
              <div className="grid grid-cols-[1fr_8rem_6rem_2.5rem] gap-2">
                <LegendWithHelp label={t("bom.material")} help="bom.material" />
                <LegendWithHelp label={t("bom.netQty")} help="bom.netQty" />
                <LegendWithHelp label={t("bom.waste")} help="bom.waste" />
              </div>
              {lines.map((l, i) => (
                <div key={i} className="grid grid-cols-[1fr_8rem_6rem_2.5rem] items-center gap-2">
                  <Select value={l.material_product_id} onFocus={() => setLineFocus("bom.material")} onChange={(e) => setLine(i, { material_product_id: e.target.value })} aria-label={t("bom.material")}>
                    {materials.data.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.sku})</option>)}
                  </Select>
                  <DecimalInput required value={l.net_quantity} onFocus={() => setLineFocus("bom.netQty")} onChange={(v) => setLine(i, { net_quantity: v })} aria-label={t("bom.netQty")} />
                  <DecimalInput suffix="%" value={l.waste_pct} onFocus={() => setLineFocus("bom.waste")} onChange={(v) => setLine(i, { waste_pct: v })} aria-label={t("bom.waste")} />
                  <Button type="button" variant="ghost" size="sm" onClick={() => setLines(lines.filter((_, j) => j !== i))} disabled={lines.length === 1} aria-label={t("common.remove")}>
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
              {lineFocus && help(lineFocus) && (
                <HelpPanel always text={help(lineFocus)!.text} example={help(lineFocus)!.example} exampleLabel={exampleLabel} />
              )}
              <Button type="button" variant="secondary" size="sm" onClick={() => setLines([...lines, { material_product_id: materials.data[0].id, net_quantity: "", waste_pct: "0" }])}>
                <Plus className="size-4" /> {t("bom.addLine")}
              </Button>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
              <Button type="submit" loading={create.isPending}>{t("common.save")}</Button>
            </div>
          </form>
        )}
      </Dialog>
    </div>
  );
}
