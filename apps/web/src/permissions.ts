import type { TenantRole } from "@conformly/shared";

export function canManageMemberships(role: TenantRole): boolean {
  return role === "owner" || role === "administrator";
}

export function canUploadFiles(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "administrator" ||
    role === "compliance_manager" ||
    role === "contributor"
  );
}

export function canDeleteFiles(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canViewFiles(role: TenantRole): boolean {
  return Boolean(role);
}

export function canManageFrameworks(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "administrator" ||
    role === "compliance_manager" ||
    role === "contributor"
  );
}

export function canReadFrameworks(role: TenantRole): boolean {
  return Boolean(role);
}

export function canReadEvidence(role: TenantRole): boolean {
  return Boolean(role);
}

export function canManageEvidence(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "administrator" ||
    role === "compliance_manager" ||
    role === "contributor"
  );
}

export function canReadPolicies(role: TenantRole): boolean {
  return Boolean(role);
}

export function canManagePolicies(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canManageTasks(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "administrator" ||
    role === "compliance_manager" ||
    role === "contributor"
  );
}

export function canManageFindings(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "administrator" ||
    role === "compliance_manager" ||
    role === "contributor"
  );
}

export function canManageControlStatus(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canReadPreAudit(role: TenantRole): boolean {
  return Boolean(role);
}

export function canManagePreAudit(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canReadWhistleblowerCases(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canManageWhistleblowerCases(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canManageWhistleblowerPortal(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canReadPublicProfile(role: TenantRole): boolean {
  return Boolean(role);
}

export function canManagePublicProfile(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canCreateExport(role: TenantRole): boolean {
  return role === "owner" || role === "administrator" || role === "compliance_manager";
}

export function canReadExport(role: TenantRole): boolean {
  return (
    role === "owner" ||
    role === "administrator" ||
    role === "compliance_manager" ||
    role === "auditor"
  );
}

export function canCancelTenant(role: TenantRole): boolean {
  return role === "owner";
}

export function canManageRetention(role: TenantRole): boolean {
  return role === "owner" || role === "administrator";
}



