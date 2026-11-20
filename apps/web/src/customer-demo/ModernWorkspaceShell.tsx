import React, { FC, ReactNode } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { en } from "../i18n/locales/en";
import { LanguageSelector } from "../components/LanguageSelector";
import { SelectedPackSummary } from "./types";
import "./modern-workspace.css";

export interface ModernWorkspaceShellProps {
  title?: string;
  subtitle?: string;
  disclaimer?: string;
  currentRevision: number;
  selectionRevision: number;
  hasUnsavedChanges?: boolean;
  selectedPackSummary?: SelectedPackSummary | null;
  isEvaluationCurrent?: boolean;
  isEvaluationStale?: boolean;
  activeStep: number;
  onStepChange: (step: number) => void;
  children: ReactNode;
}

function useSafeTranslation() {
  try {
    const ctx = useTranslation();
    return { ...ctx, isAvailable: true };
  } catch {
    // Fallback to English dictionary when rendered outside I18nProvider
    return {
      isAvailable: false,
      locale: "en" as const,
      setLocale: () => {},
      t: (key: string, params?: Record<string, string | number>) => {
        const parts = key.split(".");
        let val: unknown = en;
        for (const part of parts) {
          if (val && typeof val === "object" && part in val) {
            val = (val as Record<string, unknown>)[part];
          } else {
            return key;
          }
        }
        if (typeof val === "string" && params) {
          return val.replace(/\{([^{}]+)\}/g, (_, k) =>
            params[k] !== undefined ? String(params[k]) : `{${k}}`
          );
        }
        return typeof val === "string" ? val : key;
      },
    };
  }
}

