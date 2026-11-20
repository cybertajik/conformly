import { ConflictError, ForbiddenError, UnauthorizedError } from "./api";
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import * as api from "./operations-api";
import * as taskApi from "./task-api";
import { Policy, PolicyAcknowledgement, PolicyRevision } from "./operations-types";
import { ComplianceTask } from "./task-types";
import { PolicyWorkspaceV2 } from "./PolicyWorkspaceV2";

describe("PolicyWorkspaceV2 Component", () => {
  const basePublishedPolicy: Policy = {
    id: "pol-pub",
    tenant_id: "ten-1",
    title: "Workforce Security Policy",
    description: "Mandatory security policy",
    version: 1,
    version_string: "1.0",
    review_cycle_days: 365,
    status: "published",
    classification: "Internal",
    content: "Policy text content",
    owner_user_id: "owner-1",
    approved_by_user_id: "approver-1",
    approved_at: "2026-10-29T10:00:00Z",
    next_review_due: "2026-11-20T00:00:00Z",
    created_at: "2026-10-29T10:00:00Z",
    updated_at: "2026-10-29T10:00:00Z",
  };

  const dummyPolicy: Policy = {
    id: "pol-1",
    tenant_id: "ten-1",
    title: "Access Control Policy",
    description: "Policy governing passwords and 2FA",
    version_string: "1.0",
    status: "draft",
    owner_user_id: "user-alice",
    approved_by_user_id: null,
    approved_at: null,
    review_cycle_days: 365,
    next_review_due: null,
    version: 1,
    content: "# Access Control Policy\nAll employees must use 2FA.",
    classification: "Internal",
    created_at: "2026-10-29T10:00:00Z",
    updated_at: "2026-10-29T10:00:00Z",
  };

  const dummyRevision: PolicyRevision = {
    id: "rev-1",
    tenant_id: "ten-1",
    policy_id: "pol-1",
    revision_number: 1,
    version_string: "1.0",
    title: "Access Control Policy",
    description: "Initial draft",
    content: "Body content",
    classification: "Internal",
    status: "draft",
    created_by_user_id: "user-alice",
    approved_by_user_id: null,
    approved_at: null,
    change_summary: "Initial baseline creation",
    created_at: "2026-10-29T10:00:00Z",
  };

  const dummyAck: PolicyAcknowledgement = {
    id: "ack-1",
    tenant_id: "ten-1",
    policy_id: "pol-1",
    policy_revision_id: "rev-1",
    user_id: "current-user",
    acknowledged_at: "2026-10-29T11:00:00Z",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "fetchPolicyRevisions").mockResolvedValue([dummyRevision]);
    vi.spyOn(api, "fetchPolicyAcknowledgements").mockResolvedValue([dummyAck]);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders policies list and filters by status", async () => {
    const publishedPolicy: Policy = {
      ...dummyPolicy,
      id: "pol-2",
      title: "Data Retention Policy",
      status: "published",
      version: 2,
    };

    render(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          currentUserId="current-user"
          policies={[dummyPolicy, publishedPolicy]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("policy-workspace")).toBeInTheDocument();
    expect(screen.getByText("Access Control Policy")).toBeInTheDocument();
    expect(screen.getByText("Data Retention Policy")).toBeInTheDocument();

    // Filter by draft
    fireEvent.change(screen.getByTestId("policy-status-filter"), { target: { value: "draft" } });
    expect(screen.getByText("Access Control Policy")).toBeInTheDocument();
    expect(screen.queryByText("Data Retention Policy")).not.toBeInTheDocument();
  });

  it("renders read-only notice for unauthorized management roles and denies administrator role", () => {
    // Read-only role (e.g. employee)
    const { rerender } = render(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="employee"
          policies={[dummyPolicy]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("policies-readonly-notice")).toBeInTheDocument();
    expect(screen.queryByTestId("new-policy-btn")).not.toBeInTheDocument();

    // Administrator role (explicitly denied access to compliance policies)
    rerender(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="administrator"
          policies={[dummyPolicy]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("policy-workspace-denied")).toBeInTheDocument();
  });

  it("executes lifecycle: create -> draft edit -> submit review", async () => {
    const onPolicyCreated = vi.fn();
    const onPolicyMutated = vi.fn();

    vi.spyOn(api, "createPolicy").mockResolvedValue({
      ...dummyPolicy,
      id: "pol-new",
      title: "New Information Policy",
    });

    render(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          currentUserId="current-user"
          policies={[dummyPolicy]}
          onPolicyCreated={onPolicyCreated}
          onPolicyMutated={onPolicyMutated}
        />
      </I18nProvider>
    );

    // Open create form
    fireEvent.click(screen.getByTestId("new-policy-btn"));
    expect(screen.getByTestId("new-policy-form-card")).toBeInTheDocument();

    // Fill and submit
    fireEvent.change(screen.getByTestId("new-policy-title-input"), {
      target: { value: "New Information Policy" },
    });
    fireEvent.click(screen.getByTestId("submit-create-policy-btn"));

    await waitFor(() => {
      expect(onPolicyCreated).toHaveBeenCalled();
    });

    // Select existing draft policy
    fireEvent.click(screen.getByTestId("policy-row-pol-1"));
    expect(screen.getByTestId("detail-policy-status")).toHaveTextContent("draft");

    // Edit content and save draft
    vi.spyOn(api, "updatePolicy").mockResolvedValue({
      ...dummyPolicy,
      content: "Updated draft content",
      version: 2,
    });

    fireEvent.change(screen.getByTestId("edit-policy-content-input"), {
      target: { value: "Updated draft content" },
    });
    fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

    await waitFor(() => {
      expect(onPolicyMutated).toHaveBeenCalled();
    });

    // Submit for review
    vi.spyOn(api, "submitPolicyReview").mockResolvedValue({
      ...dummyPolicy,
      status: "in_review",
      version: 3,
    });

    fireEvent.click(screen.getByTestId("submit-review-policy-btn"));
    await waitFor(() => {
      expect(onPolicyMutated).toHaveBeenCalled();
    });
  });

  it("independent 2-person approval: owner cannot self-approve; distinct reviewer approves", async () => {
    const inReviewPolicy: Policy = {
      ...dummyPolicy,
      status: "in_review",
      owner_user_id: "user-author",
      version: 2,
    };

    // Render as author
    const { rerender } = render(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          currentUserId="user-author"
          policies={[inReviewPolicy]}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("policy-row-pol-1"));
    fireEvent.click(screen.getByTestId("approve-policy-btn"));

    // Denied client-side before calling backend
    expect(screen.getByTestId("policy-action-error")).toHaveTextContent(
      /Independent 2-person approval required/i
    );

    // Switch to distinct reviewer
    const onPolicyMutated = vi.fn();
    vi.spyOn(api, "approvePolicy").mockResolvedValue({
      ...inReviewPolicy,
      status: "approved",
      approved_by_user_id: "user-reviewer",
      version: 3,
    });

    rerender(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          currentUserId="user-reviewer"
          policies={[inReviewPolicy]}
          onPolicyMutated={onPolicyMutated}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("approve-policy-btn"));
    await waitFor(() => {
      expect(onPolicyMutated).toHaveBeenCalled();
      expect(screen.getByTestId("policy-action-success")).toHaveTextContent(
        /Policy approved successfully/i
      );
    });
  });

  it("handles publish, archive, and workforce acknowledgement lifecycle", async () => {
    const approvedPolicy: Policy = {
      ...dummyPolicy,
      status: "approved",
      version: 3,
    };

    const onPolicyMutated = vi.fn();
    vi.spyOn(api, "publishPolicy").mockResolvedValue({
      ...approvedPolicy,
      status: "published",
      version: 4,
    });

    const { rerender } = render(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          currentUserId="current-user"
          policies={[approvedPolicy]}
          onPolicyMutated={onPolicyMutated}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("policy-row-pol-1"));
    fireEvent.click(screen.getByTestId("publish-policy-btn"));

    await waitFor(() => {
      expect(onPolicyMutated).toHaveBeenCalled();
    });

    // Published state displays acknowledge button when unacknowledged
    vi.spyOn(api, "fetchPolicyAcknowledgements").mockResolvedValue([]);
    const publishedPolicy: Policy = {
      ...approvedPolicy,
      status: "published",
      version: 4,
    };

    rerender(
      <I18nProvider>
        <PolicyWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          currentUserId="current-user"
          policies={[publishedPolicy]}
          onPolicyMutated={onPolicyMutated}
        />
      </I18nProvider>
    );

    const ackSpy = vi.spyOn(api, "acknowledgePolicy").mockResolvedValue(dummyAck);
    await waitFor(() => {
      const btn = screen.getByTestId("acknowledge-policy-btn");
      expect(btn).toBeInTheDocument();
      expect(btn).not.toBeDisabled();
    });
    fireEvent.click(screen.getByTestId("acknowledge-policy-btn"));
    await waitFor(() => {
      expect(ackSpy).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByTestId("policy-action-success")).toHaveTextContent(
        /Policy acknowledged successfully/i
      );
    });
  });

  describe("B04 Repair 2 Regressions", () => {
    const restrictedListPolicy: Policy = {
      id: "pol-restricted",
      tenant_id: "ten-1",
      title: "Encrypted Keys Policy",
      description: "Secrets management",
      version_string: "1.0",
      status: "draft",
      owner_user_id: "current-user",
      approved_by_user_id: null,
      approved_at: null,
      review_cycle_days: 365,
      next_review_due: null,
      version: 1,
      content: "", // List row has empty/omitted content
      classification: "Restricted",
      created_at: "2026-10-29T10:00:00Z",
      updated_at: "2026-10-29T10:00:00Z",
    };

    it("Priority 1: Restricted listrow detailGET rejects; editing only title cannot issue destructive restricted_content=''", async () => {
      // Mock detail failure
      vi.spyOn(api, "fetchPolicy").mockRejectedValue(new Error("Network failed"));
      const updateSpy = vi.spyOn(api, "updatePolicy").mockResolvedValue({
        ...restrictedListPolicy,
        title: "Encrypted Keys Policy Updated",
      });

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[restrictedListPolicy]}
          />
        </I18nProvider>
      );

      // Select policy
      fireEvent.click(screen.getByTestId("policy-row-pol-restricted"));

      // Wait for detail error banner
      await waitFor(() => {
        expect(screen.getByTestId("policy-detail-error")).toBeInTheDocument();
      });

      // Body input must be unavailable / disabled
      const bodyInput = screen.getByTestId("edit-policy-content-input");
      expect(bodyInput).toBeDisabled();

      // Edit only title
      fireEvent.change(screen.getByTestId("edit-policy-title"), {
        target: { value: "Encrypted Keys Policy Updated" },
      });

      // Save draft
      fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalled();
      });

      const sentPayload = updateSpy.mock.calls[0][3];
      // Payload MUST NOT contain destructive restricted_content: ""
      expect(sentPayload.restricted_content).toBeUndefined();
      expect(sentPayload.content).toBeUndefined();
      expect(sentPayload.title).toBe("Encrypted Keys Policy Updated");
    });

    it("Priority 1: Retry returns protected body, editor shows it and metadata-only edit preserves it", async () => {
      // First attempt fails, second succeeds with protected body
      vi.spyOn(api, "fetchPolicy")
        .mockRejectedValueOnce(new Error("Timeout"))
        .mockResolvedValueOnce({
          ...restrictedListPolicy,
          restricted_content: "ENC:super-secret-body-v1",
        });

      const updateSpy = vi.spyOn(api, "updatePolicy").mockResolvedValue({
        ...restrictedListPolicy,
        title: "Encrypted Keys Policy (Renamed)",
        restricted_content: "ENC:super-secret-body-v1",
      });

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[restrictedListPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-restricted"));

      await waitFor(() => {
        expect(screen.getByTestId("retry-policy-detail-btn")).toBeInTheDocument();
      });

      // Click retry
      fireEvent.click(screen.getByTestId("retry-policy-detail-btn"));

      await waitFor(() => {
        const bodyInput = screen.getByTestId("edit-policy-content-input") as HTMLTextAreaElement;
        expect(bodyInput.value).toBe("ENC:super-secret-body-v1");
      });

      // Metadata-only edit
      fireEvent.change(screen.getByTestId("edit-policy-title"), {
        target: { value: "Encrypted Keys Policy (Renamed)" },
      });
      fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalled();
      });

      const sentPayload = updateSpy.mock.calls[0][3];
      // Protected body is preserved in restricted_content
      expect(sentPayload.restricted_content).toBe("ENC:super-secret-body-v1");
      expect(sentPayload.content).toBe("");
    });

    it("Priority 1: Loaded protected body -> edit -> Discard restores correct body, not list placeholder", async () => {
      vi.spyOn(api, "fetchPolicy").mockResolvedValue({
        ...restrictedListPolicy,
        restricted_content: "ENC:original-protected-body",
      });

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[restrictedListPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-restricted"));

      await waitFor(() => {
        const bodyInput = screen.getByTestId("edit-policy-content-input") as HTMLTextAreaElement;
        expect(bodyInput.value).toBe("ENC:original-protected-body");
      });

      // Edit body
      fireEvent.change(screen.getByTestId("edit-policy-content-input"), {
        target: { value: "ENC:corrupted-draft" },
      });
      expect(screen.getByTestId("discard-policy-changes-btn")).toBeInTheDocument();

      // Discard changes
      fireEvent.click(screen.getByTestId("discard-policy-changes-btn"));

      // Must restore the original loaded protected body, NOT empty string list placeholder
      const restoredInput = screen.getByTestId("edit-policy-content-input") as HTMLTextAreaElement;
      expect(restoredInput.value).toBe("ENC:original-protected-body");
    });

    it("Priority 1: Public/Internal -> Restricted upgrade clears plaintext slot and routes to restricted_content", async () => {
      const publicPolicy: Policy = {
        ...dummyPolicy,
        classification: "Public",
        content: "Open public disclosure",
      };

      vi.spyOn(api, "fetchPolicy").mockResolvedValue(publicPolicy);
      const updateSpy = vi.spyOn(api, "updatePolicy").mockResolvedValue({
        ...publicPolicy,
        classification: "Restricted",
        restricted_content: "ENC:new-restricted-body",
        content: "",
      });

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[publicPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-1"));

      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-classification")).toHaveValue("Public");
      });

      // Upgrade classification to Restricted
      fireEvent.change(screen.getByTestId("edit-policy-classification"), {
        target: { value: "Restricted" },
      });
      // Enter new restricted content
      fireEvent.change(screen.getByTestId("edit-policy-content-input"), {
        target: { value: "ENC:new-restricted-body" },
      });

      fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalled();
      });

      const sent = updateSpy.mock.calls[0][3];
      expect(sent.classification).toBe("Restricted");
      expect(sent.restricted_content).toBe("ENC:new-restricted-body");
      expect(sent.content).toBe(""); // Plaintext slot cleared!
    });

    it("Priority 2: Load detail v1/edit; rerender list v2; Save must send expected_version: 1", async () => {
      vi.spyOn(api, "fetchPolicy").mockResolvedValue({
        ...dummyPolicy,
        version: 1,
        content: "v1 body",
      });
      const updateSpy = vi.spyOn(api, "updatePolicy").mockResolvedValue({
        ...dummyPolicy,
        version: 2,
      });

      const { rerender } = render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[dummyPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-1"));

      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-content-input")).toHaveValue("v1 body");
      });

      // Edit content
      fireEvent.change(screen.getByTestId("edit-policy-content-input"), {
        target: { value: "v1 dirty edit" },
      });

      // Background poll updates list prop to v2
      const updatedListPolicy: Policy = {
        ...dummyPolicy,
        version: 2,
        title: "Title updated by peer",
      };

      rerender(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[updatedListPolicy]}
          />
        </I18nProvider>
      );

      // Save draft - must still send expected_version 1 (pinned from draft base), NOT 2 from list!
      fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalled();
      });

      const sent = updateSpy.mock.calls[0][3];
      expect(sent.expected_version).toBe(1);
    });

    it("Priority 2: 409 conflict retains draft without automatic retry; explicit reload resolves", async () => {
      vi.spyOn(api, "fetchPolicy")
        .mockResolvedValueOnce({
          ...dummyPolicy,
          version: 1,
          content: "v1 body",
        })
        .mockResolvedValueOnce({
          ...dummyPolicy,
          version: 2,
          content: "v2 body from peer",
        });

      vi.spyOn(api, "updatePolicy").mockRejectedValue(
        new ConflictError("Version conflict: resource modified by another actor")
      );

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[dummyPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-1"));

      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-content-input")).toHaveValue("v1 body");
      });

      fireEvent.change(screen.getByTestId("edit-policy-content-input"), {
        target: { value: "conflicted user draft" },
      });

      fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

      // 409 error banner shown, draft retained
      await waitFor(() => {
        expect(screen.getByTestId("policy-action-error")).toHaveTextContent(/Conflict/i);
        expect(screen.getByTestId("policy-reload-btn")).toBeInTheDocument();
      });

      expect(screen.getByTestId("edit-policy-content-input")).toHaveValue("conflicted user draft");

      // User explicitly reloads current version
      fireEvent.click(screen.getByTestId("policy-reload-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-content-input")).toHaveValue("v2 body from peer");
      });
    });

    it("Priority 3: Guarded record switch on dirty draft keeps draft on cancel and switches on confirm", async () => {
      const secondPolicy: Policy = {
        ...dummyPolicy,
        id: "pol-2",
        title: "Vendor Security Policy",
      };

      vi.spyOn(api, "fetchPolicy").mockImplementation(async (_tenant, _token, id) => {
        if (id === "pol-1") return dummyPolicy;
        return secondPolicy;
      });

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            currentUserId="current-user"
            policies={[dummyPolicy, secondPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-1"));

      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-title")).toHaveValue("Access Control Policy");
      });

      // Make dirty edit
      fireEvent.change(screen.getByTestId("edit-policy-title"), {
        target: { value: "Dirty Unsaved Title" },
      });

      // Click second policy
      fireEvent.click(screen.getByTestId("policy-row-pol-2"));

      // Dirty guard banner must appear
      expect(screen.getByTestId("dirty-switch-guard")).toBeInTheDocument();
      expect(screen.getByTestId("edit-policy-title")).toHaveValue("Dirty Unsaved Title");

      // Cancel switch
      fireEvent.click(screen.getByTestId("cancel-switch-btn"));
      expect(screen.queryByTestId("dirty-switch-guard")).not.toBeInTheDocument();
      expect(screen.getByTestId("edit-policy-title")).toHaveValue("Dirty Unsaved Title");

      // Try switch again and confirm discard
      fireEvent.click(screen.getByTestId("policy-row-pol-2"));
      expect(screen.getByTestId("dirty-switch-guard")).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("confirm-discard-switch-btn"));

      // Now switched to pol-2
      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-title")).toHaveValue("Vendor Security Policy");
      });
    });

    it("Priority 4: Uncertain create on network failure disables submit and reconciles with server", async () => {
      vi.spyOn(api, "createPolicy").mockRejectedValue(new TypeError("Failed to fetch"));
      vi.spyOn(api, "fetchPolicies").mockResolvedValue([
        {
          ...dummyPolicy,
          id: "pol-recovered",
          title: "Network Unstable Policy",
          description: "Testing reconciliation",
          classification: "Internal",
        },
      ]);

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="owner"
            currentUserId="current-user"
            policies={[]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("new-policy-btn"));
      fireEvent.change(screen.getByTestId("new-policy-title-input"), {
        target: { value: "Network Unstable Policy" },
      });
      fireEvent.change(screen.getByTestId("new-policy-desc-input"), {
        target: { value: "Testing reconciliation" },
      });

      fireEvent.click(screen.getByTestId("submit-create-policy-btn"));

      // Uncertain banner appears and submit button is disabled
      await waitFor(() => {
        expect(screen.getByTestId("policy-uncertain-create-banner")).toBeInTheDocument();
        expect(screen.getByTestId("submit-create-policy-btn")).toBeDisabled();
      });

      // Click check server
      fireEvent.click(screen.getByTestId("reconcile-policy-btn"));

      // Match found, adopt button appears
      await waitFor(() => {
        expect(screen.getByTestId("confirm-reconcile-policy-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("confirm-reconcile-policy-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("policy-action-success")).toHaveTextContent(/verified as created|reconciled/i);
      });
    });

    it("P1 Regression: two consecutive metadata saves on unavailable body omit restricted_content in both saves", async () => {
      const restrictedListPolicy: Policy = {
        id: "pol-restricted",
        tenant_id: "ten-1",
        title: "Encrypted Keys Policy",
        description: "Restricted policy without list-level body",
        version: 1,
        version_string: "1.0",
        review_cycle_days: 365,
        status: "draft",
        classification: "Restricted",
        content: null,
        owner_user_id: "user-1",
        approved_by_user_id: null,
        approved_at: null,
        next_review_due: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      };

      vi.spyOn(api, "fetchPolicy").mockRejectedValue(new Error("500 Internal Server Error"));
      const updateSpy = vi.spyOn(api, "updatePolicy")
        .mockResolvedValueOnce({
          ...restrictedListPolicy,
          title: "Encrypted Keys Policy (Save 1)",
          version: 2,
        })
        .mockResolvedValueOnce({
          ...restrictedListPolicy,
          title: "Encrypted Keys Policy (Save 2)",
          version: 3,
        });

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[restrictedListPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-restricted"));

      await waitFor(() => {
        expect(screen.getByTestId("policy-body-unavailable-banner")).toBeInTheDocument();
      });

      // First metadata-only save
      fireEvent.change(screen.getByTestId("edit-policy-title"), {
        target: { value: "Encrypted Keys Policy (Save 1)" },
      });
      fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalledTimes(1);
      });

      const payload1 = updateSpy.mock.calls[0][3];
      expect(payload1.restricted_content).toBeUndefined();
      expect(payload1.content).toBeUndefined();

      // Second consecutive metadata-only save
      fireEvent.change(screen.getByTestId("edit-policy-title"), {
        target: { value: "Encrypted Keys Policy (Save 2)" },
      });
      fireEvent.click(screen.getByTestId("save-policy-draft-btn"));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalledTimes(2);
      });

      const payload2 = updateSpy.mock.calls[1][3];
      // Crucial P1 assertion: second save must NOT send restricted_content=""
      expect(payload2.restricted_content).toBeUndefined();
      expect(payload2.content).toBeUndefined();
    });

    it("creates follow-up task linked to policy after user confirmation", async () => {
      vi.spyOn(api, "fetchPolicy").mockResolvedValue(basePublishedPolicy);
      const createTaskSpy = vi.spyOn(taskApi, "createTask").mockResolvedValue({
        id: "task-followup-1",
        tenant_id: "ten-1",
        title: "Follow-up: Workforce Security Policy",
        description: "Follow-up task for policy Workforce Security Policy",
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "medium",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-pub",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      });

      const onTaskCreatedSpy = vi.fn();

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
            onTaskCreated={onTaskCreatedSpy}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));

      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });

      // Click create follow-up task
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));

      expect(screen.getByTestId("followup-task-modal")).toBeInTheDocument();
      expect(screen.getByTestId("followup-task-policy-id")).toHaveValue("pol-pub");
      expect(screen.getByTestId("followup-task-title-input")).toHaveValue("Follow-up: Workforce Security Policy");

      // Confirm creation
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(createTaskSpy).toHaveBeenCalledWith(
          "ten-1",
          "tok-1",
          expect.objectContaining({
            policy_id: "pol-pub",
            title: "Follow-up: Workforce Security Policy",
          }),
          expect.anything()
        );
        expect(onTaskCreatedSpy).toHaveBeenCalled();
        expect(screen.queryByTestId("followup-task-modal")).not.toBeInTheDocument();
      });
    });
      it("protects against duplicate follow-up task submission after network error with scoped reconcile and adopt", async () => {
      

      vi.spyOn(api, "fetchPolicy").mockResolvedValue(basePublishedPolicy);
      // Simulate network error on create
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network failed POST"));

      const existingTaskOnServer: ComplianceTask = {
        id: "task-server-1",
        tenant_id: "ten-1",
        title: "Follow-up: Workforce Security Policy",
        description: "Follow-up task for policy Workforce Security Policy",
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "medium",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-pub",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      };

      // Mock fetchTasks for reconciliation returning the task committed on server
      const fetchTasksSpy = vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([existingTaskOnServer]);
      const onTaskCreatedSpy = vi.fn();

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
            onTaskCreated={onTaskCreatedSpy}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));

      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      expect(screen.getByTestId("followup-task-modal")).toBeInTheDocument();

      // Attempt create
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      // Uncertain banner appears and create button is disabled
      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
        expect(screen.getByTestId("confirm-create-followup-task-btn")).toBeDisabled();
      });

      // Click reconcile with server
      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      // Reconciled matching task shown
      await waitFor(() => {
        expect(fetchTasksSpy).toHaveBeenCalledWith("ten-1", "tok-1", expect.objectContaining({ limit: 100 }), expect.anything());
        expect(screen.getByTestId("followup-reconciled-match")).toBeInTheDocument();
        expect(screen.getByTestId("adopt-followup-task-btn")).toBeInTheDocument();
      });

      // Adopt existing task without duplicate POST
      fireEvent.click(screen.getByTestId("adopt-followup-task-btn"));

      expect(onTaskCreatedSpy).toHaveBeenCalledWith(existingTaskOnServer);
      expect(screen.queryByTestId("followup-task-modal")).not.toBeInTheDocument();
    });

    it("allows resubmit or abandon when no matching follow-up task is found on server", async () => {
      

      vi.spyOn(api, "fetchPolicy").mockResolvedValue(basePublishedPolicy);
      const createTaskSpy = vi.spyOn(taskApi, "createTask")
        .mockRejectedValueOnce(new Error("Network failed"))
        .mockResolvedValueOnce({
          id: "task-resubmitted",
          tenant_id: "ten-1",
          title: "Follow-up: Workforce Security Policy",
          description: "Retry succeed",
          due_date: "2026-11-20T00:00:00Z",
          status: "pending",
          priority: "medium",
          assignee_user_id: null,
          control_type: null,
          control_id: null,
          evidence_id: null,
          policy_id: "pol-pub",
          version: 1,
          completed_at: null,
          completed_by_user_id: null,
          created_at: "2026-10-29T10:00:00Z",
          updated_at: "2026-10-29T10:00:00Z",
        });

      // Server returns empty list on reconciliation
      vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([]);

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      // Reconcile
      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-reconciled-nomatch")).toBeInTheDocument();
        expect(screen.getByTestId("resubmit-followup-btn")).toBeInTheDocument();
      });

      // Click resubmit
      fireEvent.click(screen.getByTestId("resubmit-followup-btn"));

      await waitFor(() => {
        expect(createTaskSpy).toHaveBeenCalledTimes(2);
        expect(screen.queryByTestId("followup-task-modal")).not.toBeInTheDocument();
      });
    });

    it("clears uncertain follow-up state on policy context change", async () => {
      const secondPolicy: Policy = {
        ...basePublishedPolicy,
        id: "pol-pub-2",
        title: "Second Published Policy",
      };

      vi.spyOn(api, "fetchPolicy")
        .mockResolvedValueOnce(basePublishedPolicy)
        .mockResolvedValueOnce(secondPolicy);
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network failed"));

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy, secondPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      // Close modal
      fireEvent.click(screen.getByTestId("cancel-create-followup-task-btn"));

      // Switch policy context to secondPolicy
      fireEvent.click(screen.getByTestId("policy-row-pol-pub-2"));

      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-title")).toHaveValue("Second Published Policy");
      });

      // Reopen modal: uncertain state must be reset
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      expect(screen.queryByTestId("followup-uncertain-banner")).not.toBeInTheDocument();
      expect(screen.getByTestId("confirm-create-followup-task-btn")).not.toBeDisabled();
    });
    it("handles ambiguous multiple matches during followup task reconciliation", async () => {
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network connection dropped"));

      const task1: ComplianceTask = {
        id: "task-1",
        tenant_id: "ten-1",
        title: "Follow-up: Workforce Security Policy",
        description: "Follow-up task for policy Workforce Security Policy",
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "medium",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-pub",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      };
      const task2: ComplianceTask = {
        ...task1,
        id: "task-2",
      };

      vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([task1, task2]);

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-reconciled-ambiguous")).toBeInTheDocument();
        expect(screen.queryByTestId("adopt-followup-task-btn")).not.toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("abandon-followup-btn"));
      expect(screen.queryByTestId("followup-task-modal")).not.toBeInTheDocument();
    });

    it("handles incomplete query (100 items) during followup reconciliation", async () => {
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("504 Gateway Timeout"));

      // 100 unrelated tasks
      const hundredTasks: ComplianceTask[] = Array.from({ length: 100 }, (_, i) => ({
        id: `task-unrelated-${i}`,
        tenant_id: "ten-1",
        title: `Unrelated Task ${i}`,
        description: "Other",
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "low",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-other",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      }));

      vi.spyOn(taskApi, "fetchTasks").mockResolvedValue(hundredTasks);

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-reconciled-incomplete")).toBeInTheDocument();
      });
    });

    it("treats definite 403 Forbidden on createFollowupTask as definite denial rather than uncertain success", async () => {
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new ForbiddenError("Access forbidden (403)"));

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("followup-uncertain-banner")).not.toBeInTheDocument();
        expect(screen.getByText("Access forbidden (403)")).toBeInTheDocument();
      });
    });


    it("does not match same-day different-time tasks or different assignees/references during reconciliation", async () => {
      // Create attempted task with due date 2026-11-20T00:00:00Z and unassigned
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network failure"));

      // Server has task on same day but different time (14:30), or different assignee
      const differentTimeTask: ComplianceTask = {
        id: "task-diff-time",
        tenant_id: "ten-1",
        title: "Follow-up for Access Policy",
        description: "Review and update access procedures",
        due_date: "2026-11-20T14:30:00Z",
        status: "pending",
        priority: "high",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-pub",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      };

      const differentOwnerTask: ComplianceTask = {
        ...differentTimeTask,
        id: "task-diff-owner",
        due_date: "2026-11-20T00:00:00Z",
        assignee_user_id: "other-user-99",
      };

      const differentRefTask: ComplianceTask = {
        ...differentTimeTask,
        id: "task-diff-ref",
        due_date: "2026-11-20T00:00:00Z",
        control_id: "ctrl-99",
      };

      vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([differentTimeTask, differentOwnerTask, differentRefTask]);

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));

      fireEvent.change(screen.getByTestId("followup-task-due-input"), { target: { value: "2026-11-20" } });
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      // Must NOT match any of the different-time, different-owner, or different-ref tasks
      await waitFor(() => {
        expect(screen.getByTestId("followup-reconciled-nomatch")).toBeInTheDocument();
      });
    });

    it("discovers matching task beyond first 100 via bounded multi-page fetching", async () => {
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network failure"));

      // Page 1 has 100 non-matching tasks
      const page1Tasks: ComplianceTask[] = Array.from({ length: 100 }, (_, i) => ({
        id: `dummy-${i + 1}`,
        tenant_id: "ten-1",
        title: `Unrelated Task ${i + 1}`,
        description: `Description ${i + 1}`,
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "medium",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-other",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      }));

      // Page 2 has the matching task and is under 100 items (so search terminates cleanly)
      const matchingTask: ComplianceTask = {
        id: "task-match-p2",
        tenant_id: "ten-1",
        title: "Follow-up for Access Policy",
        description: "Review and update access procedures",
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "medium",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-pub",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      };

      vi.spyOn(taskApi, "fetchTasks").mockImplementation(async (_, __, opts) => {
        if (opts?.offset === 100) {
          return [matchingTask];
        }
        return page1Tasks;
      });

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.change(screen.getByTestId("followup-task-title-input"), { target: { value: "Follow-up for Access Policy" } });
      fireEvent.change(screen.getByTestId("followup-task-desc-input"), { target: { value: "Review and update access procedures" } });
      fireEvent.change(screen.getByTestId("followup-task-due-input"), { target: { value: "2026-11-20" } });
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      // Should fetch page 2 and find matching task
      await waitFor(() => {
        expect(screen.getByTestId("followup-reconciled-match")).toBeInTheDocument();
        expect(screen.getByText("Matching task found on server: Follow-up for Access Policy")).toBeInTheDocument();
      });
    });

    it("marks ambiguous when multiple matching tasks exist across pages", async () => {
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network failure"));

      const match1: ComplianceTask = {
        id: "task-match-1",
        tenant_id: "ten-1",
        title: "Follow-up for Access Policy",
        description: "Review and update access procedures",
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "medium",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-pub",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      };

      const match2: ComplianceTask = {
        ...match1,
        id: "task-match-2",
      };

      vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([match1, match2]);

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.change(screen.getByTestId("followup-task-title-input"), { target: { value: "Follow-up for Access Policy" } });
      fireEvent.change(screen.getByTestId("followup-task-desc-input"), { target: { value: "Review and update access procedures" } });
      fireEvent.change(screen.getByTestId("followup-task-due-input"), { target: { value: "2026-11-20" } });
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-reconciled-ambiguous")).toBeInTheDocument();
      });
    });

    it("does not allow pending follow-up reconciliation from policy A to leak or update policy B when policy changes", async () => {
      let resolvePolicyAFetch!: (val: ComplianceTask[]) => void;
      const fetchTasksPromiseA = new Promise<ComplianceTask[]>((res) => { resolvePolicyAFetch = res; });

      const policyA: Policy = {
        ...basePublishedPolicy,
        id: "pol-A",
        title: "Policy A",
      };
      const policyB: Policy = {
        ...basePublishedPolicy,
        id: "pol-B",
        title: "Policy B",
      };

      vi.spyOn(api, "fetchPolicy").mockImplementation(async (_tenant, _token, id) => {
        if (id === "pol-A") return policyA;
        return policyB;
      });

      // Make createTask fail with uncertain error on policy A
      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network connection dropped"));

      // Reconciliation fetch for policy A will return matching task for A
      const matchingTaskA: ComplianceTask = {
        id: "task-server-A",
        tenant_id: "ten-1",
        title: "Follow-up: Policy A",
        description: "Follow-up task for policy Policy A",
        due_date: "2026-11-20T00:00:00Z",
        status: "pending",
        priority: "medium",
        assignee_user_id: null,
        control_type: null,
        control_id: null,
        evidence_id: null,
        policy_id: "pol-A",
        version: 1,
        completed_at: null,
        completed_by_user_id: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      };

      vi.spyOn(taskApi, "fetchTasks").mockReturnValue(fetchTasksPromiseA);

      render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[policyA, policyB]}
          />
        </I18nProvider>
      );

      // Select Policy A
      fireEvent.click(screen.getByTestId("policy-row-pol-A"));

      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      expect(screen.getByTestId("followup-task-modal")).toBeInTheDocument();

      // Submit create follow-up task on policy A -> enters uncertain state
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));
      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      // Start reconciliation on policy A
      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      // Now switch selected policy to Policy B while reconciliation is in flight
      fireEvent.click(screen.getByTestId("policy-row-pol-B"));

      await waitFor(() => {
        expect(screen.getByTestId("edit-policy-title")).toHaveValue("Policy B");
      });

      // Policy A's reconciliation query resolves with task for A
      resolvePolicyAFetch([matchingTaskA]);

      await new Promise((r) => setTimeout(r, 50));

      // Under Policy B, Policy A's matching task or uncertain state must NOT appear!
      expect(screen.queryByTestId("followup-reconciled-match")).not.toBeInTheDocument();
      expect(screen.queryByTestId("followup-uncertain-banner")).not.toBeInTheDocument();
    });

    it("does not call onSessionExpired or report error when unmounted or switched during follow-up reconciliation", async () => {
      let rejectTasksFetch!: (err: unknown) => void;
      const fetchTasksPromise = new Promise<ComplianceTask[]>((_, rej) => { rejectTasksFetch = rej; });

      vi.spyOn(taskApi, "createTask").mockRejectedValue(new Error("Network connection dropped"));
      vi.spyOn(taskApi, "fetchTasks").mockReturnValue(fetchTasksPromise);

      const onSessionExpiredSpy = vi.fn();

      const { unmount } = render(
        <I18nProvider>
          <PolicyWorkspaceV2
            tenantId="ten-1"
            token="tok-1"
            userRole="compliance_manager"
            policies={[basePublishedPolicy]}
            onSessionExpired={onSessionExpiredSpy}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("policy-row-pol-pub"));
      await waitFor(() => {
        expect(screen.getByTestId("create-followup-task-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("create-followup-task-btn"));
      fireEvent.click(screen.getByTestId("confirm-create-followup-task-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("followup-uncertain-banner")).toBeInTheDocument();
      });

      // Start reconciliation
      fireEvent.click(screen.getByTestId("reconcile-followup-btn"));

      // Unmount before fetchTasks settles
      unmount();

      // Reject fetch with 401
      rejectTasksFetch(new UnauthorizedError("Token revoked"));

      await new Promise((r) => setTimeout(r, 50));
      expect(onSessionExpiredSpy).not.toHaveBeenCalled();
    });
  });
});
