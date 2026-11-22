"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompare, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Badge, Button, Card, Dialog, Empty, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { date, money, num } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { Scenario } from "@/lib/types";

const TYPES = ["BASE", "OPTIMISTIC", "PESSIMISTIC", "CUSTOM"] as const;
const tone = (t: string) => (t === "BASE" ? "accent" : t === "OPTIMISTIC" ? "ok" : t === "PESSIMISTIC" ? "danger" : "neutral");

function firstOfNextMonth() {
  const d = new Date();
  const n = new Date(d.getFullYear(), d.getMonth() + 1, 1);
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function PlanningPage() {
  const { t, lang } = useI18n();
  const { orgId, org, can } = useOrg();
  const qc = useQueryClient();
  const router = useRouter();
  const currency = org?.default_currency ?? "IDR";
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", scenario_type: "BASE", period_start: firstOfNextMonth(), period_months: "1" });
  const q = useQuery({ queryKey: ["scenarios", orgId], queryFn: () => api.get<Scenario[]>("/scenarios") });
  const create = useMutation({
    mutationFn: () => api.post<Scenario>("/scenarios", { ...form, period_months: Number(form.period_months) }),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["scenarios"] });
      router.push(`/planning/${s.id}`);
    },
  });

  return (
    <>
      <PageHeader
        title={t("plan.title")}
        description={t("plan.subtitle")}
        action={
          <div className="flex gap-2">
            {(q.data?.length ?? 0) >= 2 && (
              <Link href="/planning/compare" className="inline-flex h-10 items-center gap-2 rounded-lg border border-line bg-surface px-4 text-sm font-medium hover:bg-surface-2">
                <GitCompare className="size-4" /> {t("nav.compare")}
              </Link>
            )}
            {can("planning.write") && <Button onClick={() => setOpen(true)}><Plus className="size-4" /> {t("plan.new")}</Button>}
          </div>
        }
      />
      {q.isLoading ? (
        <Spinner />
      ) : !q.data?.length ? (
        <Card><Empty>{t("plan.empty")}</Empty></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[...q.data].sort((a, b) => Number(b.scenario_type === "BASE") - Number(a.scenario_type === "BASE") || a.name.localeCompare(b.name)).map((s) => {
            const r = s.latest_run;
            return (
              <Link key={s.id} href={`/planning/${s.id}`} className="block rounded-xl border border-line bg-surface p-5 transition-colors hover:border-accent/50">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{s.name}</p>
                    <p className="text-sm text-muted">{date(s.period_start, lang)} · {s.period_months} {t("plan.monthsShort")} · {s.lines.length} {t("nav.products").toLowerCase()}</p>
                  </div>
                  <Badge tone={tone(s.scenario_type)}>{t(`stype.${s.scenario_type}`)}</Badge>
                </div>
                {r ? (
                  <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div><dt className="text-muted">{t("plan.revenue")}</dt><dd className="num font-medium">{money(r.revenue, currency, lang)}</dd></div>
                    <div><dt className="text-muted">{t("plan.operating")}</dt><dd className={`num font-medium ${Number(r.operating_profit) < 0 ? "text-danger" : "text-ok"}`}>{money(r.operating_profit, currency, lang)}</dd></div>
                    <div><dt className="text-muted">{t("plan.bepUnits")}</dt><dd className="num font-medium">{num(r.break_even_units, lang, 0)}</dd></div>
                    <div><dt className="text-muted">{t("plan.lastRun")}</dt><dd className="text-xs text-muted">{date(r.created_at, lang)}</dd></div>
                  </dl>
                ) : (
                  <p className="mt-4 text-sm text-muted">{t("plan.noRun")}</p>
                )}
              </Link>
            );
          })}
        </div>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title={t("plan.new")}>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          {create.error && <Alert>{errorText(create.error)}</Alert>}
          <Field label={t("common.name")} help="plan.name">{(id) => <Input id={id} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}</Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t("plan.type")} help="plan.type">
              {(id) => (
                <Select id={id} value={form.scenario_type} onChange={(e) => setForm({ ...form, scenario_type: e.target.value })}>
                  {TYPES.map((x) => <option key={x} value={x}>{t(`stype.${x}`)}</option>)}
                </Select>
              )}
            </Field>
            <Field label={t("plan.start")} help="plan.start">{(id) => <Input id={id} type="date" required value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} />}</Field>
            <Field label={t("plan.months")} help="plan.months">
              {(id) => (
                <Select id={id} value={form.period_months} onChange={(e) => setForm({ ...form, period_months: e.target.value })}>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{m}</option>)}
                </Select>
              )}
            </Field>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button type="submit" loading={create.isPending}>{t("common.save")}</Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