export const ModernWorkspaceShell: FC<ModernWorkspaceShellProps> = ({
  title,
  subtitle,
  disclaimer,
  currentRevision,
  selectionRevision,
  hasUnsavedChanges = false,
  selectedPackSummary,
  isEvaluationCurrent = false,
  isEvaluationStale = false,
  activeStep,
  onStepChange,
  children,
}) => {
  const translationResult = useSafeTranslation();
  const { t } = translationResult;

  const displayTitle = title || t("customerDemo.title");
  const displaySubtitle = subtitle || t("customerDemo.subtitle");
  const displayDisclaimer = disclaimer || t("customerDemo.syntheticNotice");

  const step1Completed = currentRevision > 0 && !hasUnsavedChanges;
  const step2Completed = isEvaluationCurrent && !hasUnsavedChanges;
  const step3Completed = Boolean(selectedPackSummary && !selectedPackSummary.is_stale);

  return (
    <div className="modern-workspace-root" data-testid="modern-workspace-root">
      {/* Synthetic Demonstration Notice Banner */}
      <div
        className="mw-alert mw-alert-warning"
        role="region"
        aria-label={t("customerDemo.noticeAriaLabel")}
        data-testid="synthetic-notice-banner"
      >
        <div>
          <strong>{t("customerDemo.noticeLabel")}: </strong>
          <span>{displayDisclaimer}</span>
        </div>
      </div>

      {/* Top Application Header */}
      <header className="mw-header" role="banner">
        <div className="mw-header-left">
          <div className="mw-pill-synthetic" data-testid="pill-synthetic">
            <span>{t("customerDemo.syntheticDemo")}</span>
            <span aria-hidden="true">&bull;</span>
            <span>{t("customerDemo.evaluationOnly")}</span>
          </div>
          <h1 className="mw-title" data-testid="modern-workspace-title">{displayTitle}</h1>
          <p className="mw-subtitle">{displaySubtitle}</p>
        </div>

        <div className="mw-header-right">
          {translationResult.isAvailable ? (
            <LanguageSelector />
          ) : (
            <div className="mw-meta-pill" aria-label="Default language">
              <span aria-hidden="true">🇬🇧</span>
              <span>English</span>
            </div>
          )}
        </div>
      </header>

      {/* Step Navigation / Journey Stepper */}
      <nav className="mw-stepper" aria-label={t("customerDemo.stepperAriaLabel")} data-testid="workspace-stepper">
        <button
          type="button"
          className={`mw-step-btn ${activeStep === 1 ? "active" : ""} ${step1Completed ? "completed" : ""}`}
          onClick={() => onStepChange(1)}
          aria-current={activeStep === 1 ? "step" : undefined}
          data-testid="step-btn-1"
        >
          <span className="mw-step-num">{step1Completed && activeStep !== 1 ? "\u2713" : "1"}</span>
          <span>{t("customerDemo.stepProfile")}</span>
          {step1Completed && <span className="mw-sr-only">({t("customerDemo.stepCompleted")})</span>}
        </button>

        <span className="mw-stepper-sep" aria-hidden="true">&rsaquo;</span>

        <button
          type="button"
          className={`mw-step-btn ${activeStep === 2 ? "active" : ""} ${step2Completed ? "completed" : ""}`}
          onClick={() => onStepChange(2)}
          aria-current={activeStep === 2 ? "step" : undefined}
          data-testid="step-btn-2"
        >
          <span className="mw-step-num">{step2Completed && activeStep !== 2 ? "\u2713" : "2"}</span>
          <span>{t("customerDemo.stepEvaluation")}</span>
          {isEvaluationStale && (
            <span className="mw-step-tag stale" data-testid="step-2-stale-tag">
              {t("customerDemo.staleEvaluation")}
            </span>
          )}
          {step2Completed && <span className="mw-sr-only">({t("customerDemo.stepCompleted")})</span>}
        </button>

        <span className="mw-stepper-sep" aria-hidden="true">&rsaquo;</span>

        <button
          type="button"
          className={`mw-step-btn ${activeStep === 3 ? "active" : ""} ${step3Completed ? "completed" : ""}`}
          onClick={() => onStepChange(3)}
          aria-current={activeStep === 3 ? "step" : undefined}
          data-testid="step-btn-3"
        >
          <span className="mw-step-num">{step3Completed && activeStep !== 3 ? "\u2713" : "3"}</span>
          <span>{t("customerDemo.stepAdoption")}</span>
          {step3Completed && <span className="mw-sr-only">({t("customerDemo.stepCompleted")})</span>}
        </button>
      </nav>

      {/* Status, Revision and Adoption State Bar */}
      <div className="mw-status-banner" data-testid="workspace-status-banner">
        <div className="mw-revision-info">
          <span>
            {t("customerDemo.answersRevision")}:{" "}
            <strong className="mw-revision-badge" data-testid="answers-rev-badge">
              {currentRevision}
            </strong>
          </span>
          <span>
            {t("customerDemo.selectionRevision")}:{" "}
            <strong className="mw-revision-badge" data-testid="selection-rev-badge">
              {selectionRevision}
            </strong>
          </span>
          {hasUnsavedChanges && (
            <span className="mw-unsaved-badge" data-testid="unsaved-changes-indicator">
              <span aria-hidden="true">&bull;</span>
              {t("customerDemo.unsavedEdits")}
            </span>
          )}
        </div>

        <div>
          {selectedPackSummary ? (
            <div
              className={`mw-adoption-summary-badge ${selectedPackSummary.is_stale ? "stale" : "current"}`}
              data-testid="pack-adoption-status"
            >
              <span>{t("customerDemo.currentAdoption")}:</span>
              <code className="mw-digest-code">{selectedPackSummary.bundle_digest.slice(0, 10)}...</code>
              {selectedPackSummary.is_stale && (
                <span style={{ fontWeight: "bold" }}>{t("customerDemo.staleNotice")}</span>
              )}
            </div>
          ) : (
            <div className="mw-adoption-summary-badge none" data-testid="pack-adoption-status">
              <span>{t("customerDemo.noAdoption")}</span>
            </div>
          )}
        </div>
      </div>

      {/* Child Work Area - Region role to avoid nesting a second main landmark */}
      <div id="workspace-main-content" role="region" aria-label={displayTitle}>
        {children}
      </div>
    </div>
  );
};
