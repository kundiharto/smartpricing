"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Spinner, Table, Td, Th } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { money, num, pct } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { CompareEntry, Scenario } from "@/lib/types";

type Row = { label: string; get: (e: CompareEntry) => string | null | undefined; kind: "money" | "pct" | "units"; better?: "higher" | "lower" };

export default function ComparePage() {
  const { t, lang } = useI18n();
  const { orgId, org, can } = useOrg();
  const currency = org?.default_currency ?? "IDR";
  const scenarios = useQuery({ queryKey: ["scenarios", orgId], queryFn: () => api.get<Scenario[]>("/scenarios") });
  const [picked, setPicked] = useState<string[]>([]);
  const cmp = useMutation({
    mutationFn: () => {
      // Skenario Dasar selalu di kolom pertama sebagai acuan selisih.
      const order = (id: string) => (scenarios.data?.find((x) => x.id === id)?.scenario_type === "BASE" ? 0 : 1);
      const ids = [...picked].sort((a, b) => order(a) - order(b));
      return api.post<CompareEntry[]>("/scenarios/compare", { scenario_ids: ids, rerun: can("planning.write") });
    },
  });

  const rows: Row[] = [
    { label: t("plan.revenue"), get: (e) => e.pnl?.revenue, kind: "money", better: "higher" },
    { label: t("plan.cogs"), get: (e) => e.pnl?.cogs, kind: "money", better: "lower" },
    { label: t("plan.gross"), get: (e) => e.pnl?.gross_profit, kind: "money", better: "higher" },
    { label: t("plan.variable"), get: (e) => e.pnl?.variable_costs, kind: "money", better: "lower" },
    { label: t("plan.contribution"), get: (e) => e.pnl?.contribution, kind: "money", better: "higher" },
    { label: t("plan.fixed"), get: (e) => e.pnl?.fixed_costs, kind: "money", better: "lower" },
    { label: t("plan.operating"), get: (e) => e.pnl?.operating_profit, kind: "money", better: "higher" },
    { label: `${t("plan.margin")} ${t("plan.operating").toLowerCase()}`, get: (e) => e.pnl?.operating_margin, kind: "pct", better: "higher" },
    { label: t("plan.net"), get: (e) => e.pnl?.net_profit, kind: "money", better: "higher" },
    { label: t("plan.bepUnits"), get: (e) => e.break_even?.units, kind: "units", better: "lower" },
    { label: t("plan.bepRevenue"), get: (e) => e.break_even?.revenue, kind: "money", better: "lower" },
    { label: t("plan.safety"), get: (e) => e.break_even?.margin_of_safety, kind: "pct", better: "higher" },
    { label: t("plan.needUnits"), get: (e) => e.target?.units, kind: "units", better: "lower" },
  ];
  const fmt = (k: Row["kind"], v: string | null | undefined) => (k === "money" ? money(v, currency, lang) : k === "pct" ? pct(v, lang, 1) : num(v, lang, 0));
  const data = cmp.data ?? [];
  const chart = data.filter((e) => e.pnl).map((e) => ({
    name: e.name,
    revenue: Number(e.pnl!.revenue),
    operating: Number(e.pnl!.operating_profit),
    net: Number(e.pnl!.net_profit),
  }));
  const compact = (v: number) => new Intl.NumberFormat(lang === "id" ? "id-ID" : "en-US", { notation: "compact" }).format(v);

  return (
    <>
      <Link href="/planning" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> {t("plan.title")}
      </Link>
      <PageHeader title={t("cmp.title")} description={t("cmp.pick")} />
      <Card>
        {scenarios.isLoading ? <Spinner /> : (
          <div className="flex flex-wrap items-end gap-3 p-5">
            <div className="flex flex-1 flex-wrap gap-2">
              {scenarios.data?.map((s) => {
                const on = picked.includes(s.id);
                return (
                  <label key={s.id} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${on ? "border-accent bg-accent-soft" : "border-line"}`}>
                    <input type="checkbox" className="accent-[var(--accent)]" checked={on} disabled={!on && picked.length >= 6}
                      onChange={() => setPicked(on ? picked.filter((x) => x !== s.id) : [...picked, s.id])} />
                    {s.name}
                  </label>
                );
              })}
            </div>
            <Button disabled={picked.length < 2} loading={cmp.isPending} onClick={() => cmp.mutate()}>{t("cmp.run")}</Button>
          </div>
        )}
      </Card>
      {cmp.error && <div className="mt-4"><Alert>{errorText(cmp.error)}</Alert></div>}

      {data.length > 0 && (
        <>
          <Card className="mt-6">
            <Table>
              <thead>
                <tr>
                  <Th>{t("cmp.metric")}</Th>
                  {data.map((e) => (
                    <Th key={e.scenario_id} align="right">
                      <span className="block normal-case">{e.name}</span>
                      <span className="font-normal normal-case">{t(`stype.${e.scenario_type}`)}</span>
                    </Th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const base = data[0] ? r.get(data[0]) : null;
                  return (
                    <tr key={r.label}>
                      <Td className="text-muted">{r.label}</Td>
                      {data.map((e, i) => {
                        const v = r.get(e);
                        const diff = i > 0 && v != null && base != null ? Number(v) - Number(base) : null;
                        const good = diff === null || diff === 0 ? null : (diff > 0) === (r.better === "higher");
                        return (
                          <Td key={e.scenario_id} align="right">
                            <span className={Number(v) < 0 ? "text-danger" : ""}>{v == null ? "—" : fmt(r.kind, v)}</span>
                            {diff !== null && diff !== 0 && (
                              <span className={`block text-xs ${good ? "text-ok" : "text-danger"}`}>
                                {diff > 0 ? "+" : ""}{fmt(r.kind, String(diff))}
                              </span>
                            )}
                          </Td>
                        );
                      })}
                    </tr>
                  );
                })}
                <tr>
                  <Td className="text-muted">{t("common.status")}</Td>
                  {data.map((e) => (
                    <Td key={e.scenario_id} align="right">
                      {e.status === "OK" ? <Badge tone="ok">OK</Badge> : <Badge tone="warn">{e.status}</Badge>}
                      {(e.warnings?.length ?? 0) > 0 && <span className="block text-xs text-warn">{e.warnings!.map((w) => t(`warn.${w.code}`)).join(", ")}</span>}
                      {e.message && <span className="block text-xs text-danger">{e.message}</span>}
                    </Td>
                  ))}
                </tr>
              </tbody>
            </Table>
            <p className="px-5 py-3 text-xs text-muted">{t("cmp.diff")}</p>
          </Card>

          {chart.length > 0 && (
            <Card className="mt-6">
              <CardHeader title={`${t("plan.revenue")} · ${t("plan.operating")} · ${t("plan.net")}`} />
              <div className="h-80 p-5">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart}>
                    <CartesianGrid vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="name" fontSize={12} stroke="var(--muted)" />
                    <YAxis tickFormatter={compact} fontSize={12} stroke="var(--muted)" width={60} />
                    <Tooltip formatter={(v: number) => money(String(v), currency, lang)} cursor={{ fill: "var(--surface-2)" }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="revenue" name={t("plan.revenue")} fill="#98a2b3" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="operating" name={t("plan.operating")} fill="var(--accent)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="net" name={t("plan.net")} fill="#5fa8a0" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}
        </>
      )}
    </>
  );
}
