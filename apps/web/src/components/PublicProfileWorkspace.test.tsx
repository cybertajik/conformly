import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PublicProfileWorkspace } from "./PublicProfileWorkspace";
import type {
  PreAuditCertificateSummary,
  PreAuditSummary,
  PublicProfileDetailSummary,
} from "@conformly/shared";

const mockDraftProfile: PublicProfileDetailSummary = {
  id: "profile-1",
  tenant_id: "tenant-1",
  slug: "cyberdyne",
  display_name: "Cyberdyne Systems",
  description: "Compliance operations platform.",
  logo_url: "https://cyberdyne.com/logo.png",
  website_url: "https://cyberdyne.com",
  primary_contact_email: "compliance@cyberdyne.com",
  is_published: false,
  published_at: null,
  version: 1,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  credentials: [
    {
      id: "cred-1",
      profile_id: "profile-1",
      tenant_id: "tenant-1",
      credential_type: "third_party",
      title: "ISO 27001 Certification",
      issuer_name: "BSI Group",
      scope_description: "Global cloud services scope.",
      issued_at: "2026-08-01T00:00:00Z",
      valid_until: "2028-08-01T00:00:00Z",
      status: "active",
      verification_url: "https://verify.bsigroup.com",
      source_certificate_id: null,
      is_publicly_visible: true,
      display_order: 0,
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-08-01T00:00:00Z",
    },
  ],
  statements: [
    {
      id: "stmt-1",
      profile_id: "profile-1",
      tenant_id: "tenant-1",
      title: "Data Sovereignty Pledge",
      statement_content: "All data encrypted at rest with AES-256-GCM.",
      display_order: 0,
      is_publicly_visible: true,
      created_at: "2026-09-01T00:00:00Z",
      updated_at: "2026-09-01T00:00:00Z",
    },
  ],
};

const mockPreAuditCert: PreAuditCertificateSummary = {
  id: "cert-99",
  tenant_id: "tenant-1",
  pre_audit_id: "pa-1",
  certificate_number: "CONF-2026-SOC2",
  status: "active",
  issued_at: "2026-09-01T00:00:00Z",
  expires_at: "2027-09-01T00:00:00Z",
  revoked_at: null,
  revoked_reason: null,
  created_at: "2026-09-01T00:00:00Z",
};

