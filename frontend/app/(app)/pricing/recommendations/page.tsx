"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { RecommendationTable } from "@/components/recommendation-table";
import { Button, Card, Empty, PageHeader, Select, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { useAllProducts } from "@/lib/queries";
import type { Recommendation } from "@/lib/types";

const PAGE = 25;

export default function RecommendationsPage() {
  const { t } = useI18n();
  const { orgId } = useOrg();
  const [productId, setProductId] = useState("");
  const [offset, setOffset] = useState(0);
  const products = useAllProducts();
  const q = useQuery({
    queryKey: ["recommendations", orgId, "list", productId, offset],
    queryFn: () => api.page<Recommendation[]>("/pricing/recommendations", { query: { product_id: productId, limit: PAGE, offset } }),
    placeholderData: keepPreviousData,
  });
  const total = q.data?.meta.total ?? 0;

  return (
    <>
      <PageHeader title={t("rec.title")} />
      <Card>
        <div className="border-b border-line p-4">
          <Select aria-label={t("nav.products")} value={productId} onChange={(e) => { setProductId(e.target.value); setOffset(0); }} className="max-w-sm">
            <option value="">{t("nav.products")}: {t("common.all")}</option>
            {products.data?.filter((p) => p.product_type !== "MATERIAL").map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        </div>
        {q.isLoading ? <Spinner /> : !q.data?.data.length ? <Empty>{t("common.empty")}</Empty> : <RecommendationTable rows={q.data.data} />}
        {total > PAGE && (
          <div className="flex items-center justify-between px-4 py-3 text-sm text-muted">
            <span className="num">{offset + 1}–{Math.min(offset + PAGE, total)} {t("common.of")} {total}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>{t("common.prev")}</Button>
              <Button size="sm" variant="secondary" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>{t("common.next")}</Button>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
