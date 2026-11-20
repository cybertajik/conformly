import { describe, expect, it } from "vitest";
import type { TenantRole } from "@conformly/shared";
import {
  canAccessCustomerDemo,
  canCancelTenant,
  canCreateExport,
  canDeleteFiles,
  canManageAssets,
  canManageControlStatus,
  canManageEntitlements,
  canReadEntitlements,
  canManageEvidence,
  canManageFindings,
  canManageFrameworks,
  canManageMemberships,
  canReadMemberships,
  canManageOrganization,
  canManagePolicies,
  canManagePreAudit,
  canManagePublicProfile,
  canManageRetention,
  canManageRisks,
  canManageTasks,
  canManageVendors,
  canManageWhistleblowerCases,
  canManageWhistleblowerPortal,
  canReadAssets,
  canReadEvidence,
  canReadExport,
  canReadFindings,
  canReadFrameworks,
  canReadOrganization,
  canReadPolicies,
  canReadPreAudit,
  canReadPublicProfile,
  canReadRisks,
  canReadTasks,
  canReadVendors,
  canReadWhistleblowerCases,
  canUploadFiles,
  canViewFiles,
} from "./permissions";

describe("permissions", () => {
  const allRoles: TenantRole[] = [
    "owner",
    "administrator",
    "compliance_manager",
    "control_owner",
    "contributor",
    "auditor",
    "reviewer",
    "employee",
  ];

  describe("canAccessCustomerDemo", () => {
    it("allows owner and compliance_manager only", () => {
      expect(canAccessCustomerDemo("owner")).toBe(true);
      expect(canAccessCustomerDemo("compliance_manager")).toBe(true);

      const deniedRoles: TenantRole[] = [
        "administrator",
        "control_owner",
        "contributor",
        "auditor",
        "reviewer",
        "employee",
      ];
      for (const role of deniedRoles) {
        expect(canAccessCustomerDemo(role)).toBe(false);
      }
    });
  });

  describe("Compliance Isolation (Administrator strictly barred from compliance data)", () => {
    it("bars administrator from viewing compliance files and evidence", () => {
      expect(canViewFiles("administrator")).toBe(false);
      expect(canReadEvidence("administrator")).toBe(false);
      expect(canManageEvidence("administrator")).toBe(false);
      expect(canUploadFiles("administrator")).toBe(false);
      expect(canDeleteFiles("administrator")).toBe(false);
    });

    it("bars administrator from frameworks and pre-audit", () => {
      expect(canReadFrameworks("administrator")).toBe(false);
      expect(canManageFrameworks("administrator")).toBe(false);
      expect(canReadPreAudit("administrator")).toBe(false);
      expect(canManagePreAudit("administrator")).toBe(false);
    });

    it("bars administrator from findings, policies, and tasks", () => {
      expect(canReadFindings("administrator")).toBe(false);
      expect(canManageFindings("administrator")).toBe(false);
      expect(canReadPolicies("administrator")).toBe(false);
      expect(canManagePolicies("administrator")).toBe(false);
      expect(canReadTasks("administrator")).toBe(false);
      expect(canManageTasks("administrator")).toBe(false);
    });

    it("bars administrator from operational registers", () => {
      expect(canReadRisks("administrator")).toBe(false);
      expect(canManageRisks("administrator")).toBe(false);
      expect(canReadAssets("administrator")).toBe(false);
      expect(canManageAssets("administrator")).toBe(false);
      expect(canReadVendors("administrator")).toBe(false);
      expect(canManageVendors("administrator")).toBe(false);
    });
  });

  describe("Administrative & Tenant Ownership capabilities", () => {
    it("allows owner and administrator to manage memberships and org", () => {
      expect(canManageMemberships("owner")).toBe(true);
      expect(canManageMemberships("administrator")).toBe(true);
      expect(canManageMemberships("compliance_manager")).toBe(false);
      expect(canManageMemberships("employee")).toBe(false);

      expect(canManageOrganization("owner")).toBe(true);
      expect(canManageOrganization("administrator")).toBe(true);
      expect(canManageOrganization("auditor")).toBe(false);

      expect(canManageEntitlements("owner")).toBe(true);
      expect(canManageEntitlements("administrator")).toBe(true);
      expect(canManageEntitlements("contributor")).toBe(false);

      expect(canReadMemberships("owner")).toBe(true);
      expect(canReadMemberships("administrator")).toBe(true);
      expect(canReadMemberships("compliance_manager")).toBe(false);
      expect(canReadMemberships("employee")).toBe(false);

      expect(canReadEntitlements("owner")).toBe(true);
      expect(canReadEntitlements("administrator")).toBe(true);
      expect(canReadEntitlements("contributor")).toBe(false);
      expect(canReadEntitlements("auditor")).toBe(false);
    });

    it("restricts tenant cancellation exclusively to owner", () => {
      expect(canCancelTenant("owner")).toBe(true);
      for (const role of allRoles.filter((r) => r !== "owner")) {
        expect(canCancelTenant(role)).toBe(false);
      }
    });

    it("allows owner and administrator to manage retention", () => {
      expect(canManageRetention("owner")).toBe(true);
      expect(canManageRetention("administrator")).toBe(true);
      expect(canManageRetention("compliance_manager")).toBe(false);
    });
  });

  describe("Compliance Manager and Contributor capabilities", () => {
    it("allows compliance_manager and control_owner to manage frameworks, tasks and controls", () => {
      expect(canManageFrameworks("compliance_manager")).toBe(true);
      expect(canManageFrameworks("control_owner")).toBe(true);
      expect(canManageControlStatus("compliance_manager")).toBe(true);
      expect(canManageControlStatus("control_owner")).toBe(false);
      expect(canManageTasks("compliance_manager")).toBe(true);
      expect(canManageTasks("control_owner")).toBe(true);
      expect(canReadTasks("compliance_manager")).toBe(true);
    });

    it("allows upload by authorized operational roles", () => {
      expect(canUploadFiles("owner")).toBe(true);
      expect(canUploadFiles("compliance_manager")).toBe(true);
      expect(canUploadFiles("control_owner")).toBe(true);
      expect(canUploadFiles("contributor")).toBe(true);
      expect(canUploadFiles("auditor")).toBe(false);
      expect(canUploadFiles("employee")).toBe(false);
    });
  });

  describe("Public Profile, Exports & Whistleblower", () => {
    it("checks public profile and export access", () => {
      for (const role of allRoles) {
        expect(canReadOrganization(role)).toBe(true);
        expect(canReadPublicProfile(role)).toBe(true);
      }
      expect(canManagePublicProfile("owner")).toBe(true);
      expect(canManagePublicProfile("compliance_manager")).toBe(true);
      expect(canManagePublicProfile("administrator")).toBe(false);

      expect(canCreateExport("owner")).toBe(true);
      expect(canCreateExport("administrator")).toBe(true);
      expect(canCreateExport("compliance_manager")).toBe(true);
      expect(canCreateExport("employee")).toBe(false);

      expect(canReadExport("auditor")).toBe(true);
      expect(canReadExport("reviewer")).toBe(true);
      expect(canReadExport("employee")).toBe(false);
    });

    it("checks whistleblower permissions", () => {
      expect(canReadWhistleblowerCases("owner")).toBe(true);
      expect(canReadWhistleblowerCases("compliance_manager")).toBe(true);
      expect(canReadWhistleblowerCases("administrator")).toBe(false);

      expect(canManageWhistleblowerCases("owner")).toBe(true);
      expect(canManageWhistleblowerCases("compliance_manager")).toBe(true);
      expect(canManageWhistleblowerCases("administrator")).toBe(false);

      expect(canManageWhistleblowerPortal("owner")).toBe(true);
      expect(canManageWhistleblowerPortal("compliance_manager")).toBe(true);
      expect(canManageWhistleblowerPortal("contributor")).toBe(false);
    });
  });
});
