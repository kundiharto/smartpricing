"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RecommendationTable } from "@/components/recommendation-table";
import { Card, CardHeader, Empty, PageHeader, Spinner, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime, money } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { byId, useAllProducts } from "@/lib/queries";
import type { AuditLog, Product, Recommendation } from "@/lib/types";

export default function DashboardPage() {
  const { t, lang } = useI18n();
  const { org, orgId, can } = useOrg();
  const products = useAllProducts();
  const productMap = byId(products.data);

  const counts = useQuery({
    queryKey: ["dash-counts", orgId],
    queryFn: async () => {
      const [all, mats] = await Promise.all([
        api.page<Product[]>("/products", { query: { limit: 1, status: "ACTIVE" } }),
        api.page<Product[]>("/products", { query: { limit: 1, status: "ACTIVE", product_type: "MATERIAL" } }),
      ]);
      return { products: all.meta.total ?? 0, materials: mats.meta.total ?? 0 };
    },
  });
  const recs = useQuery({
    queryKey: ["recommendations", orgId, "dash"],
    queryFn: () => api.page<Recommendation[]>("/pricing/recommendations", { query: { limit: 50 } }),
    enabled: can("pricing.read"),
  });
  const audit = useQuery({
    queryKey: ["audit", orgId, "dash"],
    queryFn: () => api.get<AuditLog[]>("/audit-logs", { query: { limit: 8 } }),
    enabled: can("audit.read"),
  });

  // Rekomendasi terbaru per produk, untuk grafik biaya vs harga.
  const latest = new Map<string, Recommendation>();
  for (const r of recs.data?.data ?? []) if (!latest.has(r.product_id)) latest.set(r.product_id, r);
  const chart = [...latest.values()].slice(0, 8).map((r) => ({
    name: productMap[r.product_id]?.sku ?? "…",
    cost: Number(r.unit_cost ?? 0),
    price: Number(r.recommended_price),
  }));

  const steps = [
    { label: t("dash.step1"), done: (counts.data?.products ?? 0) > 0, href: "/products" },
    { label: t("dash.step2"), done: (counts.data?.materials ?? 0) > 0, href: "/products" },
    { label: t("dash.step3"), done: (recs.data?.meta.total ?? 0) > 0, href: "/products" },
    { label: t("dash.step4"), done: (recs.data?.meta.total ?? 0) > 0, href: "/pricing/calculator" },
  ];
  const allDone = steps.every((s) => s.done);
  const fmtCompact = (v: number) => new Intl.NumberFormat(lang === "id" ? "id-ID" : "en-US", { notation: "compact" }).format(v);

  return (
    <>
      <PageHeader title={org?.name ?? t("dash.title")} description={org?.business_models.map((m) => t(`bm.${m}`)).join(" · ")} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label={t("dash.products")} value={counts.data?.products ?? "—"} />
        <Stat label={t("dash.materials")} value={counts.data?.materials ?? "—"} />
        <Stat tone="accent" label={t("dash.recommendations")} value={recs.data?.meta.total ?? "—"} />
      </div>

      {!allDone && (
        <Card className="mt-6">
          <CardHeader title={t("dash.start")} />
          <ol className="grid gap-2 p-5 sm:grid-cols-2">
            {steps.map((s, i) => (
              <li key={i}>
                <Link href={s.href} className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm hover:bg-surface-2">
                  {s.done ? <CheckCircle2 className="size-5 text-ok" /> : <Circle className="size-5 text-muted" />}
                  <span className={s.done ? "text-muted line-through" : "font-medium"}>{s.label}</span>
                </Link>
              </li>
            ))}
          </ol>
        </Card>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-5">
        <Card className="min-w-0 xl:col-span-3">
          <CardHeader title={t("dash.chart")} />
          <div className="h-72 p-5">
            {recs.isLoading ? (
              <Spinner />
            ) : chart.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart}>
                  <CartesianGrid vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="name" fontSize={12} stroke="var(--muted)" />
                  <YAxis tickFormatter={fmtCompact} fontSize={12} stroke="var(--muted)" width={56} />
                  <Tooltip formatter={(v: number) => money(String(v), org?.default_currency, lang)} cursor={{ fill: "var(--surface-2)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="cost" name={t("price.unitCost")} fill="#98a2b3" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="price" name={t("price.net")} fill="var(--accent)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty>{t("common.empty")}</Empty>
            )}
          </div>
        </Card>
        <Card className="min-w-0 xl:col-span-2">
          <CardHeader title={t("dash.activity")} />
          {!can("audit.read") ? (
            <Empty>{t("common.noPermission")}</Empty>
          ) : !audit.data?.length ? (
            <Empty>{t("common.empty")}</Empty>
          ) : (
            <ul className="divide-y divide-line">
              {audit.data.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm">
                  <span className="min-w-0 truncate">
                    <span className="font-medium">{a.action}</span> <span className="text-muted">{a.entity_type}</span>
                  </span>
                  <span className="shrink-0 text-xs whitespace-nowrap text-muted">{dateTime(a.created_at, lang)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {can("pricing.read") && (
        <Card className="mt-6">
          <CardHeader title={t("dash.recent")} />
          {recs.isLoading ? <Spinner /> : !recs.data?.data.length ? <Empty>{t("common.empty")}</Empty> : <RecommendationTable rows={recs.data.data.slice(0, 6)} />}
        </Card>
      )}
    </>
  );
}
