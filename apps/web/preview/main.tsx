import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "../src/App";
import "../src/styles.css";

// Isolated visual QA entry point. Not imported or emitted by the production entry.
// All API requests are intercepted; this page never signs in or contacts a server.
const tenant = { tenant_id: "visual-fixture", tenant_name: "Northstar Technologies", tenant_slug: "northstar-preview", role: "owner" };
sessionStorage.setItem("conformly.access_token", "synthetic-visual-fixture-not-a-credential");
localStorage.setItem("conformly.locale", "en");
const summary = {
  readiness_score: 72, is_administrator_view: false, admin_metrics: null,
  controls_summary: { total: 96, implemented: 69, in_progress: 19, not_started: 8 },
  frameworks_adopted: [
    { framework_id: "iso", framework_name: "ISO/IEC 27001:2022", total_controls: 93, implemented_controls: 67, progress_percentage: 72 },
    { framework_id: "soc", framework_name: "SOC 2", total_controls: 64, implemented_controls: 35, progress_percentage: 55 },
    { framework_id: "gdpr", framework_name: "GDPR", total_controls: 42, implemented_controls: 36, progress_percentage: 86 }
  ],
  expiring_evidence: [
    { id: "ev1", title: "Quarterly access review", classification: "Confidential", expires_at: "2026-09-18", days_remaining: 4 },
    { id: "ev2", title: "Security awareness training", classification: "Internal", expires_at: "2026-09-24", days_remaining: 10 }
  ],
  review_due_policies: [{ id: "pol1", title: "Information security policy", review_due_at: "2026-09-21", days_remaining: 7 }],
  open_tasks: [
    { id: "t1", title: "Complete supplier risk assessment", priority: "high", status: "in_progress", due_date: "2026-09-18" },
    { id: "t2", title: "Review evidence for access controls", priority: "critical", status: "pending", due_date: "2026-09-19" },
    { id: "t3", title: "Update incident response procedure", priority: "medium", status: "pending", due_date: "2026-09-25" }
  ],
  top_risks: [{ id: "r1", title: "Third-party access management", inherent_score: 16, residual_score: 8, status: "treating" }],
  vendor_health: { total_vendors: 24, signed_dpa_count: 21, missing_dpa_count: 3, critical_vendors: 4 },
  recent_activity: [
    { id: "a1", action: "evidence.uploaded", resource_type: "access review", occurred_at: "2026-09-14T09:00:00Z" },
    { id: "a2", action: "control.implemented", resource_type: "information security policy", occurred_at: "2026-09-13T12:00:00Z" },
    { id: "a3", action: "framework.adopted", resource_type: "ISO/IEC 27001", occurred_at: "2026-09-12T12:00:00Z" }
  ]
};
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  if (init?.method && init.method !== "GET" && path !== "/v1/auth/session" && path !== "/api/v1/auth/session") return new Response(JSON.stringify({detail:"Visual fixture: changes are disabled."}), {status:403});
  let data: unknown = [];
  if(path.endsWith("/auth/session")) data = { user_id: "preview-user", email: "preview@example.invalid" };
  else if(path.endsWith("/me/tenants")) data = [tenant];
  else if(path.endsWith("/context")) data = { ...tenant, id: tenant.tenant_id };
  else if(path.includes("dashboard")) data = summary;
  return new Response(JSON.stringify(data), {status:200,headers:{"Content-Type":"application/json"}});
};
createRoot(document.getElementById("root")!).render(<StrictMode><div style={{position:"fixed",bottom:0,left:0,zIndex:9999,background:"#fff5dc",color:"#755110",padding:"3px 10px",fontSize:10}}>VISUAL QA · Synthetic data · No server requests</div><App/></StrictMode>);
