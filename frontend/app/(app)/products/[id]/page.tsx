"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { BomTab } from "@/components/product/bom-tab";
import { CostingTab } from "@/components/product/costing-tab";
import { GeneralTab } from "@/components/product/general-tab";
import { PricesTab } from "@/components/product/prices-tab";
import { ProductPricingTab } from "@/components/product/pricing-tab";
import { Alert, Badge, PageHeader, Spinner, statusTone, Tabs } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { Product } from "@/lib/types";

type Tab = "general" | "prices" | "bom" | "costing" | "pricing";

export default function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t } = useI18n();
  const { orgId, can } = useOrg();
  const [tab, setTab] = useState<Tab>("general");
  const q = useQuery({ queryKey: ["product", orgId, id], queryFn: () => api.get<Product>(`/products/${id}`) });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <Alert>{errorText(q.error)}</Alert>;
  const p = q.data;

  const tabs: { value: Tab; label: string }[] = [{ value: "general", label: t("prod.tab.general") }];
  if (p.product_type === "MATERIAL") tabs.push({ value: "prices", label: t("prod.tab.prices") });
  if (p.product_type === "FINISHED_GOOD") tabs.push({ value: "bom", label: t("prod.tab.bom") });
  if (p.product_type !== "MATERIAL" && can("costing.read")) tabs.push({ value: "costing", label: t("prod.tab.costing") });
  if (p.product_type !== "MATERIAL" && can("pricing.read")) tabs.push({ value: "pricing", label: t("prod.tab.pricing") });

  return (
    <>
      <Link href="/products" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> {t("prod.title")}
      </Link>
      <PageHeader
        title={p.name}
        description={`${p.sku} · ${t(`pt.${p.product_type}`)} · ${t(`bm.${p.business_model}`)}`}
        action={<Badge tone={statusTone(p.status)}>{t(`status.${p.status}`)}</Badge>}
      />
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "general" && <GeneralTab product={p} />}
      {tab === "prices" && <PricesTab product={p} />}
      {tab === "bom" && <BomTab product={p} />}
      {tab === "costing" && <CostingTab product={p} />}
      {tab === "pricing" && <ProductPricingTab product={p} />}
    </>
  );
}
