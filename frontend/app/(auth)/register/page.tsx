"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/auth-card";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api, errorText, login } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function RegisterPage() {
  const { t, lang } = useI18n();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/register", { ...form, preferred_language: lang }, { org: false });
      await login(form.email, form.password);
      window.location.href = "/onboarding";
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <AuthCard title={t("auth.register")} subtitle={t("auth.createTitle")}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field label={t("auth.fullName")}>
          {(id) => <Input id={id} required autoComplete="name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}
        </Field>
        <Field label={t("auth.email")}>
          {(id) => <Input id={id} type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
        </Field>
        <Field label={t("auth.password")} hint={t("auth.passwordHint")}>
          {(id) => (
            <Input
              id={id}
              type="password"
              required
              minLength={10}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          )}
        </Field>
        <Button type="submit" className="w-full" loading={busy}>
          {t("auth.register")}
        </Button>
        <p className="text-center text-sm text-muted">
          {t("auth.haveAccount")}{" "}
          <Link href="/login" className="font-medium text-accent hover:underline">
            {t("auth.login")}
          </Link>
        </p>
      </form>
    </AuthCard>
  );
}
