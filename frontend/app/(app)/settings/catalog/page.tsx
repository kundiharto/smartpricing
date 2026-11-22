"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Alert, Button, Card, CardHeader, Empty, Input, PageHeader, Select, Spinner, Table, Td, Th } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { byId, useCategories, useUnits } from "@/lib/queries";

const DIMENSIONS = ["COUNT", "MASS", "VOLUME", "LENGTH", "AREA", "TIME", "OTHER"];

export default function CatalogPage() {
  const { t } = useI18n();
  const { can } = useOrg();
  const qc = useQueryClient();
  const units = useUnits();
  const categories = useCategories();
  const catMap = byId(categories.data);
  const writable = can("products.write");
  const [unit, setUnit] = useState({ code: "", name: "", dimension: "COUNT" });
  const [cat, setCat] = useState({ name: "", parent_id: "" });

  const addUnit = useMutation({
    mutationFn: () => api.post("/units", unit),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["units"] });
      setUnit({ code: "", name: "", dimension: unit.dimension });
    },
  });
  const addCat = useMutation({
    mutationFn: () => api.post("/product-categories", { name: cat.name, parent_id: cat.parent_id || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["categories"] });
      setCat({ name: "", parent_id: "" });
    },
  });

  return (
    <>
      <PageHeader title={t("nav.catalog")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title={t("catalog.units")} />
          {writable && (
            <form onSubmit={(e) => { e.preventDefault(); addUnit.mutate(); }} className="grid grid-cols-[6rem_1fr_8rem_auto] gap-2 border-b border-line p-4">
              <Input aria-label={t("common.code")} placeholder="kg" required value={unit.code} onChange={(e) => setUnit({ ...unit, code: e.target.value })} />
              <Input aria-label={t("common.name")} placeholder={t("common.name")} required value={unit.name} onChange={(e) => setUnit({ ...unit, name: e.target.value })} />
              <Select aria-label={t("catalog.dimension")} value={unit.dimension} onChange={(e) => setUnit({ ...unit, dimension: e.target.value })}>
                {DIMENSIONS.map((d) => <option key={d}>{d}</option>)}
              </Select>
              <Button type="submit" loading={addUnit.isPending}>{t("common.add")}</Button>
              {addUnit.error && <div className="col-span-4"><Alert>{errorText(addUnit.error)}</Alert></div>}
            </form>
          )}
          {units.isLoading ? <Spinner /> : !units.data?.length ? <Empty>{t("common.empty")}</Empty> : (
            <Table>
              <thead><tr><Th>{t("common.code")}</Th><Th>{t("common.name")}</Th><Th>{t("catalog.dimension")}</Th></tr></thead>
              <tbody>
                {units.data.map((u) => (
                  <tr key={u.id}><Td className="font-mono text-xs">{u.code}</Td><Td>{u.name}</Td><Td className="text-muted">{u.dimension}</Td></tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader title={t("catalog.categories")} />
          {writable && (
            <form onSubmit={(e) => { e.preventDefault(); addCat.mutate(); }} className="grid grid-cols-[1fr_10rem_auto] gap-2 border-b border-line p-4">
              <Input aria-label={t("common.name")} placeholder={t("common.name")} required value={cat.name} onChange={(e) => setCat({ ...cat, name: e.target.value })} />
              <Select aria-label={t("catalog.parent")} value={cat.parent_id} onChange={(e) => setCat({ ...cat, parent_id: e.target.value })}>
                <option value="">{t("catalog.parent")}: —</option>
                {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
              <Button type="submit" loading={addCat.isPending}>{t("common.add")}</Button>
              {addCat.error && <div className="col-span-3"><Alert>{errorText(addCat.error)}</Alert></div>}
            </form>
          )}
          {categories.isLoading ? <Spinner /> : !categories.data?.length ? <Empty>{t("common.empty")}</Empty> : (
            <Table>
              <thead><tr><Th>{t("common.name")}</Th><Th>{t("catalog.parent")}</Th></tr></thead>
              <tbody>
                {categories.data.map((c) => (
                  <tr key={c.id}><Td>{c.name}</Td><Td className="text-muted">{c.parent_id ? catMap[c.parent_id]?.name : "—"}</Td></tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>
    </>
  );
}
