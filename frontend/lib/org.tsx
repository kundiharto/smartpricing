"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getOrgId, setOrgId } from "./api";
import type { Me, Organization } from "./types";

type Ctx = {
  me: Me | undefined;
  orgs: Organization[];
  org: Organization | undefined;
  orgId: string | null;
  switchOrg: (id: string) => void;
  can: (permission: string) => boolean;
  loading: boolean;
};

const OrgContext = createContext<Ctx | null>(null);

export function OrgProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [orgId, setOrgIdState] = useState<string | null>(null);

  const meQ = useQuery({ queryKey: ["me"], queryFn: () => api.get<Me>("/auth/me", { org: false }) });
  const orgsQ = useQuery({ queryKey: ["orgs"], queryFn: () => api.get<Organization[]>("/organizations", { org: false }) });

  useEffect(() => {
    if (!orgsQ.data) return;
    const saved = getOrgId();
    const valid = orgsQ.data.find((o) => o.id === saved) ?? orgsQ.data[0];
    const next = valid?.id ?? null;
    setOrgId(next);
    setOrgIdState(next);
  }, [orgsQ.data]);

  const orgQ = useQuery({
    queryKey: ["org", orgId],
    queryFn: () => api.get<Organization>(`/organizations/${orgId}`, { org: false }),
    enabled: Boolean(orgId),
  });

  const switchOrg = useCallback(
    (id: string) => {
      setOrgId(id);
      setOrgIdState(id);
      qc.removeQueries({ predicate: (q) => !["me", "orgs"].includes(String(q.queryKey[0])) });
    },
    [qc],
  );

  const can = useCallback((p: string) => Boolean(orgQ.data?.my_permissions.includes(p)), [orgQ.data]);

  return (
    <OrgContext.Provider
      value={{
        me: meQ.data,
        orgs: orgsQ.data ?? [],
        org: orgQ.data,
        orgId,
        switchOrg,
        can,
        loading: meQ.isLoading || orgsQ.isLoading || (Boolean(orgId) && orgQ.isLoading),
      }}
    >
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg(): Ctx {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrg must be used inside OrgProvider");
  return ctx;
}
