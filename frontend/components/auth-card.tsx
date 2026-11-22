"use client";

import { useI18n } from "@/lib/i18n";
import { cn } from "./ui";

export function AuthCard({ title, subtitle, children, wide }: { title: string; subtitle?: string; children: React.ReactNode; wide?: boolean }) {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className={cn("w-full", wide ? "max-w-xl" : "max-w-sm")}>
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">SP</div>
            <div className="leading-tight">
              <p className="text-sm font-semibold">{t("app.name")}</p>
              <p className="text-xs text-muted">{t("app.tagline")}</p>
            </div>
          </div>
          <div className="flex rounded-lg border border-line p-0.5 text-xs font-medium" role="group" aria-label="Language">
            {(["id", "en"] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLang(l)}
                aria-pressed={lang === l}
                className={cn("rounded-md px-2 py-1 uppercase", lang === l ? "bg-accent text-white" : "text-muted")}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
          <div className="mt-5">{children}</div>
        </div>
      </div>
    </div>
  );
}
