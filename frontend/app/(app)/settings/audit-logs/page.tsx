"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Badge, Button, Card, Empty, PageHeader, Select, Spinner, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { AuditLog, Member } from "@/lib/types";

const PAGE = 30;
const ENTITIES = ["organization", "organization_member", "product", "unit", "product_category", "material_price", "bom", "costing_version", "pricing_recommendation"];

export default function AuditLogsPage() {
  const { t, lang } = useI18n();
  const { org, orgId } = useOrg();
  const [entity, setEntity] = useState("");
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["audit", orgId, entity, offset],
    queryFn: () => api.page<AuditLog[]>("/audit-logs", { query: { entity_type: entity, limit: PAGE, offset } }),
    placeholderData: keepPreviousData,
  });
  const members = useQuery({ queryKey: ["members", org?.id], queryFn: () => api.get<Member[]>(`/organizations/${org!.id}/members`, { org: false }), enabled: Boolean(org) });
  const names = Object.fromEntries((members.data ?? []).map((m) => [m.user_id, m.full_name]));
  const total = q.data?.meta.total ?? 0;

  return (
    <>
      <PageHeader title={t("audit.title")} />
      <Card>
        <div className="border-b border-line p-4">
          <Select aria-label={t("audit.entity")} value={entity} onChange={(e) => { setEntity(e.target.value); setOffset(0); }} className="max-w-xs">
            <option value="">{t("audit.entity")}: {t("common.all")}</option>
            {ENTITIES.map((e) => <option key={e} value={e}>{e}</option>)}
          </Select>
        </div>
        {q.isLoading ? <Spinner /> : !q.data?.data.length ? <Empty>{t("common.empty")}</Empty> : (
          <Table>
            <thead>
              <tr>
                <Th>{t("common.date")}</Th>
                <Th>{t("auth.fullName")}</Th>
                <Th>{t("audit.action")}</Th>
                <Th>{t("audit.entity")}</Th>
                <Th>{t("audit.changes")}</Th>
              </tr>
            </thead>
            <tbody>
              {q.data.data.map((a) => (
                <Fragment key={a.id}>
                  <tr className="hover:bg-surface-2">
                    <Td className="whitespace-nowrap text-muted">{dateTime(a.created_at, lang)}</Td>
                    <Td>{a.user_id ? names[a.user_id] ?? "…" : "—"}</Td>
                    <Td><Badge tone="accent">{a.action}</Badge></Td>
                    <Td className="font-mono text-xs">{a.entity_type}</Td>
                    <Td>
                      <Button size="sm" variant="ghost" onClick={() => setExpanded(expanded === a.id ? null : a.id)} aria-expanded={expanded === a.id}>
                        {expanded === a.id ? t("common.close") : t("audit.changes")}
                      </Button>
                    </Td>
                  </tr>
                  {expanded === a.id && (
                    <tr>
                      <td colSpan={5} className="border-b border-line bg-surface-2 px-4 py-3">
                        <div className="grid gap-3 md:grid-cols-2">
                          {(["old_values", "new_values"] as const).map((k) => (
                            <div key={k}>
                              <p className="mb-1 text-xs font-medium text-muted uppercase">{k === "old_values" ? t("audit.before") : t("audit.after")}</p>
                              <pre className="overflow-x-auto rounded-lg bg-surface p-3 text-xs ring-1 ring-line">{a[k] ? JSON.stringify(a[k], null, 2) : "—"}</pre>
                            </div>
                          ))}
                        </div>
                        <p className="mt-2 font-mono text-xs text-muted">request_id: {a.request_id ?? "—"}</p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </Table>
        )}
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
