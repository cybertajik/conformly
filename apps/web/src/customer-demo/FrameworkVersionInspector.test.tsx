import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { FrameworkVersionInspector } from "./FrameworkVersionInspector";
import { DemoManifest, DemoPack, WorkspaceData } from "./types";

const mockPackV1: DemoPack = {
  pack_id: "pack-wp09",
  pack_version_id: "pack-v1",
  version: "1.0.0",
  name: "Synthetic Customer Baseline Pack",
  description: "Baseline customer onboarding requirements",
  bundle_digest: "acc8f821be6ae61ece7961683af39c343d14854d8092494ac6410eb33d14e197",
  requirement_count: 2,
  requirements: [
    {
      id: "req-1",
      version_id: "req-1-v1",
      identifier: "REQ-CLOUD-STORAGE",
      title: "Cloud Storage Encryption",
      description: "Ensure storage is encrypted",
      rule_id: "rule-1",
      rule_version_id: "rule-1-v1",
      control_id: "ctrl-1",
      control_version_id: "ctrl-1-v1",
      control_identifier: "CTRL-STORAGE-SEC",
      control_title: "Storage Security",
    },
    {
      id: "req-2",
      version_id: "req-2-v1",
      identifier: "REQ-EU-PROCESSING",
      title: "EU Processing",
      description: "Ensure regional residency",
      rule_id: "rule-2",
      rule_version_id: "rule-2-v1",
      control_id: "ctrl-2",
      control_version_id: "ctrl-2-v1",
      control_identifier: "CTRL-EU-DATA",
      control_title: "Data Residency",
    },
  ],
};

const mockPackV2: DemoPack = {
  pack_id: "pack-wp09",
  pack_version_id: "pack-v2",
  version: "2.0.0",
  name: "Synthetic Customer Extended Pack",
  description: "Extended customer onboarding requirements",
  bundle_digest: "8b2273b87ba78008ea5d4f0032fcbfc531711c1770d70e6da98e837fd6a0e0cb",
  requirement_count: 3,
  requirements: [
    {
      ...mockPackV1.requirements[0],
      rule_version_id: "rule-1-v2", // changed rule pin
    },
    mockPackV1.requirements[1],
    {
      id: "req-3",
      version_id: "req-3-v1",
      identifier: "REQ-HYBRID-FALLBACK",
      title: "Hybrid Fallback Protection",
      description: "Hybrid containment",
      rule_id: "rule-3",
      rule_version_id: "rule-3-v1",
      control_id: "ctrl-3",
      control_version_id: "ctrl-3-v1",
      control_identifier: "CTRL-HYBRID",
      control_title: "Hybrid Control",
    },
  ],
};

const mockDifferentPack: DemoPack = {
  pack_id: "pack-iso-27001",
  pack_version_id: "iso-v1",
  version: "1.0.0",
  name: "Synthetic ISO 27001 Pack",
  description: "ISMS requirements",
  bundle_digest: "1111111111111111111111111111111111111111111111111111111111111111",
  requirement_count: 1,
  requirements: [
    {
      id: "iso-req-1",
      version_id: "iso-req-1-v1",
      identifier: "ISO-A5-1",
      title: "Policies for information security",
      description: "Define policies",
      rule_id: "iso-rule-1",
      rule_version_id: "iso-rule-1-v1",
      control_id: "iso-ctrl-1",
      control_version_id: "iso-ctrl-1-v1",
      control_identifier: "A.5.1",
      control_title: "InfoSec Policies",
    },
  ],
};


const mockResiliencePackV1: DemoPack = {
  pack_id: "wp09-pack-service-resilience",
  pack_version_id: "wp09-resilience-v1",
  version: "1.0.0",
  name: "Synthetic Service Resilience Baseline Pack",
  description: "Resilience baseline requirements",
  bundle_digest: "9e348609c13459281ab8f9d9e8aac7bafa8f1510ffaf9949d07b38cab9cf38b4",
  requirement_count: 3,
  requirements: [
    {
      id: "req-res-1",
      version_id: "req-res-1-v1",
      identifier: "SYNTH-RES-001",
      title: "Synthetic Resilience Cloud Baseline",
      description: "Cloud baseline",
      rule_id: "rule-res-1",
      rule_version_id: "rule-res-1-v1",
      control_id: "ctrl-1",
      control_version_id: "ctrl-1-v1",
      control_identifier: "SYNTH-CTRL-001",
      control_title: "Cloud Configuration & Access Baseline",
    },
    {
      id: "req-res-2",
      version_id: "req-res-2-v1",
      identifier: "SYNTH-RES-002",
      title: "Synthetic Regional Failover Strategy",
      description: "Regional failover",
      rule_id: "rule-res-2",
      rule_version_id: "rule-res-2-v1",
      control_id: "ctrl-res-4",
      control_version_id: "ctrl-res-4-v1",
      control_identifier: "SYNTH-CTRL-004",
      control_title: "Automated Service Failover & Redundancy",
    },
    {
      id: "req-res-3",
      version_id: "req-res-3-v1",
      identifier: "SYNTH-RES-003",
      title: "Synthetic Legacy Disaster Recovery Standard",
      description: "Legacy DR",
      rule_id: "rule-res-3",
      rule_version_id: "rule-res-3-v1",
      control_id: "ctrl-res-5",
      control_version_id: "ctrl-res-5-v1",
      control_identifier: "SYNTH-CTRL-005",
      control_title: "Immutable Backup & Restoration Assurance",
    },
  ],
};

