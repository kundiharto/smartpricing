"use client";

import { useState } from "react";
import { AuthCard } from "@/components/auth-card";
import { Alert, Button, cn, Field, Input, LegendWithHelp, Select } from "@/components/ui";
import { api, errorText, setOrgId } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Organization } from "@/lib/types";

const MODELS = ["MANUFACTURING", "TRADING", "DISTRIBUTION", "RETAIL", "SERVICES"] as const;

function slugify(s: string) {
  return s
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

export default function OnboardingPage() {
  const { t, lang } = useI18n();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [currency, setCurrency] = useState("IDR");
  const [fiscal, setFiscal] = useState("1");
  const [models, setModels] = useState<string[]>(["MANUFACTURING"]);
  const [primary, setPrimary] = useState("MANUFACTURING");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function toggle(m: string) {
    setModels((cur) => {
      const next = cur.includes(m) ? cur.filter((x) => x !== m) : [...cur, m];
      if (!next.includes(primary)) setPrimary(next[0] ?? "");
      return next;
    });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const org = await api.post<Organization>(
        "/organizations",
        {
          name,
          slug,
          default_currency: currency,
          default_language: lang,
          fiscal_year_start_month: Number(fiscal),
          business_models: models,
          primary_business_model: primary,
        },
        { org: false },
      );
      setOrgId(org.id);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  const months = Array.from({ length: 12 }, (_, i) =>
    new Intl.DateTimeFormat(lang === "id" ? "id-ID" : "en-US", { month: "long" }).format(new Date(2026, i, 1)),
  );

  return (
    <AuthCard title={t("onb.title")} subtitle={t("onb.subtitle")} wide>
      <form onSubmit={submit} className="space-y-5">
        {error && <Alert>{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("common.name")} help="org.name" className="sm:col-span-2">
            {(id) => (
              <Input
                id={id}
                required
                value={name}
                placeholder="PT Maju Bersama"
                onChange={(e) => {
                  setName(e.target.value);
                  if (!slugTouched) setSlug(slugify(e.target.value));
                }}
              />
            )}
          </Field>
          <Field label={t("onb.slug")} help="org.slug" className="sm:col-span-2">
            {(id) => (
              <Input
                id={id}
                required
                pattern="[a-z0-9]([a-z0-9\-]{0,62}[a-z0-9])?"
                value={slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setSlug(e.target.value.toLowerCase());
                }}
              />
            )}
          </Field>
          <Field label={t("onb.currency")} help="org.currency">
            {(id) => (
              <Select id={id} value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {["IDR", "USD", "SGD", "MYR", "EUR"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t("onb.fiscal")} help="org.fiscal">
            {(id) => (
              <Select id={id} value={fiscal} onChange={(e) => setFiscal(e.target.value)}>
                {months.map((m, i) => (
                  <option key={m} value={i + 1}>
                    {m}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        <fieldset>
          <legend><LegendWithHelp label={t("onb.models")} help="org.models" /></legend>
          <p className="mb-2 text-xs text-muted">{t("onb.hybridHint")}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {MODELS.map((m) => {
              const on = models.includes(m);
              return (
                <div key={m} className={cn("flex items-center justify-between rounded-lg border px-3 py-2.5", on ? "border-accent bg-accent-soft" : "border-line")}>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={on} onChange={() => toggle(m)} className="accent-[var(--accent)]" />
                    {t(`bm.${m}`)}
                  </label>
                  {on && models.length > 1 && (
                    <label className="flex items-center gap-1 text-xs text-muted">
                      <input type="radio" name="primary" checked={primary === m} onChange={() => setPrimary(m)} className="accent-[var(--accent)]" />
                      {t("onb.primary")}
                    </label>
                  )}
                </div>
              );
            })}
          </div>
        </fieldset>

        <Button type="submit" className="w-full" loading={busy} disabled={!models.length}>
          {t("onb.create")}
        </Button>
      </form>
    </AuthCard>
  );
}
