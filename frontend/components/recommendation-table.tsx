"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { byId, useAllProducts } from "@/lib/queries";
import { date, money, pct } from "@/lib/format";
import type { Recommendation } from "@/lib/types";
import { Badge, statusTone, Table, Td, Th } from "./ui";

export function RecommendationTable({ rows, hideProduct }: { rows: Recommendation[]; hideProduct?: boolean }) {
  const { t, lang } = useI18n();
  const products = byId(useAllProducts().data);
  return (
    <Table>
      <thead>
        <tr>
          <Th>{t("common.date")}</Th>
          {!hideProduct && <Th>{t("nav.products")}</Th>}
          <Th>{t("price.method")}</Th>
          <Th align="right">{t("price.list")}</Th>
          <Th align="right">{t("price.net")}</Th>
          <Th align="right">{t("price.cm")}</Th>
          <Th>{t("common.status")}</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="hover:bg-surface-2">
            <Td>
              <Link href={`/pricing/recommendations/${r.id}`} className="font-medium text-ink hover:text-accent hover:underline">
                {date(r.effective_date, lang)}
              </Link>
            </Td>
            {!hideProduct && <Td>{products[r.product_id]?.name ?? "…"}</Td>}
            <Td className="text-muted">{t(`method.${r.pricing_method}`)}</Td>
            <Td align="right" className="font-medium">{money(r.list_price, r.currency, lang)}</Td>
            <Td align="right">{money(r.recommended_price, r.currency, lang)}</Td>
            <Td align="right">{pct(r.expected_contribution_margin, lang)}</Td>
            <Td>
              <div className="flex items-center gap-1.5">
                <Badge tone={statusTone(r.status)}>{t(`status.${r.status}`)}</Badge>
                {r.warnings.length > 0 && <AlertTriangle className="size-4 text-warn" aria-label={r.warnings.map((w) => w.code).join(", ")} />}
              </div>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