const mockResiliencePackV2: DemoPack = {
  pack_id: "wp09-pack-service-resilience",
  pack_version_id: "wp09-resilience-v2",
  version: "2.0.0",
  name: "Synthetic Service Resilience Extended Pack",
  description: "Resilience extended requirements",
  bundle_digest: "ee82e0b3717ed2d7a25983dc0bc8985fa560efe89dc7b42f22893287c1dee5f4",
  requirement_count: 3,
  requirements: [
    mockResiliencePackV1.requirements[0], // unchanged req-res-1
    {
      ...mockResiliencePackV1.requirements[1],
      version_id: "req-res-2-v2", // changed pin
      rule_version_id: "rule-res-2-v2",
      title: "Synthetic Multi-Region Failover Architecture",
    },
    {
      id: "req-res-4",
      version_id: "req-res-4-v1",
      identifier: "SYNTH-RES-004",
      title: "Synthetic Continuous Capacity & Monitoring",
      description: "Capacity monitoring",
      rule_id: "rule-res-4",
      rule_version_id: "rule-res-4-v1",
      control_id: "ctrl-res-6",
      control_version_id: "ctrl-res-6-v1",
      control_identifier: "SYNTH-CTRL-006",
      control_title: "Continuous Capacity & Degradation Containment",
    },
  ],
};

const mockManifest: DemoManifest = {
  disclaimer: "Synthetic demonstration",
  evaluator_version: "wp09-synthetic-v1",
  companies: [],
  fact_definitions: [],
  packs: [mockPackV1, mockPackV2, mockResiliencePackV1, mockResiliencePackV2, mockDifferentPack],
};

const mockWorkspace: WorkspaceData = {
  tenant_id: "tenant-1",
  current_revision: 1,
  selection_revision: 1,
  manifest: mockManifest,
  answers: null,
  selected_pack: {
    selection_revision: 1,
    evaluation_id: "eval-1",
    pack_version_id: "pack-v1",
    bundle_digest: mockPackV1.bundle_digest,
    created_at: "2026-10-25T10:00:00Z",
    is_stale: false,
  },
  latest_evaluation: null,
  history_summary: [
    {
      selection_revision: 1,
      pack_version_id: "pack-v1",
      bundle_digest: mockPackV1.bundle_digest,
      created_at: "2026-10-25T10:00:00Z",
    },
  ],
};

