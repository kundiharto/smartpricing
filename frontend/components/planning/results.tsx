"use client";

import { Badge, Card, CardHeader, Stat, Table, Td, Th, Trace, Alert } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { Run } from "@/lib/types";

/** Hasil simulasi: KPI, laba rugi, BEP & target, profitabilitas produk, dan rincian biaya. */
export function PlanResults({ run, currency }: { run: Run; currency: string }) {
  const { t, lang } = useI18n();
  const v = run.result_snapshot.values;
  const names = run.result_snapshot.products ?? {};
  const p = v.pnl;
  const b = v.break_even;
  const m = (x: string | null | undefined) => money(x, currency, lang);
  const neg = (x: string | null | undefined) => Number(x ?? 0) < 0;

  const pnlRows: [string, string, string | null, boolean?][] = [
    [t("plan.revenue"), p.revenue, null],
    [`− ${t("plan.cogs")}`, p.cogs, null],
    [t("plan.gross"), p.gross_profit, p.gross_margin, true],
    [`− ${t("plan.variable")}`, p.variable_costs, null],
    [t("plan.contribution"), p.contribution, p.contribution_margin, true],
    [`− ${t("plan.fixed")}`, p.fixed_costs, null],
    [t("plan.operating"), p.operating_profit, p.operating_margin, true],
    [`− ${t("plan.incomeTax")}`, p.income_tax, null],
    [t("plan.net"), p.net_profit, p.net_margin, true],
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label={t("plan.revenue")} value={m(p.revenue)} sub={`${num(v.units, lang, 0)} unit`} />
        <Stat tone="accent" label={t("plan.operating")} value={<span className={neg(p.operating_profit) ? "text-danger" : ""}>{m(p.operating_profit)}</span>} sub={`${t("plan.margin")} ${pct(p.operating_margin, lang)}`} />
        <Stat label={t("plan.net")} value={<span className={neg(p.net_profit) ? "text-danger" : ""}>{m(p.net_profit)}</span>} sub={`${t("plan.margin")} ${pct(p.net_margin, lang)}`} />
        <Stat label={t("plan.bepUnits")} value={b.units ? num(b.units, lang, 0) : "—"} sub={b.margin_of_safety ? `${t("plan.safety")} ${pct(b.margin_of_safety, lang, 1)}` : t(`warn.${b.status}`)} />
      </div>

      {run.result_snapshot.warnings.map((w, i) => (
        <Alert key={i} tone="warn" title={t(`warn.${w.code}`)}>{w.message}</Alert>
      ))}
      {run.result_snapshot.items_without_version?.length > 0 && (
        <Alert tone="info">{t("costs.noVersion")}: {run.result_snapshot.items_without_version.join(", ")}</Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader title={t("plan.pnl")} description={`${v.period_months} ${t("plan.monthsShort")}`} />
          <Table>
            <tbody>
              {pnlRows.map(([label, value, margin, bold]) => (
                <tr key={label} className={bold ? "bg-surface-2/60" : ""}>
                  <Td className={bold ? "font-semibold" : "text-muted"}>{label}</Td>
                  <Td align="right" className={`${bold ? "font-semibold" : ""} ${neg(value) ? "text-danger" : ""}`}>{m(value)}</Td>
                  <Td align="right" className="w-24 text-xs text-muted">{margin ? pct(margin, lang, 1) : ""}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card className="min-w-0">
          <CardHeader title={t("plan.bep")} description={b.assumption} />
          <dl className="divide-y divide-line text-sm">
            {[
              [t("plan.bepUnits"), b.units ? `${num(b.units, lang, 0)} unit` : t(`warn.${b.status}`)],
              [t("plan.bepRevenue"), m(b.revenue)],
              [t("plan.safety"), b.margin_of_safety ? pct(b.margin_of_safety, lang, 1) : "—"],
              [t("plan.ucm"), m(b.unit_contribution)],
              [t("plan.ranges"), b.profitable_ranges.length ? b.profitable_ranges.map(([a, z]) => `${num(a, lang, 0)}–${num(z, lang, 0)}`).join(" · ") : "—"],
            ].map(([k, val]) => (
              <div key={k} className="flex justify-between gap-4 px-5 py-2.5"><dt className="text-muted">{k}</dt><dd className="num text-right font-medium">{val}</dd></div>
            ))}
          </dl>
          <p className="px-5 pb-3 text-xs text-muted">{t("plan.safetyHint")}</p>
          {v.target && (
            <div className="border-t border-line p-5">
              <p className="text-sm font-semibold">{t("plan.targetResult")}: {t(`target.${v.target.kind}`)} {m(v.target.amount)}</p>
              {v.target.units ? (
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <div><p className="text-muted">{t("plan.needUnits")}</p><p className="num font-semibold">{num(v.target.units, lang, 0)} unit</p>
                    <p className="text-xs text-muted">{pct(v.target.change_vs_plan, lang, 1)} {t("plan.vsPlan")}</p></div>
                  <div><p className="text-muted">{t("plan.needRevenue")}</p><p className="num font-semibold">{m(v.target.revenue)}</p></div>
                </div>
              ) : (
                <p className="mt-2 text-sm text-danger">{t("plan.notReachable")}</p>
              )}
              {(v.target.capacity_exceeded_items?.length ?? 0) > 0 && (
                <p className="mt-2 text-sm text-warn">{t("plan.capacityNeeded")}: {v.target.capacity_exceeded_items!.join(", ")}</p>
              )}
              {v.target.achieved && <Badge tone="ok">{t("plan.achieved")}</Badge>}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title={t("plan.products")} />
        <Table>
          <thead>
            <tr>
              <Th>{t("nav.products")}</Th>
              <Th align="right">{t("plan.volume")}</Th>
              <Th align="right">{t("plan.revenue")}</Th>
              <Th align="right">{t("plan.contribution")}</Th>
              <Th align="right">CM</Th>
              <Th align="right">{t("plan.allocated")}</Th>
              <Th align="right">{t("plan.afterAlloc")}</Th>
            </tr>
          </thead>
          <tbody>
            {v.lines.map((l) => (
              <tr key={l.product}>
                <Td className="font-medium">{names[l.product]?.name ?? l.product} <span className="font-mono text-xs text-muted">{names[l.product]?.sku}</span></Td>
                <Td align="right">{num(l.volume, lang, 0)}</Td>
                <Td align="right">{m(l.revenue)}</Td>
                <Td align="right" className={neg(l.contribution) ? "text-danger" : ""}>{m(l.contribution)}</Td>
                <Td align="right" className="text-muted">{pct(l.contribution_margin, lang, 1)}</Td>
                <Td align="right" className="text-muted">{m(l.allocated_costs)}</Td>
                <Td align="right" className={`font-medium ${neg(l.profit_after_allocation) ? "text-danger" : ""}`}>{m(l.profit_after_allocation)}</Td>
              </tr>
            ))}
            <tr>
              <td colSpan={6} className="border-b border-line px-4 py-3 text-muted">{t("plan.companyCosts")}</td>
              <Td align="right" className="whitespace-nowrap text-muted">− {m(v.company_level_costs)}</Td>
            </tr>
            <tr className="bg-surface-2/60">
              <td colSpan={6} className="border-b border-line px-4 py-3 font-semibold">{t("plan.operating")}</td>
              <Td align="right" className="whitespace-nowrap font-semibold">{m(p.operating_profit)}</Td>
            </tr>
          </tbody>
        </Table>
      </Card>

      <Card>
        <CardHeader title={t("plan.costDetail")} description={v.excluded_product_scope.length ? `${t("plan.excluded")}: ${v.excluded_product_scope.join(", ")}` : undefined} />
        <Table>
          <thead>
            <tr>
              <Th>{t("costs.code")}</Th>
              <Th>{t("common.name")}</Th>
              <Th>{t("costs.behavior")}</Th>
              <Th align="right">{t("costs.fixed")}</Th>
              <Th align="right">{t("costs.variable")}</Th>
              <Th align="right">{t("costs.total")}</Th>
            </tr>
          </thead>
          <tbody>
            {v.costs.map((c) => (
              <tr key={c.code}>
                <Td className="font-mono text-xs">{c.code}</Td>
                <Td>
                  {c.name}
                  {(c.tier || c.resource_count || c.escalation || c.capacity_exceeded) && (
                    <span className="block text-xs text-muted">
                      {c.tier && `tier ${num(c.tier[0], lang, 0)}–${num(c.tier[1], lang, 0)}`}
                      {c.resource_count && `${num(String(c.resource_count), lang, 0)} × ${t("costs.costPerResource").toLowerCase()}`}
                      {c.escalation && ` · ${c.escalation}`}
                      {c.capacity_exceeded && <span className="text-warn"> · {t("warn.CAPACITY_EXCEEDED")}</span>}
                    </span>
                  )}
                </Td>
                <Td><Badge>{t(`beh.${c.behavior}`)}</Badge></Td>
                <Td align="right">{m(c.fixed)}</Td>
                <Td align="right">{m(c.variable)}</Td>
                <Td align="right" className="font-medium">{m(c.total)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      <details className="rounded-xl border border-line bg-surface p-5">
        <summary className="cursor-pointer text-sm font-medium">{t("cost.explain")} · {t("rec.engine")} {run.engine_version} · {run.input_hash.slice(0, 12)}…</summary>
        <div className="mt-4"><Trace lines={run.result_snapshot.trace} /></div>
      </details>
    </div>
  );
}
