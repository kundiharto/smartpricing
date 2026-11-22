"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { Organization } from "@/lib/types";

export default function OrganizationSettingsPage() {
  const { t, lang } = useI18n();
  const { org, can } = useOrg();
  const qc = useQueryClient();
  const editable = can("org.manage");
  const [form, setForm] = useState({ name: "", default_currency: "IDR", default_language: "id", fiscal_year_start_month: 1, timezone: "Asia/Jakarta" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (org)
      setForm({
        name: org.name,
        default_currency: org.default_currency,
        default_language: org.default_language,
        fiscal_year_start_month: org.fiscal_year_start_month,
        timezone: org.timezone,
      });
  }, [org]);

  const save = useMutation({
    mutationFn: () => api.patch<Organization>(`/organizations/${org!.id}`, { row_version: org!.row_version, ...form }, { org: false }),
    onSuccess: () => {
      setSaved(true);
      qc.invalidateQueries({ queryKey: ["org"] });
      qc.invalidateQueries({ queryKey: ["orgs"] });
    },
  });
  if (!org) return null;

  const months = Array.from({ length: 12 }, (_, i) => new Intl.DateTimeFormat(lang === "id" ? "id-ID" : "en-US", { month: "long" }).format(new Date(2026, i, 1)));

  return (
    <>
      <PageHeader title={t("org.title")} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title={org.name} description={`${org.slug} · ${t("common.version")} ${org.row_version}`} />
          <form
            className="space-y-4 p-5"
            onSubmit={(e) => {
              e.preventDefault();
              setSaved(false);
              save.mutate();
            }}
          >
            {save.error && <Alert>{errorText(save.error)}</Alert>}
            {saved && <Alert tone="ok">{t("org.saved")}</Alert>}
            {!editable && <Alert tone="info">{t("common.noPermission")}</Alert>}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("common.name")} help="org.name" className="sm:col-span-2">
                {(id) => <Input id={id} value={form.name} disabled={!editable} required onChange={(e) => setForm({ ...form, name: e.target.value })} />}
              </Field>
              <Field label={t("onb.currency")} help="org.currency">
                {(id) => (
                  <Select id={id} value={form.default_currency} disabled={!editable} onChange={(e) => setForm({ ...form, default_currency: e.target.value })}>
                    {["IDR", "USD", "SGD", "MYR", "EUR"].map((c) => <option key={c}>{c}</option>)}
                  </Select>
                )}
              </Field>
              <Field label={t("onb.fiscal")} help="org.fiscal">
                {(id) => (
                  <Select id={id} value={form.fiscal_year_start_month} disabled={!editable} onChange={(e) => setForm({ ...form, fiscal_year_start_month: Number(e.target.value) })}>
                    {months.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
                  </Select>
                )}
              </Field>
              <Field label={t("org.language")} help="org.language">
                {(id) => (
                  <Select id={id} value={form.default_language} disabled={!editable} onChange={(e) => setForm({ ...form, default_language: e.target.value })}>
                    <option value="id">Bahasa Indonesia</option>
                    <option value="en">English</option>
                  </Select>
                )}
              </Field>
              <Field label={t("org.timezone")} help="org.timezone">
                {(id) => (
                  <Select id={id} value={form.timezone} disabled={!editable} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
                    {["Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "Asia/Singapore", "UTC"].map((z) => <option key={z}>{z}</option>)}
                  </Select>
                )}
              </Field>
            </div>
            {editable && (
              <div className="flex justify-end">
                <Button type="submit" loading={save.isPending}>{t("common.save")}</Button>
              </div>
            )}
          </form>
        </Card>
        <Card>
          <CardHeader title={t("onb.models")} />
          <div className="space-y-4 p-5 text-sm">
            <div className="flex flex-wrap gap-2">
              {org.business_models.map((m) => (
                <Badge key={m} tone={m === org.primary_business_model ? "accent" : "neutral"}>
                  {t(`bm.${m}`)}{m === org.primary_business_model ? ` · ${t("onb.primary")}` : ""}
                </Badge>
              ))}
              {org.is_hybrid && <Badge tone="ok">Hybrid</Badge>}
            </div>
            <div>
              <p className="mb-1.5 text-muted">{t("org.roles")}</p>
              <div className="flex flex-wrap gap-2">{org.my_roles.map((r) => <Badge key={r}>{r}</Badge>)}</div>
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}