describe("FrameworkVersionInspector Component", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders version comparison between current v1 and candidate v2", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    expect(screen.getByTestId("version-inspector")).toBeInTheDocument();
    expect(screen.getByText("Framework Version Inspector")).toBeInTheDocument();
    expect(screen.getAllByText(/Synthetic Customer Baseline Pack/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId("candidate-version-select")).toBeInTheDocument();
  });

  it("identifies added requirements in candidate pack", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    const addedList = screen.getByTestId("added-requirements-list");
    expect(addedList).toBeInTheDocument();
    expect(addedList).toHaveTextContent("REQ-HYBRID-FALLBACK");
  });

  it("identifies changed version pins in matching requirements", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    const changedPinsList = screen.getByTestId("changed-pins-list");
    expect(changedPinsList).toBeInTheDocument();
    expect(changedPinsList).toHaveTextContent("REQ-CLOUD-STORAGE");
    expect(changedPinsList).toHaveTextContent("rule-1-v");
  });

  it("displays bundle digests and distinguishes versions", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    const digestBox = screen.getByTestId("bundle-digest-comparison");
    expect(digestBox).toHaveTextContent(mockPackV1.bundle_digest);
    expect(digestBox).toHaveTextContent(mockPackV2.bundle_digest);
    expect(digestBox).toHaveTextContent(/differ/i);
  });

  it("displays stale adoption warning when is_stale is true", () => {
    const staleWorkspace: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        ...mockWorkspace.selected_pack!,
        is_stale: true,
      },
    };

    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={staleWorkspace} />
      </I18nProvider>
    );

    expect(screen.getByTestId("stale-warning")).toBeInTheDocument();
    expect(screen.getByText(/Stale Adoption/i)).toBeInTheDocument();
  });

  it("renders preserved immutable adoption history records", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    const historyList = screen.getByTestId("adoption-history-list");
    expect(historyList).toBeInTheDocument();
    expect(historyList).toHaveTextContent("Rev 1:");
    expect(historyList).toHaveTextContent(mockPackV1.bundle_digest.slice(0, 10));
  });

  it("switches candidate version when dropdown changes", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    const select = screen.getByTestId("candidate-version-select");
    fireEvent.change(select, { target: { value: "pack-v1" } });

    // When candidate is also pack-v1, 0 diffs
    const digestBox = screen.getByTestId("bundle-digest-comparison");
    expect(digestBox).toHaveTextContent(/identical/i);
  });

  it("displays alert notice when adopted version is unavailable in manifest", () => {
    const unavailableWorkspace: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        ...mockWorkspace.selected_pack!,
        pack_version_id: "unknown-legacy-pack-version",
      },
    };

    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={unavailableWorkspace} />
      </I18nProvider>
    );

    expect(screen.getByTestId("adopted-unavailable-notice")).toBeInTheDocument();
    expect(screen.queryByTestId("bundle-digest-comparison")).not.toBeInTheDocument();
  });

  it("guards against cross-pack comparisons across different pack families", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    const select = screen.getByTestId("candidate-version-select");
    fireEvent.change(select, { target: { value: "iso-v1" } });

    expect(screen.getByTestId("cross-pack-notice")).toBeInTheDocument();
    expect(screen.queryByTestId("added-requirements-list")).not.toBeInTheDocument();
  });

  it("flags inconsistent metadata when same version ID has differing digests", () => {
    const driftedWorkspace: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        ...mockWorkspace.selected_pack!,
        pack_version_id: "pack-v1",
        bundle_digest: "drifted-digest-99999999999999999999999999999999999999999999999999",
      },
    };

    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={driftedWorkspace} />
      </I18nProvider>
    );

    const select = screen.getByTestId("candidate-version-select");
    fireEvent.change(select, { target: { value: "pack-v1" } });

    expect(screen.getByTestId("inconsistent-digest-notice")).toBeInTheDocument();
    expect(screen.queryByTestId("bundle-digest-comparison")).not.toBeInTheDocument();
  });
  it("compares second synthetic resilience pack v1 vs v2 identifying added, removed, changed and unchanged pins", () => {
    const resilienceWorkspace: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        ...mockWorkspace.selected_pack!,
        pack_version_id: "wp09-resilience-v1",
        bundle_digest: mockResiliencePackV1.bundle_digest,
      },
    };

    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={resilienceWorkspace} />
      </I18nProvider>
    );

    // By default, candidate selects v2 of the same pack
    expect(screen.getByTestId("added-requirements-list")).toHaveTextContent("SYNTH-RES-004");
    expect(screen.getByTestId("removed-requirements-list")).toHaveTextContent("SYNTH-RES-003");
    expect(screen.getByTestId("changed-pins-list")).toHaveTextContent("SYNTH-RES-002");
    expect(screen.getByTestId("unchanged-requirements-list")).toHaveTextContent("SYNTH-RES-001");
  });

  it("renders optgroups grouped by framework pack identity in candidate selector", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector workspace={mockWorkspace} />
      </I18nProvider>
    );

    const select = screen.getByTestId("candidate-version-select");
    const optgroups = select.querySelectorAll("optgroup");
    expect(optgroups.length).toBeGreaterThanOrEqual(2);
  });

  it("synchronizes candidate version with selectedCandidateVersionId prop", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector
          workspace={mockWorkspace}
          selectedCandidateVersionId="iso-v1"
        />
      </I18nProvider>
    );

    const select = screen.getByTestId("candidate-version-select") as HTMLSelectElement;
    expect(select.value).toBe("iso-v1");
    expect(screen.getByTestId("cross-pack-notice")).toBeInTheDocument();
  });

  it("renders candidate unavailable notice when selectedCandidateVersionId does not exist in manifest without falling back to packs[0]", () => {
    render(
      <I18nProvider>
        <FrameworkVersionInspector
          workspace={mockWorkspace}
          selectedCandidateVersionId="non-existent-pack-id"
        />
      </I18nProvider>
    );

    const notice = screen.getByTestId("candidate-unavailable-notice");
    expect(notice).toBeInTheDocument();
    expect(notice).toHaveTextContent("non-existent-pack-id");
    expect(screen.queryByTestId("bundle-digest-comparison")).not.toBeInTheDocument();
  });
});