"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus } from "lucide-react";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Dialog, Empty, Field, Input, PageHeader, Spinner, statusTone, Table, Td, Th } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import type { Member } from "@/lib/types";

const ROLES = ["OWNER", "DIRECTOR", "FINANCE_MANAGER", "FINANCIAL_ANALYST", "OPERATIONS_MANAGER", "SALES_MANAGER", "VIEWER"];

export default function UsersPage() {
  const { t } = useI18n();
  const { org, can } = useOrg();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [roles, setRoles] = useState<string[]>(["VIEWER"]);

  const q = useQuery({ queryKey: ["members", org?.id], queryFn: () => api.get<Member[]>(`/organizations/${org!.id}/members`, { org: false }), enabled: Boolean(org) });
  const add = useMutation({
    mutationFn: () => api.post(`/organizations/${org!.id}/members`, { email, role_codes: roles }, { org: false }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members"] });
      setOpen(false);
      setEmail("");
      setRoles(["VIEWER"]);
    },
  });
  const assignable = org?.my_roles.includes("OWNER") ? ROLES : ROLES.filter((r) => r !== "OWNER");

  return (
    <>
      <PageHeader
        title={t("users.title")}
        action={can("members.manage") && <Button onClick={() => setOpen(true)}><UserPlus className="size-4" /> {t("users.add")}</Button>}
      />
      <Card>
        <CardHeader title={org?.name ?? ""} />
        {q.isLoading ? (
          <Spinner />
        ) : !q.data?.length ? (
          <Empty>{t("common.empty")}</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>{t("common.name")}</Th>
                <Th>{t("auth.email")}</Th>
                <Th>{t("users.roles")}</Th>
                <Th>{t("common.status")}</Th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((m) => (
                <tr key={m.member_id}>
                  <Td className="font-medium">{m.full_name}</Td>
                  <Td className="text-muted">{m.email}</Td>
                  <Td><div className="flex flex-wrap gap-1">{m.roles.map((r) => <Badge key={r} tone={r === "OWNER" ? "accent" : "neutral"}>{r}</Badge>)}</div></Td>
                  <Td><Badge tone={statusTone(m.status)}>{t(`status.${m.status}`)}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Dialog open={open} onClose={() => setOpen(false)} title={t("users.add")}>
        <form onSubmit={(e) => { e.preventDefault(); add.mutate(); }} className="space-y-4">
          {add.error && <Alert>{errorText(add.error)}</Alert>}
          <Alert tone="info">{t("users.addHint")}</Alert>
          <Field label={t("auth.email")}>{(id) => <Input id={id} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          <fieldset>
            <legend className="mb-2 text-sm font-medium">{t("users.roles")}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {assignable.map((r) => (
                <label key={r} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={roles.includes(r)}
                    onChange={() => setRoles(roles.includes(r) ? roles.filter((x) => x !== r) : [...roles, r])}
                    className="accent-[var(--accent)]"
                  />
                  {r}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button type="submit" loading={add.isPending} disabled={!roles.length}>{t("common.save")}</Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
