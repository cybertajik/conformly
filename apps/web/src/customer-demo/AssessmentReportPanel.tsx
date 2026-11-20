import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { SupportedLocale } from "../i18n/types";
import {
  AssessmentReportError, downloadAssessmentReport, validReportContext,
  type ReportContext, type ReportErrorCode,
} from "./assessment-report-api";
import { reportCopy } from "./assessment-report-copy";
import "./assessment-report.css";

export interface AssessmentReportPanelProps extends ReportContext {
  token: string;
  actorId: string;
  /** Existing whole-tenant customer-demo admission; server admission is authoritative. */
  admitted: boolean;
  locale: SupportedLocale;
  onSessionExpired?: () => void;
}

export function AssessmentReportPanel({
  tenantId, adoptionId, answerRevision, selectionRevision,
  token, actorId, admitted, locale, onSessionExpired,
}: AssessmentReportPanelProps) {
  const copy = reportCopy[locale];
  const scope = useMemo(() => ({
    tenantId, adoptionId, answerRevision, selectionRevision, token, actorId, admitted,
  }), [tenantId, adoptionId, answerRevision, selectionRevision, token, actorId, admitted]);
  const [view, setView] = useState<{
    scope: object | null; status: "idle" | "busy" | "prepared"; error: ReportErrorCode | null;
  }>({ scope: null, status: "idle", error: null });
  const busy = view.scope === scope && view.status === "busy";
  const prepared = view.scope === scope && view.status === "prepared";
  const error = view.scope === scope ? view.error : null;
  const active = useRef<{ scope: object; controller: AbortController } | null>(null);
  const objectUrls = useRef(new Set<string>());
  const context = { tenantId, adoptionId, answerRevision, selectionRevision };
  const valid = validReportContext(context) && !!actorId.trim() && !!token.trim();

  useLayoutEffect(() => {
    const urls = objectUrls.current;
    return () => {
      if (active.current?.scope === scope) {
        active.current.controller.abort();
        active.current = null;
      }
      for (const url of urls) URL.revokeObjectURL(url);
      urls.clear();
    };
  }, [scope]);

  const cancel = () => {
    active.current?.controller.abort();
    active.current = null;
    setView({ scope, status: "idle", error: null });
  };
  const download = async () => {
    if (!admitted || !valid || active.current) return;
    const controller = new AbortController();
    const operation = { scope, controller };
    active.current = operation;
    setView({ scope, status: "busy", error: null });
    try {
      const report = await downloadAssessmentReport(context, token, controller.signal);
      if (active.current !== operation || controller.signal.aborted) return;
      const url = URL.createObjectURL(report.blob);
      objectUrls.current.add(url);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = report.filename;
      anchor.rel = "noopener";
      anchor.hidden = true;
      document.body.appendChild(anchor);
      try {
        anchor.click();
        setView({ scope, status: "prepared", error: null });
      } finally {
        anchor.remove();
        // Yield one browser task so the download consumes the URL before release.
        setTimeout(() => {
          if (objectUrls.current.delete(url)) URL.revokeObjectURL(url);
        }, 0);
      }
    } catch (cause) {
      if (active.current !== operation || controller.signal.aborted) return;
      const code = cause instanceof AssessmentReportError ? cause.code : "unavailable";
      setView({ scope, status: "idle", error: code });
      if (code === "unauthorized") onSessionExpired?.();
    } finally {
      if (active.current === operation) {
        active.current = null;
      }
    }
  };
  return (
    <section className="assessment-report-panel" aria-label={copy.title} aria-busy={busy}>
      <div className="assessment-report-panel__heading">
        <span className="assessment-report-panel__icon" aria-hidden="true">↓</span>
        <h2>{copy.title}</h2>
      </div>
      <p>{copy.description}</p>
      <p className="assessment-report-panel__details">{copy.contents}</p>
      {!admitted ? <p role="status">{copy.denied}</p> : !valid ? <p role="status">{copy.missing}</p> : null}
      {error && <p role="alert" className="assessment-report-panel__error">{copy.errors[error]}</p>}
      {prepared && <p role="status">{copy.prepared}</p>}
      <div className="assessment-report-panel__actions">
        <button type="button" disabled={!admitted || !valid || busy} onClick={() => { void download(); }}>
          {busy ? copy.preparing : copy.download}
        </button>
        {busy && <button type="button" className="assessment-report-panel__cancel" onClick={cancel}>{copy.cancel}</button>}
      </div>
    </section>
  );
}

