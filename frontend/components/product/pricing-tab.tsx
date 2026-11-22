"use client";

import { useQuery } from "@tanstack/react-query";
import { Calculator } from "lucide-react";
import Link from "next/link";
import { RecommendationTable } from "@/components/recommendation-table";
import { Card, CardHeader, Empty, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { Product, Recommendation } from "@/lib/types";

export function ProductPricingTab({ product }: { product: Product }) {
  const { t } = useI18n();
  const { orgId, can } = useOrg();
  const q = useQuery({
    queryKey: ["recommendations", orgId, product.id],
    queryFn: () => api.get<Recommendation[]>("/pricing/recommendations", { query: { product_id: product.id, limit: 50 } }),
  });
  return (
    <Card>
      <CardHeader
        title={t("rec.title")}
        action={
          can("pricing.calculate") && (
            <Link
              href={`/pricing/calculator?product=${product.id}`}
              className="inline-flex h-8 items-center gap-2 rounded-lg bg-accent px-3 text-sm font-medium text-white hover:bg-accent-hover"
            >
              <Calculator className="size-4" /> {t("nav.calculator")}
            </Link>
          )
        }
      />
      {q.isLoading ? <Spinner /> : !q.data?.length ? <Empty>{t("common.empty")}</Empty> : <RecommendationTable rows={q.data} hideProduct />}
    </Card>
  );
}