const mockPreAudit: PreAuditSummary = {
  id: "pa-1",
  tenant_id: "tenant-1",
  title: "SOC 2 Readiness Evaluation",
  description: "Assessment for SOC 2 Type II readiness",
  status: "completed",
  framework_adoption_id: "fa-1",
  lead_user_id: "u-1",
  reviewer_user_id: "u-2",
  reviewed_at: "2026-09-01T00:00:00Z",
  rule_version: "v1.0.0",
  overall_score: 0.95,
  version: 1,
  certificates: [mockPreAuditCert],
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const mockApi = {
  getTenantPublicProfile: vi.fn(),
  configureTenantPublicProfile: vi.fn(),
  publishTenantPublicProfile: vi.fn(),
  unpublishTenantPublicProfile: vi.fn(),
  addTenantPublicCredential: vi.fn(),
  linkPreAuditPublicCredential: vi.fn(),
  updateTenantPublicCredential: vi.fn(),
  revokeTenantPublicCredential: vi.fn(),
  deleteTenantPublicCredential: vi.fn(),
  addTenantPublicStatement: vi.fn(),
  deleteTenantPublicStatement: vi.fn(),
  listPreAudits: vi.fn(),
};

vi.mock("../api", () => ({
  getTenantPublicProfile: (...args: unknown[]) => mockApi.getTenantPublicProfile(...args),
  configureTenantPublicProfile: (...args: unknown[]) => mockApi.configureTenantPublicProfile(...args),
  publishTenantPublicProfile: (...args: unknown[]) => mockApi.publishTenantPublicProfile(...args),
  unpublishTenantPublicProfile: (...args: unknown[]) => mockApi.unpublishTenantPublicProfile(...args),
  addTenantPublicCredential: (...args: unknown[]) => mockApi.addTenantPublicCredential(...args),
  linkPreAuditPublicCredential: (...args: unknown[]) => mockApi.linkPreAuditPublicCredential(...args),
  updateTenantPublicCredential: (...args: unknown[]) => mockApi.updateTenantPublicCredential(...args),
  revokeTenantPublicCredential: (...args: unknown[]) => mockApi.revokeTenantPublicCredential(...args),
  deleteTenantPublicCredential: (...args: unknown[]) => mockApi.deleteTenantPublicCredential(...args),
  addTenantPublicStatement: (...args: unknown[]) => mockApi.addTenantPublicStatement(...args),
  deleteTenantPublicStatement: (...args: unknown[]) => mockApi.deleteTenantPublicStatement(...args),
  listPreAudits: (...args: unknown[]) => mockApi.listPreAudits(...args),
}));

describe("PublicProfileWorkspace", () => {
  beforeEach(() => {
    mockApi.getTenantPublicProfile.mockResolvedValue({ ...mockDraftProfile });
    mockApi.listPreAudits.mockResolvedValue([mockPreAudit]);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders workspace and shows unpublished status badge", async () => {
    render(
      <PublicProfileWorkspace
        token="test-token"
        tenantId="tenant-1"
        role="compliance_manager"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-workspace")).toBeInTheDocument();
    });

    expect(screen.getByText("Public Compliance Trust Center")).toBeInTheDocument();
    expect(screen.getByTestId("profile-status-badge")).toHaveTextContent("Draft (Unpublished)");
  });

  it("publishes profile with optimistic concurrency control", async () => {
    mockApi.publishTenantPublicProfile.mockResolvedValue({
      ...mockDraftProfile,
      is_published: true,
      published_at: "2026-09-12T00:00:00Z",
      version: 2,
    });

    render(
      <PublicProfileWorkspace
        token="test-token"
        tenantId="tenant-1"
        role="compliance_manager"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("toggle-publish-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-publish-btn"));

    await waitFor(() => {
      expect(mockApi.publishTenantPublicProfile).toHaveBeenCalledWith(
        "test-token",
        "tenant-1",
        1
      );
    });

    expect(screen.getByText("Unpublish Profile")).toBeInTheDocument();
  });

  it("switches to credentials tab and links pre-audit badge", async () => {
    mockApi.linkPreAuditPublicCredential.mockResolvedValue({
      id: "cred-2",
      profile_id: "profile-1",
      tenant_id: "tenant-1",
      credential_type: "conformly_readiness",
      title: "Conformly Pre-Audit Readiness: SOC 2 Readiness Evaluation",
      issuer_name: "Conformly Automated Compliance",
      scope_description: "Evaluation against rule set v1.0.0.",
      issued_at: "2026-09-01T00:00:00Z",
      valid_until: "2027-09-01T00:00:00Z",
      status: "active",
      verification_url: null,
      source_certificate_id: "cert-99",
      is_publicly_visible: true,
      display_order: 1,
      created_at: "2026-09-01T00:00:00Z",
      updated_at: "2026-09-01T00:00:00Z",
    });

    render(
      <PublicProfileWorkspace
        token="test-token"
        tenantId="tenant-1"
        role="compliance_manager"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("tab-credentials")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("tab-credentials"));

    expect(screen.getByText("ISO 27001 Certification")).toBeInTheDocument();

    // Click Link Conformly Pre-Audit Badge
    fireEvent.click(screen.getByTestId("import-preaudit-badge-btn"));

    await waitFor(() => {
      expect(screen.getByText("CONF-2026-SOC2")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Link Badge"));

    await waitFor(() => {
      expect(mockApi.linkPreAuditPublicCredential).toHaveBeenCalledWith("test-token", "tenant-1", {
        certificate_id: "cert-99",
        is_publicly_visible: true,
        display_order: 1,
      });
    });
  });

  it("allows revoking a credential with reason", async () => {
    mockApi.revokeTenantPublicCredential.mockResolvedValue({
      ...mockDraftProfile.credentials[0],
      status: "revoked",
    });

    render(
      <PublicProfileWorkspace
        token="test-token"
        tenantId="tenant-1"
        role="compliance_manager"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("tab-credentials")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("tab-credentials"));

    const revokeBtn = screen.getByTestId("revoke-cred-btn-cred-1");
    fireEvent.click(revokeBtn);

    const reasonInput = screen.getByPlaceholderText(/superseded by recertification/i);
    fireEvent.change(reasonInput, {
      target: { value: "Recertification complete with updated ISO version." },
    });

    fireEvent.click(screen.getByText("Confirm Revoke"));

    await waitFor(() => {
      expect(mockApi.revokeTenantPublicCredential).toHaveBeenCalledWith(
        "test-token",
        "tenant-1",
        "cred-1",
        "Recertification complete with updated ISO version."
      );
    });
  });

  it("prevents viewers and auditors from publishing or modifying credentials", async () => {
    render(
      <PublicProfileWorkspace
        token="test-token"
        tenantId="tenant-1"
        role="auditor"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-workspace")).toBeInTheDocument();
    });

    // Auditor cannot publish
    expect(screen.queryByTestId("toggle-publish-btn")).not.toBeInTheDocument();

    // Auditor cannot add credentials
    fireEvent.click(screen.getByTestId("tab-credentials"));
    expect(screen.queryByTestId("import-preaudit-badge-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-third-party-cert-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("revoke-cred-btn-cred-1")).not.toBeInTheDocument();
  });
});
