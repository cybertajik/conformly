import type { TenantRole } from "@conformly/shared";

// ── Strict Role Check Utilities (Section 7, Cards 8 & 11) ───────────────────

export function canManageMemberships(role: TenantRole): boolean {
  return role === "owner" || role === "administrator";
}

export function canManageOrganization(role: TenantRole): boolean {
  return role === "owner" || role === "administrator";
}

export function canReadOrganization(role: TenantRole): boolean {
  return Boolean(role);
}

export function canManageEntitlements(role: TenantRole): boolean {
  return role === "owner" || role === "administrator";
}

// ── Strict Compliance Isolation: Administrator CANNOT access compliance content

export function canUploadFiles(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "compliance_manager" ||
    role === "control_owner" ||
    role === "contributor"
  );
}

export function canDeleteFiles(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

export function canViewFiles(role: TenantRole): boolean {
  return role !== "administrator";
}

export function canManageFrameworks(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "compliance_manager" ||
    role === "control_owner" ||
    role === "contributor"
  );
}

export function canReadFrameworks(role: TenantRole): boolean {
  return role !== "administrator" && role !== "employee";
}

export function canReadEvidence(role: TenantRole): boolean {
  return role !== "administrator" && role !== "employee";
}

export function canManageEvidence(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "compliance_manager" ||
    role === "control_owner" ||
    role === "contributor"
  );
}

export function canReadPolicies(role: TenantRole): boolean {
  return role !== "administrator";
}

export function canManagePolicies(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

export function canManageTasks(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "compliance_manager" ||
    role === "control_owner" ||
    role === "contributor"
  );
}

export function canReadTasks(role: TenantRole): boolean {
  return role !== "administrator";
}

export function canManageFindings(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "compliance_manager" ||
    role === "control_owner" ||
    role === "contributor"
  );
}

export function canReadFindings(role: TenantRole): boolean {
  return role !== "administrator" && role !== "employee";
}

export function canManageControlStatus(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

export function canReadPreAudit(role: TenantRole): boolean {
  return role !== "administrator" && role !== "employee";
}

export function canManagePreAudit(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

// ── Operational Registers (Section 15, Card 17) ──────────────────────────────

export function canReadRisks(role: TenantRole): boolean {
  return role !== "administrator" && role !== "employee";
}

export function canManageRisks(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

export function canReadAssets(role: TenantRole): boolean {
  return role !== "administrator" && role !== "employee";
}

export function canManageAssets(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "compliance_manager" ||
    role === "control_owner" ||
    role === "contributor"
  );
}

export function canReadVendors(role: TenantRole): boolean {
  return role !== "administrator" && role !== "employee";
}

export function canManageVendors(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

// ── Public Profile & Exports ──────────────────────────────────────────────────

export function canReadPublicProfile(role: TenantRole): boolean {
  return Boolean(role);
}

export function canManagePublicProfile(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

export function canCreateExport(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canReadExport(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "administrator" ||
    role === "compliance_manager" ||
    role === "reviewer" ||
    role === "auditor"
  );
}

export function canCancelTenant(role: TenantRole): boolean {
  return role === "owner";
}

export function canManageRetention(role: TenantRole): boolean {
  return role === "owner" || role === "administrator";
}

// ── Whistleblower (Add-on module) ─────────────────────────────────────────────

export function canReadWhistleblowerCases(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

export function canManageWhistleblowerCases(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}

export function canManageWhistleblowerPortal(role: TenantRole): boolean {
  return role === "owner" || role === "compliance_manager";
}
