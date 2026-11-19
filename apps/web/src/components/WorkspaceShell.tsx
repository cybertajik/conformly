import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowDownToLine, ArrowRight, Building2, Check, ChevronDown, Command, Flag, FolderCheck, Globe2, LayoutDashboard, Layers3, ListChecks, LogOut, Menu, Search, Server, Shield, Sparkles, Users, X, type LucideIcon } from "lucide-react";
import type { TenantMembershipSummary } from "@conformly/shared";
import type { Tab } from "../App";
import { workspaceCopy } from "../i18n/workspaceCopy";
import { LanguageSelector } from "./LanguageSelector";
import { useTranslation } from "../i18n/I18nContext";

export interface NavigationItem { id: Tab; label: string }
const icons: Partial<Record<Tab, LucideIcon>> = { overview: LayoutDashboard, onboarding: ListChecks, organization: Building2, frameworks: Layers3, compliance: FolderCheck, risks: Flag, assets: Server, vendors: Building2, preaudit: Shield, public_profile: Globe2, lifecycle: ArrowDownToLine, members: Users };
const groups: { label: string; ids: Tab[] }[] = [
  { label: "Workspace", ids: ["overview", "onboarding"] },
  { label: "Compliance", ids: ["frameworks", "compliance", "risks", "assets", "vendors", "preaudit", "public_profile"] },
  { label: "Administration", ids: ["organization", "members", "lifecycle"] },
];

export function Brand() { return <span className="identity"><span className="identity-symbol"><Shield size={22} strokeWidth={1.8}/><Check size={11}/></span><span>conformly<span className="identity-dot">.</span></span></span>; }

export function WorkspaceShell({ children, items, tab, navigate, tenants, selected, chooseTenant, signOut }: {
  children: ReactNode; items: NavigationItem[]; tab: Tab; navigate: (tab: Tab) => void;
  tenants: TenantMembershipSummary[]; selected: TenantMembershipSummary;
  chooseTenant: (id: string) => void; signOut: () => void;
}) {
  const { t, locale } = useTranslation();
  const copy = workspaceCopy[locale];
  const [mobileOpen, setMobileOpen] = useState(false);
  const [query, setQuery] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const rail = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!mobileOpen) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    rail.current?.querySelector<HTMLButtonElement>(".mobile-close")?.focus();
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || dialog.current?.open) return;
      const controls = Array.from(rail.current?.querySelectorAll<HTMLElement>("button:not(:disabled), select") ?? []).filter(element => element.getClientRects().length);
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", trapFocus);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener("keydown", trapFocus); previousFocus?.focus(); };
  }, [mobileOpen]);
  const title = items.find(item => item.id === tab)?.label ?? copy.workspace;
  const openSearch = () => { setQuery(""); dialog.current?.showModal(); search.current?.focus(); };
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "k") { event.preventDefault(); openSearch(); }
      if (event.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);
  const go = (next: Tab) => { if (!items.some(item => item.id === next)) return; navigate(next); setMobileOpen(false); dialog.current?.close(); };
  const filtered = items.filter(item => item.label.toLowerCase().includes(query.toLowerCase()));
  return <div className="workspace-shell">
    <a href="#main-content" className="skip-to-content">{copy.skip}</a>
    {mobileOpen && <button className="navigation-scrim" aria-label={copy.closeNav} onClick={() => setMobileOpen(false)}/>}
    <aside ref={rail} className={`navigation-rail ${mobileOpen ? "is-open" : ""}`} aria-label="Sidebar">
      <div className="rail-brand"><Brand/><button className="mobile-close icon-button" aria-label={copy.closeNav} onClick={() => setMobileOpen(false)}><X size={19}/></button></div>
      <div className="workspace-picker"><span className="workspace-avatar">{selected.tenant_name.slice(0, 2).toUpperCase()}</span><div><label htmlFor="tenant-selector">{t("nav.organizationLabel")}</label><select id="tenant-selector" value={selected.tenant_id} onChange={event => chooseTenant(event.target.value)}>{tenants.map(tenant => <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.tenant_name}</option>)}</select></div><ChevronDown size={14}/></div>
      <button className="rail-search" onClick={openSearch}><Search size={16}/><span>{copy.quick}</span><kbd>⌘ K</kbd></button>
      <nav aria-label="Primary navigation" className="rail-navigation">{groups.map(group => <div className="navigation-group" key={group.label}><p>{group.label === "Workspace" ? copy.workspace : group.label === "Administration" ? copy.administration : t("nav.compliance")}</p>{group.ids.map(id => items.find(item => item.id === id)).filter((item): item is NavigationItem => Boolean(item)).map(item => { const Icon = icons[item.id] ?? Layers3; return <button key={item.id} aria-current={tab === item.id ? "page" : undefined} className={`navigation-link ${tab === item.id ? "is-active" : ""}`} onClick={() => go(item.id)}><Icon size={18}/><span>{item.label}</span>{tab === item.id && <span className="active-dot"/>}</button>; })}</div>)}</nav>
      <div className="rail-bottom"><button className="setup-shortcut" onClick={() => go("onboarding")}><Sparkles size={18}/><span>{copy.setupTitle}<small>{copy.setupDetail}</small></span><ArrowRight size={15}/></button><div className="rail-account"><span className="account-avatar">{selected.tenant_name.charAt(0)}</span><span className="account-detail"><strong>{selected.tenant_name}</strong><small>{selected.role.replaceAll("_", " ")}</small></span><button className="icon-button" aria-label={t("nav.signOut")} title={t("nav.signOut")} onClick={signOut}><LogOut size={17}/></button></div></div>
    </aside>
    <div className="workspace-body" inert={mobileOpen}><header className="workspace-topbar"><div className="breadcrumb"><button className="mobile-menu icon-button" aria-label={copy.openNav} aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}><Menu size={21}/></button><span className="breadcrumb-parent">{copy.workspace}</span><span className="breadcrumb-divider">/</span><strong>{title}</strong></div><div className="topbar-tools"><span className="workspace-context"><span/> {selected.tenant_name}</span><LanguageSelector compact/><button className="icon-button" title={copy.quick + " (Ctrl+K)"} aria-label={copy.quick} onClick={openSearch}><Search size={19}/></button></div></header>
      <main id="main-content" className="workspace-main" tabIndex={-1} key={selected.tenant_id}>{children}</main>
      <footer className="workspace-footer"><span>Conformly · {copy.tagline}</span><span>{copy.operations}</span></footer>
    </div>
    <dialog ref={dialog} className="command-dialog" aria-label={copy.quick}><div className="command-input"><Search size={21}/><input ref={search} value={query} onChange={event => setQuery(event.target.value)} placeholder={copy.searchPlaceholder} aria-label={copy.searchLabel}/><button className="icon-button" onClick={() => dialog.current?.close()} aria-label={copy.closeSearch}><X size={18}/></button></div><div className="command-results">{filtered.length === 0 ? <p className="empty-state">{copy.noResults}</p> : filtered.map(item => { const Icon = icons[item.id] ?? Command; return <button key={item.id} onClick={() => go(item.id)}><Icon size={18}/><span>{item.label}</span><ArrowRight size={17}/></button>; })}</div><div className="command-footer">Navigate your workspace <kbd>{copy.escape}</kbd></div></dialog>
  </div>;
}
