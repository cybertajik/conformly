import React, { FC, useEffect, useRef, useState } from "react";

import { bootstrapSession, CatalogApiError, fetchCatalogGraph, revokeSession } from "./api";
import {
  cleanUrlParams,
  clearStoredSession,
  getStoredSession,
  getStoredToken,
  handleOidcCallback,
  isSessionExpired,
  parseCallbackMarkers,
  setStoredSession,
  startWorkforceLogin,
  STORAGE_KEYS,
} from "./auth";
import "./catalog-demo.css";
import { CatalogDemoGraphResponse, CatalogDemoSessionResponse } from "./types";

type ActiveTab = "overview" | "requirements" | "evidence";

interface CallbackFlight {
  generation: number;
  abortController: AbortController;
  promise: Promise<void>;
  abortTimeoutId?: ReturnType<typeof setTimeout>;
}

export const CatalogDemoApp: FC = () => {
  const [session, setSession] = useState<CatalogDemoSessionResponse | null>(null);
  const [graph, setGraph] = useState<CatalogDemoGraphResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [selectedReqKey, setSelectedReqKey] = useState<string | null>(null);

  const isMountedRef = useRef<boolean>(true);
  const opGenRef = useRef<number>(0);
  const callbackFlightRef = useRef<CallbackFlight | null>(null);

  // Check for OIDC callback code & state on initial load.
  // StrictMode-safe single flight: the first mount initiates the token exchange and bootstrap,
  // and the second mount in StrictMode reuses the in-flight operation without re-issuing a fetch.
  useEffect(() => {
    isMountedRef.current = true;

    // StrictMode re-mount: connect to existing in-flight operation
    if (callbackFlightRef.current) {
      if (callbackFlightRef.current.abortTimeoutId) {
        clearTimeout(callbackFlightRef.current.abortTimeoutId);
        callbackFlightRef.current.abortTimeoutId = undefined;
      }
      return () => {
        isMountedRef.current = false;
        const flight = callbackFlightRef.current;
        if (flight) {
          flight.abortTimeoutId = setTimeout(() => {
            flight.abortController.abort();
            callbackFlightRef.current = null;
          }, 150);
        }
      };
    }

    const callbackInfo = parseCallbackMarkers();
    if (callbackInfo.isCallback) {
      // Snapshot PKCE state before cleaning URL or before handleOidcCallback consumes it
      const pkceVerifier = sessionStorage.getItem(STORAGE_KEYS.PKCE_VERIFIER);

      cleanUrlParams();

      if (!callbackInfo.valid || !callbackInfo.code || !callbackInfo.state) {
        clearStoredSession();
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSession(null);
        setErrorStatus(401);
        setErrorMessage(callbackInfo.error || "Workforce authentication failed or was cancelled.");
        setLoading(false);
        return;
      }

      opGenRef.current += 1;
      const currentGen = opGenRef.current;
      const abortController = new AbortController();

      const exchangeAndBootstrap = async () => {
        setLoading(true);
        setErrorStatus(null);
        setErrorMessage(null);
        try {
          const idToken = await handleOidcCallback(
            callbackInfo.code!,
            callbackInfo.state!,
            abortController.signal,
            pkceVerifier
          );
          const newSession = await bootstrapSession(idToken, abortController.signal);

          // Fence: current generation, signal not aborted, and component mounted
          if (currentGen !== opGenRef.current || abortController.signal.aborted || !isMountedRef.current) {
            return;
          }

          // Active operation alone commits credentials to storage and state
          sessionStorage.setItem(STORAGE_KEYS.TOKEN, idToken);
          setStoredSession(newSession);
          setSession(newSession);
          setLoading(false);
          callbackFlightRef.current = null;
        } catch (err: unknown) {
          if (currentGen !== opGenRef.current || abortController.signal.aborted || !isMountedRef.current) {
            return;
          }
          clearStoredSession();
          setSession(null);
          setLoading(false);
          callbackFlightRef.current = null;
          if (err instanceof CatalogApiError) {
            setErrorStatus(err.status);
            setErrorMessage(err.message);
          } else {
            setErrorStatus(401);
            setErrorMessage(
              err instanceof Error ? err.message : "Authentication failed or was cancelled."
            );
          }
        }
      };

      const flightPromise = exchangeAndBootstrap();

      callbackFlightRef.current = {
        generation: currentGen,
        abortController,
        promise: flightPromise,
      };

      return () => {
        isMountedRef.current = false;
        const flight = callbackFlightRef.current;
        if (flight) {
          flight.abortTimeoutId = setTimeout(() => {
            flight.abortController.abort();
            callbackFlightRef.current = null;
          }, 150);
        }
      };
    } else {
      // Normal mount without callback: load initial stored session
      const stored = getStoredSession();
      const token = getStoredToken();
      if (stored && token && !isSessionExpired(stored)) {
        setSession(stored);
      } else {
        clearStoredSession();
        setSession(null);
      }
      setLoading(false);
    }

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Fetch catalog graph when an active staff session is available
  useEffect(() => {
    if (!session) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setGraph(null);
      return;
    }

    opGenRef.current += 1;
    const currentGen = opGenRef.current;
    const abortController = new AbortController();

    const loadGraph = async () => {
      setLoading(true);
      setErrorStatus(null);
      setErrorMessage(null);
      try {
        const token = getStoredToken();
        if (!token) {
          setLoading(false);
          return;
        }
        const data = await fetchCatalogGraph(token, abortController.signal);
        if (currentGen !== opGenRef.current || abortController.signal.aborted || !isMountedRef.current) {
          return;
        }
        setGraph(data);
        if (data.requirements && data.requirements.length > 0) {
          setSelectedReqKey(data.requirements[0].requirement_key);
        }
        setLoading(false);
      } catch (err: unknown) {
        if (currentGen !== opGenRef.current || abortController.signal.aborted || !isMountedRef.current) {
          return;
        }
        setLoading(false);
        if (err instanceof CatalogApiError) {
          setErrorStatus(err.status);
          setErrorMessage(err.message);
          if (err.status === 401 || err.status === 403) {
            clearStoredSession();
            setSession(null);
          }
        } else {
          setErrorStatus(500);
          setErrorMessage(err instanceof Error ? err.message : "Failed to load catalog data");
        }
      }
    };

    void loadGraph();

    return () => {
      abortController.abort();
      opGenRef.current += 1;
    };
  }, [session]);

  const handleSignIn = async () => {
    setErrorStatus(null);
    setErrorMessage(null);
    try {
      await startWorkforceLogin();
    } catch (err: unknown) {
      setErrorStatus(400);
      setErrorMessage(err instanceof Error ? err.message : "Failed to initiate login");
    }
  };

  const handleSignOut = () => {
    const tokenToRevoke = getStoredToken();
    opGenRef.current += 1;
    if (callbackFlightRef.current) {
      if (callbackFlightRef.current.abortTimeoutId) {
        clearTimeout(callbackFlightRef.current.abortTimeoutId);
      }
      callbackFlightRef.current.abortController.abort();
      callbackFlightRef.current = null;
    }
    clearStoredSession();
    setSession(null);
    setGraph(null);
    setErrorStatus(null);
    setErrorMessage(null);
    setActiveTab("overview");
    if (tokenToRevoke) {
      void revokeSession(tokenToRevoke).catch(() => {});
    }
  };

  const selectedRequirement = graph?.requirements.find(
    (r) => r.requirement_key === selectedReqKey
  );

  return (
    <div className="catalog-demo-container">
      {/* Synthetic Demonstration Watermark / Warning */}
      <header className="catalog-demo-banner" role="region" aria-label="Synthetic Data Warning">
        <div className="banner-badge">SYNTHETIC ENVIRONMENT</div>
        <div className="banner-content">
          <strong>NOTICE: Synthetic data only.</strong> This catalog preview is for demonstration
          and assurance validation purposes. It does not contain customer or production data.
        </div>
        <div className="banner-status">Draft catalog preview</div>
      </header>

      {/* Main Header with Session info */}
      <div className="catalog-demo-header">
        <div className="header-titles">
          <h1>Conformly Synthetic Catalog Demo</h1>
          <p className="subtitle">
            Authenticated Staff Preview & Assurance Verification Workspace
          </p>
        </div>
        <div className="header-auth">
          {session ? (
            <div className="session-card">
              <div className="user-details">
                <span className="user-label">Signed in as:</span>
                <strong data-testid="session-user" className="user-name">
                  {session.display_name}
                </strong>
                <span className="user-caps">Capabilities: {session.capabilities.join(", ")}</span>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleSignOut}
                data-testid="sign-out-btn"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSignIn}
              data-testid="sign-in-btn"
            >
              Sign In with Workforce SSO
            </button>
          )}
        </div>
      </div>

      {/* Status & Error Messages */}
      {errorStatus && (
        <div className="alert alert-error" role="alert">
          <strong>Error ({errorStatus}):</strong> {errorMessage}
        </div>
      )}

      {loading && (
        <div className="loading-indicator" role="status">
          <div className="spinner" />
          <span>Loading catalog demo workspace...</span>
        </div>
      )}

      {/* Unauthenticated Placeholder View */}
      {!session && !loading && (
        <div className="unauth-view">
          <div className="unauth-card">
            <h2>Authentication Required</h2>
            <p>
              Please sign in with your enterprise workforce credentials to access the synthetic
              assurance catalog.
            </p>
            <button type="button" className="btn btn-primary" onClick={handleSignIn}>
              Sign In with Workforce SSO
            </button>
          </div>
        </div>
      )}

      {/* Authenticated Workspace */}
      {session && graph && !loading && (
        <div className="catalog-workspace">
          {/* Navigation Tabs */}
          <nav className="tab-nav" aria-label="Catalog Demo Navigation">
            <button
              type="button"
              className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
              onClick={() => setActiveTab("overview")}
              data-testid="tab-overview"
            >
              Overview & Provenance
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "requirements" ? "active" : ""}`}
              onClick={() => setActiveTab("requirements")}
              data-testid="tab-requirements"
            >
              Requirements & Controls
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "evidence" ? "active" : ""}`}
              onClick={() => setActiveTab("evidence")}
              data-testid="tab-evidence"
            >
              Evidence & Procedures
            </button>
          </nav>

          {/* Tab 1: Overview */}
          {activeTab === "overview" && (
            <div className="tab-pane overview-pane" data-testid="pane-overview">
              <section className="card">
                <h3>Catalog Source Specification</h3>
                <dl className="details-grid">
                  <dt>Source Title</dt>
                  <dd>{graph.source.title}</dd>
                  <dt>Source Key</dt>
                  <dd>
                    <code>{graph.source.source_key}</code>
                  </dd>
                  <dt>Version Edition</dt>
                  <dd>{graph.source_version.edition}</dd>
                  <dt>Publication Date</dt>
                  <dd>{graph.source_version.publication_date}</dd>
                  <dt>Digest</dt>
                  <dd>
                    <code>{graph.source_version.content_digest}</code>
                  </dd>
                  <dt>Official Locator</dt>
                  <dd>{graph.source_version.official_locator}</dd>
                </dl>
              </section>

              <section className="card metrics-card">
                <h3>Draft Assurance Metrics</h3>
                <div className="metrics-grid">
                  <div className="metric-box">
                    <span className="metric-num">{graph.requirements.length}</span>
                    <span className="metric-label">Requirements</span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-num">{graph.controls.length}</span>
                    <span className="metric-label">Controls</span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-num">{graph.mappings.length}</span>
                    <span className="metric-label">Mappings</span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-num">{graph.evidence_requirements.length}</span>
                    <span className="metric-label">Evidence Specs</span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-num">{graph.assessment_procedures.length}</span>
                    <span className="metric-label">Procedures</span>
                  </div>
                </div>
              </section>
            </div>
          )}

          {/* Tab 2: Requirements & Controls */}
          {activeTab === "requirements" && (
            <div className="tab-pane requirements-pane" data-testid="pane-requirements">
              <div className="master-detail-layout">
                <aside className="master-list">
                  <h4>Requirements ({graph.requirements.length})</h4>
                  <ul>
                    {graph.requirements.map((req) => (
                      <li key={req.id}>
                        <button
                          type="button"
                          className={`list-item-btn ${
                            selectedReqKey === req.requirement_key ? "selected" : ""
                          }`}
                          onClick={() => setSelectedReqKey(req.requirement_key)}
                          data-testid={`req-selector-${req.requirement_key}`}
                        >
                          <strong>{req.requirement_key}</strong>
                          <span className="badge badge-sm">{req.normalized_outcome}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </aside>

                <main className="detail-view">
                  {selectedRequirement ? (
                    <article className="card requirement-detail">
                      <header className="req-header">
                        <h3>{selectedRequirement.requirement_key}</h3>
                        <span className="badge badge-primary">
                          {selectedRequirement.normalized_outcome}
                        </span>
                      </header>

                      <div className="req-meta">
                        <span>Actor: {selectedRequirement.obligated_actor}</span>
                        <span>Type: {selectedRequirement.requirement_type}</span>
                        <span>Revision: {selectedRequirement.revision}</span>
                      </div>

                      <h4>Mapped Common Controls</h4>
                      {(() => {
                        const reqMappings = graph.mappings.filter(
                          (m) => m.requirement_id === selectedRequirement.id
                        );
                        if (reqMappings.length === 0) {
                          return <p className="text-muted">No controls currently mapped.</p>;
                        }

                        return (
                          <div className="controls-list">
                            {reqMappings.map((mapItem) => {
                              const ctrl = graph.controls.find((c) => c.id === mapItem.control_id);
                              if (!ctrl) return null;
                              return (
                                <div key={mapItem.id} className="control-item-card">
                                  <div className="ctrl-header">
                                    <strong>{ctrl.control_key}</strong>: {ctrl.title}
                                  </div>
                                  <p className="ctrl-obj">{ctrl.objective}</p>
                                  {ctrl.guidance && <p className="ctrl-guidance">{ctrl.guidance}</p>}
                                  {mapItem.rationale && (
                                    <p className="ctrl-rationale">{mapItem.rationale}</p>
                                  )}
                                  {mapItem.covered_dimensions && (
                                    <p className="ctrl-covered">Covered: {mapItem.covered_dimensions}</p>
                                  )}
                                  {mapItem.excluded_dimensions && (
                                    <p className="ctrl-excluded">Excluded: {mapItem.excluded_dimensions}</p>
                                  )}
                                  <div className="ctrl-tags">
                                    <span className="tag">Domain: {ctrl.domain}</span>
                                    <span className="tag">Frequency: {ctrl.frequency}</span>
                                    <span className="tag">Type: {ctrl.control_type}</span>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        );
                      })()}
                    </article>
                  ) : (
                    <p>Select a requirement to inspect its details and control mappings.</p>
                  )}
                </main>
              </div>
            </div>
          )}

          {/* Tab 3: Evidence & Procedures */}
          {activeTab === "evidence" && (
            <div className="tab-pane evidence-pane" data-testid="pane-evidence">
              <section className="card">
                <h3>Evidence Specifications</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Key</th>
                      <th>Title</th>
                      <th>Frequency</th>
                      <th>Artifact Types</th>
                      <th>Required Metadata</th>
                    </tr>
                  </thead>
                  <tbody>
                    {graph.evidence_requirements.map((evid) => (
                      <tr key={evid.id}>
                        <td>
                          <code>{evid.requirement_key}</code>
                        </td>
                        <td>{evid.title}</td>
                        <td>{evid.frequency}</td>
                        <td>{evid.artifact_types.map((a) => a.artifact_type).join(", ")}</td>
                        <td>{evid.required_metadata.map((m) => m.metadata_key).join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              <section className="card">
                <h3>Assessment Procedures</h3>
                <div className="procedures-grid">
                  {graph.assessment_procedures.map((proc) => (
                    <div key={proc.id} className="procedure-card">
                      <div className="proc-header">
                        <h4>{proc.procedure_key}</h4>
                        <span className="proc-title">{proc.title}</span>
                      </div>
                      <p className="proc-obj">
                        <strong>Objective:</strong> {proc.objective}
                      </p>
                      <div className="proc-steps">
                        <h5>Steps:</h5>
                        <ol>
                          {proc.steps.map((step) => (
                            <li key={step.sequence}>
                              <em>({step.step_kind})</em> {step.instruction}
                            </li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
