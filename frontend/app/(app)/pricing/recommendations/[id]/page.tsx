"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import { Alert, Badge, Card, CardHeader, PageHeader, Spinner, Stat, statusTone, Trace } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { date, dateTime, money, pct } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { Product, Recommendation } from "@/lib/types";

type Request = {
  discount?: string;
  target_margin?: string | null;
  markup?: string | null;
  fees?: { name: string; rate: string; base: string }[];
  turnover_tax_load?: string;
  rounding?: { increment: string; mode: string; apply_to: string; margin_guard: boolean } | null;
};

export default function RecommendationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, lang } = useI18n();
  const { orgId } = useOrg();
  const q = useQuery({ queryKey: ["recommendation", orgId, id], queryFn: () => api.get<Recommendation>(`/pricing/recommendations/${id}`) });
  const product = useQuery({
    queryKey: ["product", orgId, q.data?.product_id],
    queryFn: () => api.get<Product>(`/products/${q.data!.product_id}`),
    enabled: Boolean(q.data),
  });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <Alert>{errorText(q.error)}</Alert>;
  const r = q.data;
  const snap = r.calculation_snapshot;
  const req = ((r.input_snapshot as { request?: Request } | undefined)?.request ?? {}) as Request;

  const assumptions: [string, string][] = [
    [t("price.method"), t(`method.${r.pricing_method}`)],
    [t("price.unitCost"), money(snap?.unit_cost, r.currency, lang, true)],
  ];
  if (req.target_margin) assumptions.push([t("price.margin"), `${pct(req.target_margin, lang)} (${r.margin_definition})`]);
  if (req.markup) assumptions.push([t("price.markup"), pct(req.markup, lang)]);
  assumptions.push([t("price.discount"), pct(req.discount ?? "0", lang)]);
  for (const f of req.fees ?? []) assumptions.push([f.name, `${pct(f.rate, lang)} × ${t(`base.${f.base}`)}`]);
  if (req.turnover_tax_load && Number(req.turnover_tax_load) > 0) assumptions.push([t("price.taxLoad"), pct(req.turnover_tax_load, lang)]);
  if (req.rounding) assumptions.push([t("price.rounding"), `${req.rounding.mode} ${req.rounding.increment} · ${t(`base.${req.rounding.apply_to}`)}`]);

  return (
    <>
      <Link href="/pricing/recommendations" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> {t("rec.title")}
      </Link>
      <PageHeader
        title={product.data?.name ?? t("rec.detail")}
        description={`${t("price.effective")}: ${date(r.effective_date, lang)} · ${dateTime(r.created_at, lang)}`}
        action={<Badge tone={statusTone(r.status)}>{t(`status.${r.status}`)}</Badge>}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat tone="accent" label={t("price.list")} value={money(r.list_price, r.currency, lang)} />
        <Stat label={t("price.net")} value={money(r.recommended_price, r.currency, lang)} />
        <Stat label={t("price.minimum")} value={money(r.minimum_price, r.currency, lang)} />
        <Stat label={t("price.cm")} value={pct(r.expected_contribution_margin, lang)} sub={`${t("price.gm")}: ${pct(r.expected_gross_margin, lang)}`} />
      </div>
      {r.warnings.length > 0 && (
        <div className="mt-5 space-y-2">
          {r.warnings.map((w) => <Alert key={w.code} tone="warn" title={t(`warn.${w.code}`)}>{w.message}</Alert>)}
        </div>
      )}
      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card>
          <CardHeader title={t("rec.assumptions")} />
          <dl className="divide-y divide-line">
            {assumptions.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 px-5 py-2.5 text-sm">
                <dt className="text-muted">{k}</dt>
                <dd className="num text-right font-medium">{v}</dd>
              </div>
            ))}
            <div className="flex justify-between gap-4 px-5 py-2.5 text-sm">
              <dt className="text-muted">{t("rec.engine")}</dt>
              <dd className="font-mono text-xs">{r.engine_version}</dd>
            </div>
            <div className="flex justify-between gap-4 px-5 py-2.5 text-sm">
              <dt className="text-muted">{t("rec.hash")}</dt>
              <dd className="truncate font-mono text-xs" title={r.input_hash}>{r.input_hash.slice(0, 16)}…</dd>
            </div>
          </dl>
        </Card>
        <Card>
          <CardHeader title={t("cost.explain")} description={t("rec.snapshot")} />
          <div className="p-5">
            <Trace lines={[...(snap?.engine.price.trace ?? []), ...(snap?.engine.rounding?.trace ?? [])]} />
          </div>
        </Card>
      </div>
    </>
  );
}
