import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { ModernWorkspaceShell } from "./ModernWorkspaceShell";
import type { SelectedPackSummary } from "./types";

describe("ModernWorkspaceShell", () => {
  afterEach(() => {
    cleanup();
  });

  const renderWithI18n = (ui: React.ReactElement) => {
    return render(<I18nProvider>{ui}</I18nProvider>);
  };

  it("renders synthetic notice banner, title, subtitle and accessibility landmarks", () => {
    renderWithI18n(
      <ModernWorkspaceShell
        currentRevision={2}
        selectionRevision={1}
        activeStep={1}
        onStepChange={vi.fn()}
      >
        <div data-testid="child-content">Workspace Inner Content</div>
      </ModernWorkspaceShell>
    );

    expect(screen.getByTestId("synthetic-notice-banner")).toBeInTheDocument();
    expect(screen.getByTestId("pill-synthetic")).toHaveTextContent("Synthetic Demo");
    expect(screen.getByTestId("modern-workspace-title")).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /customer onboarding steps/i })).toBeInTheDocument();
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });

  it("displays correct revision badges and toggles unsaved changes indicator", () => {
    const { rerender } = renderWithI18n(
      <ModernWorkspaceShell
        currentRevision={3}
        selectionRevision={2}
        hasUnsavedChanges={false}
        activeStep={1}
        onStepChange={vi.fn()}
      >
        <div>Content</div>
      </ModernWorkspaceShell>
    );

    expect(screen.getByTestId("answers-rev-badge")).toHaveTextContent("3");
    expect(screen.getByTestId("selection-rev-badge")).toHaveTextContent("2");
    expect(screen.queryByTestId("unsaved-changes-indicator")).not.toBeInTheDocument();

    rerender(
      <I18nProvider>
        <ModernWorkspaceShell
          currentRevision={3}
          selectionRevision={2}
          hasUnsavedChanges={true}
          activeStep={1}
          onStepChange={vi.fn()}
        >
          <div>Content</div>
        </ModernWorkspaceShell>
      </I18nProvider>
    );

    expect(screen.getByTestId("unsaved-changes-indicator")).toBeInTheDocument();
  });

  it("handles step navigation click events with active step indication", () => {
    const handleStepChange = vi.fn();
    renderWithI18n(
      <ModernWorkspaceShell
        currentRevision={1}
        selectionRevision={0}
        activeStep={2}
        onStepChange={handleStepChange}
      >
        <div>Content</div>
      </ModernWorkspaceShell>
    );

    const step1Btn = screen.getByTestId("step-btn-1");
    const step2Btn = screen.getByTestId("step-btn-2");
    const step3Btn = screen.getByTestId("step-btn-3");

    expect(step2Btn).toHaveAttribute("aria-current", "step");
    expect(step1Btn).not.toHaveAttribute("aria-current");

    fireEvent.click(step1Btn);
    expect(handleStepChange).toHaveBeenCalledWith(1);

    fireEvent.click(step3Btn);
    expect(handleStepChange).toHaveBeenCalledWith(3);
  });

  it("renders pack adoption state correctly for unadopted, current, and stale adoptions", () => {
    const { rerender } = renderWithI18n(
      <ModernWorkspaceShell
        currentRevision={1}
        selectionRevision={0}
        selectedPackSummary={null}
        activeStep={1}
        onStepChange={vi.fn()}
      >
        <div>Content</div>
      </ModernWorkspaceShell>
    );

    expect(screen.getByTestId("pack-adoption-status")).toHaveTextContent(/No Pack Adopted Yet/i);

    const activePack: SelectedPackSummary = {
      selection_revision: 1,
      evaluation_id: "eval-1",
      pack_version_id: "pack-v1",
      bundle_digest: "abcd1234ef567890abcdef",
      created_at: "2026-10-22T10:00:00Z",
      is_stale: false,
    };

    rerender(
      <I18nProvider>
        <ModernWorkspaceShell
          currentRevision={1}
          selectionRevision={1}
          selectedPackSummary={activePack}
          activeStep={1}
          onStepChange={vi.fn()}
        >
          <div>Content</div>
        </ModernWorkspaceShell>
      </I18nProvider>
    );

    expect(screen.getByTestId("pack-adoption-status")).toHaveTextContent("abcd1234ef");
    expect(screen.queryByText(/Stale/i)).not.toBeInTheDocument();

    const stalePack: SelectedPackSummary = {
      ...activePack,
      is_stale: true,
    };

    rerender(
      <I18nProvider>
        <ModernWorkspaceShell
          currentRevision={2}
          selectionRevision={1}
          selectedPackSummary={stalePack}
          activeStep={1}
          onStepChange={vi.fn()}
        >
          <div>Content</div>
        </ModernWorkspaceShell>
      </I18nProvider>
    );

    expect(screen.getByTestId("pack-adoption-status")).toHaveTextContent(/Stale/i);
  });
  it("derives Step 2 completion from current evaluation, showing stale tag when evaluation is outdated", () => {
    // Case 1: currentRevision > 0 but evaluation is NOT current (e.g. saved but unevaluated)
    const { rerender } = renderWithI18n(
      <ModernWorkspaceShell
        currentRevision={1}
        selectionRevision={0}
        activeStep={1}
        isEvaluationCurrent={false}
        isEvaluationStale={false}
        onStepChange={vi.fn()}
      >
        <div>Content</div>
      </ModernWorkspaceShell>
    );

    const step2Btn = screen.getByTestId("step-btn-2");
    expect(step2Btn).not.toHaveClass("completed");
    expect(step2Btn.querySelector(".mw-step-num")).toHaveTextContent("2");
    expect(screen.queryByTestId("step-2-stale-tag")).not.toBeInTheDocument();

    // Case 2: evaluation is stale (answer revision advanced after evaluation)
    rerender(
      <I18nProvider>
        <ModernWorkspaceShell
          currentRevision={2}
          selectionRevision={0}
          activeStep={1}
          isEvaluationCurrent={false}
          isEvaluationStale={true}
          onStepChange={vi.fn()}
        >
          <div>Content</div>
        </ModernWorkspaceShell>
      </I18nProvider>
    );

    expect(screen.getByTestId("step-btn-2")).not.toHaveClass("completed");
    expect(screen.getByTestId("step-2-stale-tag")).toBeInTheDocument();

    // Case 3: evaluation is current (matches current revision without unsaved edits)
    rerender(
      <I18nProvider>
        <ModernWorkspaceShell
          currentRevision={2}
          selectionRevision={0}
          activeStep={1}
          isEvaluationCurrent={true}
          isEvaluationStale={false}
          onStepChange={vi.fn()}
        >
          <div>Content</div>
        </ModernWorkspaceShell>
      </I18nProvider>
    );

    expect(screen.getByTestId("step-btn-2")).toHaveClass("completed");
    expect(screen.getByTestId("step-btn-2").querySelector(".mw-step-num")).toHaveTextContent("\u2713");
    expect(screen.queryByTestId("step-2-stale-tag")).not.toBeInTheDocument();
  });

  it("avoids nesting a second main landmark and renders region role for workspace content", () => {
    const { container } = renderWithI18n(
      <ModernWorkspaceShell
        currentRevision={0}
        selectionRevision={0}
        activeStep={1}
        onStepChange={vi.fn()}
      >
        <div>Content</div>
      </ModernWorkspaceShell>
    );

    // Verify no <main> element is rendered by ModernWorkspaceShell to prevent nesting inside App's main
    expect(container.querySelector("main")).toBeNull();
    const contentRegion = container.querySelector("#workspace-main-content");
    expect(contentRegion).toHaveAttribute("role", "region");
  });
});
