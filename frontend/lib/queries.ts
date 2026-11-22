"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useOrg } from "./org";
import type { Category, Product, Unit } from "./types";

export function useUnits() {
  const { orgId } = useOrg();
  return useQuery({ queryKey: ["units", orgId], queryFn: () => api.get<Unit[]>("/units"), enabled: Boolean(orgId) });
}

export function useCategories() {
  const { orgId } = useOrg();
  return useQuery({ queryKey: ["categories", orgId], queryFn: () => api.get<Category[]>("/product-categories"), enabled: Boolean(orgId) });
}

/** Semua produk non-arsip (maks. 200) untuk pilihan & pemetaan nama. */
export function useAllProducts(productType?: string) {
  const { orgId } = useOrg();
  return useQuery({
    queryKey: ["products-all", orgId, productType],
    queryFn: () => api.get<Product[]>("/products", { query: { limit: 200, sort: "name", product_type: productType } }),
    enabled: Boolean(orgId),
  });
}

export function byId<T extends { id: string }>(rows: T[] | undefined): Record<string, T> {
  return Object.fromEntries((rows ?? []).map((r) => [r.id, r]));
}
