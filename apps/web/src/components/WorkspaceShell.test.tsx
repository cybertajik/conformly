import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceShell, type NavigationItem } from "./WorkspaceShell";
import { I18nProvider } from "../i18n/I18nContext";
import type { TenantMembershipSummary } from "@conformly/shared";

const tenants = [
  { tenant_id:"one", tenant_name:"Northstar", tenant_slug:"northstar", role:"owner" },
  { tenant_id:"two", tenant_name:"Harbor", tenant_slug:"harbor", role:"administrator" }
] as TenantMembershipSummary[];
const items: NavigationItem[] = [{id:"overview",label:"Overview"},{id:"onboarding",label:"Setup guide"},{id:"risks",label:"Risk Register"}];
function mount(overrides: Partial<Parameters<typeof WorkspaceShell>[0]> = {}) {
  const props = {items,tab:"overview" as const,navigate:vi.fn(),tenants,selected:tenants[0],chooseTenant:vi.fn(),signOut:vi.fn(),children:<h1>Workspace content</h1>,...overrides};
  render(<I18nProvider><WorkspaceShell {...props}/></I18nProvider>);
  return props;
}
beforeEach(() => {
  localStorage.clear();
  HTMLDialogElement.prototype.showModal = function() { this.open = true; };
  HTMLDialogElement.prototype.close = function() { this.open = false; };
});
afterEach(cleanup);
describe("WorkspaceShell", () => {
  it("marks the active page and only exposes allowed navigation", () => {
    const props = mount();
    const navigation = screen.getByRole("navigation",{name:"Primary navigation"});
    expect(within(navigation).getByRole("button",{name:"Overview"})).toHaveAttribute("aria-current","page");
    expect(within(navigation).queryByRole("button",{name:"Members"})).not.toBeInTheDocument();
    fireEvent.click(within(navigation).getByRole("button",{name:"Risk Register"}));
    expect(props.navigate).toHaveBeenCalledWith("risks");
  });
  it("filters quick navigation and routes only to a supplied page", () => {
    const props = mount();
    fireEvent.keyDown(window,{key:"k",ctrlKey:true});
    const dialog = screen.getByRole("dialog",{name:"Quick navigation"});
    fireEvent.change(within(dialog).getByRole("textbox"),{target:{value:"risk"}});
    expect(within(dialog).queryByRole("button",{name:"Overview"})).not.toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button",{name:"Risk Register"}));
    expect(props.navigate).toHaveBeenCalledWith("risks");
    expect(dialog).not.toHaveAttribute("open");
  });
  it("switches tenants without altering the selected tenant itself", () => {
    const props = mount();
    fireEvent.change(screen.getByRole("combobox",{name:"Organization"}),{target:{value:"two"}});
    expect(props.chooseTenant).toHaveBeenCalledWith("two");
  });
  it("closes mobile navigation on Escape and restores the page", () => {
    mount();
    fireEvent.click(screen.getByRole("button",{name:"Open navigation"}));
    expect(screen.getByRole("button",{name:"Open navigation",hidden:true})).toHaveAttribute("aria-expanded","true");
    fireEvent.keyDown(window,{key:"Escape"});
    expect(screen.getByRole("button",{name:"Open navigation"})).toHaveAttribute("aria-expanded","false");
    expect(document.body.style.overflow).toBe("");
  });
  it("translates new navigation controls and keeps tenant data unchanged", () => {
    localStorage.setItem("conformly.locale","de");
    mount();
    expect(screen.getByRole("button",{name:"Schnellnavigation"})).toBeInTheDocument();
    expect(screen.getByRole("combobox",{name:"Organisation"})).toHaveValue("one");
  });
});
