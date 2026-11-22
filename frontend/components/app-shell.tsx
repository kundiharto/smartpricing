"use client";

import {
  Building2,
  Calculator,
  ChevronDown,
  FileClock,
  LayoutDashboard,
  LineChart,
  ListChecks,
  LogOut,
  Menu,
  Package,
  Ruler,
  Users,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { logout } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useOrg } from "@/lib/org";
import { cn, Spinner } from "./ui";

type NavItem = { href: string; label: string; icon: React.ComponentType<{ className?: string }>; permission?: string };

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, lang, setLang } = useI18n();
  const { me, orgs, org, orgId, switchOrg, can, loading } = useOrg();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMobileOpen(false), [pathname]);
  useEffect(() => {
    if (!loading && orgs.length === 0 && me) router.replace("/onboarding");
  }, [loading, orgs.length, me, router]);

  const groups: { title?: string; items: NavItem[] }[] = [
    {
      items: [
        { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard },
        { href: "/products", label: t("nav.products"), icon: Package, permission: "products.read" },
        { href: "/costs", label: t("nav.costs"), icon: Wallet, permission: "costs.read" },
      ],
    },
    {
      title: t("nav.planning"),
      items: [
        { href: "/planning", label: t("nav.scenarios"), icon: LineChart, permission: "planning.read" },
      ],
    },
    {
      title: t("nav.pricing"),
      items: [
        { href: "/pricing/calculator", label: t("nav.calculator"), icon: Calculator, permission: "pricing.calculate" },
        { href: "/pricing/recommendations", label: t("nav.recommendations"), icon: ListChecks, permission: "pricing.read" },
      ],
    },
    {
      title: t("nav.settings"),
      items: [
        { href: "/settings/organization", label: t("nav.organization"), icon: Building2, permission: "org.read" },
        { href: "/settings/users", label: t("nav.users"), icon: Users, permission: "org.read" },
        { href: "/settings/catalog", label: t("nav.catalog"), icon: Ruler, permission: "products.read" },
        { href: "/settings/audit-logs", label: t("nav.audit"), icon: FileClock, permission: "audit.read" },
      ],
    },
  ];

  const nav = (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4" aria-label="Main">
      {groups.map((g, gi) => {
        const items = g.items.filter((i) => !i.permission || can(i.permission));
        if (!items.length) return null;
        return (
          <div key={gi}>
            {g.title && <p className="px-3 pb-1.5 text-xs font-medium tracking-wide text-muted uppercase">{g.title}</p>}
            <ul className="space-y-0.5">
              {items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                        active ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-2 hover:text-ink",
                      )}
                    >
                      <Icon className="size-4 shrink-0" />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );

  const brand = (
    <div className="flex h-16 items-center gap-2.5 border-b border-line px-5">
      <div className="flex size-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">SP</div>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-ink">Smart Pricing</p>
        <p className="text-xs text-muted">Engine</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-line bg-surface lg:flex">
        {brand}
        {nav}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-surface shadow-xl">
            <div className="flex items-center justify-between pr-3">
              {brand}
              <button type="button" onClick={() => setMobileOpen(false)} className="rounded-md p-2 text-muted" aria-label="Close menu">
                <X className="size-5" />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}

      <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur lg:px-8">
        <button type="button" onClick={() => setMobileOpen(true)} className="rounded-md p-2 text-muted lg:hidden" aria-label="Open menu">
          <Menu className="size-5" />
        </button>

        <div className="relative min-w-0">
          <label htmlFor="org-switch" className="sr-only">
            {t("nav.organization")}
          </label>
          <select
            id="org-switch"
            value={orgId ?? ""}
            onChange={(e) => switchOrg(e.target.value)}
            className="h-9 max-w-[52vw] appearance-none truncate rounded-lg border border-line bg-surface py-0 pr-8 pl-3 text-sm font-medium text-ink sm:max-w-xs"
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute top-2.5 right-2.5 size-4 text-muted" />
        </div>
        <Link href="/onboarding" className="hidden text-sm text-muted hover:text-ink sm:inline">
          + {t("nav.organization")}
        </Link>

        <div className="ml-auto flex items-center gap-2">
          <div className="flex rounded-lg border border-line p-0.5 text-xs font-medium" role="group" aria-label="Language">
            {(["id", "en"] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLang(l)}
                aria-pressed={lang === l}
                className={cn("rounded-md px-2 py-1 uppercase", lang === l ? "bg-accent text-white" : "text-muted hover:text-ink")}
              >
                {l}
              </button>
            ))}
          </div>
          <div className="hidden text-right leading-tight md:block">
            <p className="text-sm font-medium text-ink">{me?.user.full_name}</p>
            <p className="text-xs text-muted">{org?.my_roles.join(", ")}</p>
          </div>
          <button
            type="button"
            onClick={() => logout()}
            className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-ink"
            title={t("nav.logout")}
            aria-label={t("nav.logout")}
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8 lg:py-8">{loading || !org ? <Spinner label={t("common.loading")} /> : children}</main>
    </div>
  );
}
