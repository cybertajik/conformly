import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PublicProfileView } from "./PublicProfileView";
import type { PublicProfileView as PublicProfileViewType } from "@conformly/shared";

const mockPublicProfile: PublicProfileViewType = {
  id: "profile-1",
  slug: "cyberdyne-trust",
  display_name: "Cyberdyne Systems Security & Trust",
  description: "Autonomous compliance infrastructure and verified audit readiness.",
  logo_url: "https://cyberdyne.com/logo.png",
  website_url: "https://cyberdyne.com",
  primary_contact_email: "security@cyberdyne.com",
  published_at: "2026-09-01T12:00:00Z",
  conformly_verified: true,
  disclaimer:
    "Conformly is an audit-readiness and compliance operations platform, not an accredited certification body.",
  credentials: [
    {
      id: "cred-1",
      profile_id: "profile-1",
      tenant_id: "tenant-1",
      credential_type: "conformly_readiness",
      title: "Conformly Pre-Audit Readiness: SOC 2 Type II",
      issuer_name: "Conformly Automated Compliance",
      scope_description: "Evaluation against rule set v1.0.0. Overall readiness score: 95.0%.",
      issued_at: "2026-09-01T12:00:00Z",
      valid_until: "2027-09-01T12:00:00Z",
      status: "active",
      verification_url: "/v1/public/certificates/CONF-2026-99",
      source_certificate_id: "cert-1",
      is_publicly_visible: true,
      display_order: 0,
      created_at: "2026-09-01T12:00:00Z",
      updated_at: "2026-09-01T12:00:00Z",
    },
    {
      id: "cred-2",
      profile_id: "profile-1",
      tenant_id: "tenant-1",
      credential_type: "third_party",
      title: "ISO/IEC 27001:2022 Certification",
      issuer_name: "BSI Group",
      scope_description: "Information security management for global SaaS infrastructure.",
      issued_at: "2026-08-15T00:00:00Z",
      valid_until: "2028-08-15T00:00:00Z",
      status: "active",
      verification_url: "https://verify.bsigroup.com/cyberdyne",
      source_certificate_id: null,
      is_publicly_visible: true,
      display_order: 1,
      created_at: "2026-08-15T00:00:00Z",
      updated_at: "2026-08-15T00:00:00Z",
    },
  ],
  statements: [
    {
      id: "stmt-1",
      profile_id: "profile-1",
      tenant_id: "tenant-1",
      title: "Data Sovereignty & Envelope Encryption",
      statement_content: "All tenant data is protected with application-layer AES-256-GCM envelope encryption.",
      display_order: 0,
      is_publicly_visible: true,
      created_at: "2026-09-01T12:00:00Z",
      updated_at: "2026-09-01T12:00:00Z",
    },
  ],
};

vi.mock("../api", () => ({
  getPublicProfile: vi.fn().mockImplementation((slug: string) => {
    if (slug === "cyberdyne-trust") {
      return Promise.resolve({ data: mockPublicProfile, notModified: false });
    }
    return Promise.reject(new Error("Compliance profile is currently unpublished or unavailable."));
  }),
}));

describe("PublicProfileView", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders public trust center with branding, disclaimer, badges, and statements", async () => {
    render(<PublicProfileView slug="cyberdyne-trust" />);

    await waitFor(() => {
      expect(screen.getByTestId("trust-center-view")).toBeInTheDocument();
    });

    expect(screen.getByText("Cyberdyne Systems Security & Trust")).toBeInTheDocument();
    expect(screen.getByTestId("conformly-verified-badge")).toBeInTheDocument();
    expect(screen.getByTestId("regulatory-disclaimer-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/Conformly is an audit-readiness and compliance operations platform/i)
    ).toBeInTheDocument();

    // Badges
    expect(screen.getByText("Conformly Pre-Audit Readiness: SOC 2 Type II")).toBeInTheDocument();
    expect(screen.getByText("ISO/IEC 27001:2022 Certification")).toBeInTheDocument();

    // Statement
    expect(screen.getByText("Data Sovereignty & Envelope Encryption")).toBeInTheDocument();
  });

  it("renders unavailable error state when profile does not exist or is unpublished", async () => {
    render(<PublicProfileView slug="non-existent" />);

    await waitFor(() => {
      expect(screen.getByTestId("trust-center-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Trust Center Unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/Compliance profile is currently unpublished or unavailable/i)
    ).toBeInTheDocument();
  });

  it("filters credentials between Conformly readiness badges and 3rd-party certs", async () => {
    render(<PublicProfileView slug="cyberdyne-trust" initialData={mockPublicProfile} />);

    // Initially both are visible
    expect(screen.getByText("Conformly Pre-Audit Readiness: SOC 2 Type II")).toBeInTheDocument();
    expect(screen.getByText("ISO/IEC 27001:2022 Certification")).toBeInTheDocument();

    // Filter to Conformly badges only
    fireEvent.click(screen.getByText("Conformly Badges"));
    expect(screen.getByText("Conformly Pre-Audit Readiness: SOC 2 Type II")).toBeInTheDocument();
    expect(screen.queryByText("ISO/IEC 27001:2022 Certification")).not.toBeInTheDocument();

    // Filter to 3rd-party certs only
    fireEvent.click(screen.getByText("3rd-Party Certifications"));
    expect(screen.queryByText("Conformly Pre-Audit Readiness: SOC 2 Type II")).not.toBeInTheDocument();
    expect(screen.getByText("ISO/IEC 27001:2022 Certification")).toBeInTheDocument();

    // Filter back to All
    fireEvent.click(screen.getByText(/All \(2\)/));
    expect(screen.getByText("Conformly Pre-Audit Readiness: SOC 2 Type II")).toBeInTheDocument();
    expect(screen.getByText("ISO/IEC 27001:2022 Certification")).toBeInTheDocument();
  });

  it("opens and closes credential inspection modal", async () => {
    render(<PublicProfileView slug="cyberdyne-trust" initialData={mockPublicProfile} />);

    const detailsButtons = screen.getAllByText("Details →");
    fireEvent.click(detailsButtons[0]);

    const modal = screen.getByTestId("credential-detail-modal");
    expect(within(modal).getByText("Conformly Automated Compliance")).toBeInTheDocument();
    expect(
      within(modal).getByText("Evaluation against rule set v1.0.0. Overall readiness score: 95.0%.")
    ).toBeInTheDocument();

    // Close modal
    fireEvent.click(within(modal).getByText("Close"));
    expect(screen.queryByTestId("credential-detail-modal")).not.toBeInTheDocument();
  });
});
