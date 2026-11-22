"use client";

import { money, num, pct } from "./format";
import type { Lang } from "./format";
import type { CostItem } from "./types";

/** Ringkasan parameter biaya dalam satu baris, untuk tabel. */
export function describeCost(item: CostItem, t: (k: string) => string, lang: Lang, currency: string): string {
  const v = item.current_version;
  if (!v) return "—";
  const per = t(`period.${item.period_months}`);
  const drv = item.driver ? (item.driver.unit_label || item.driver.name) : "";
  switch (item.behavior_type) {
    case "FIXED":
      return `${money(v.base_amount, currency, lang)} ${per}`;
    case "VARIABLE":
      return `${money(v.rate, currency, lang, true)} / ${drv}`;
    case "SEMI_VARIABLE":
      return `${money(v.base_amount, currency, lang)} ${per} + ${money(v.rate, currency, lang, true)} / ${drv}`;
    case "PERCENTAGE":
      return `${pct(v.percentage, lang)} × ${v.percentage_base === "COGS" ? t("costs.cogs") : t("costs.revenue")}`;
    case "STEP_FIXED":
      if (v.step_mode === "CEILING")
        return `${money(v.cost_per_resource, currency, lang)} ${per} / ${num(v.capacity_per_resource, lang)} ${drv}`;
      return (v.tiers ?? []).map((x) => `${num(x.from_activity, lang)}–${num(x.to_activity, lang)}: ${money(x.amount, currency, lang)}`).join(" · ");
  }
}
