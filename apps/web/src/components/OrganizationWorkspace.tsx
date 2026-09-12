import type {
  BusinessUnitSummary,
  LegalEntitySummary,
  LocationSummary,
  TenantEntitlementSummary,
  TenantRole,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import {
  createBusinessUnit,
  createLegalEntity,
  createLocation,
  getTenantEntitlement,
  listBusinessUnits,
  listLegalEntities,
  listLocations,
} from "../api";
import { getAccessToken } from "../auth";
import { canManageOrganization } from "../permissions";

interface OrganizationWorkspaceProps {
  tenantId: string;
  userRole: TenantRole;
}

type OrgTab = "entities" | "units" | "locations" | "entitlements";

export function OrganizationWorkspace({ tenantId, userRole }: OrganizationWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<OrgTab>("entities");
  const [entities, setEntities] = useState<LegalEntitySummary[]>([]);
  const [units, setUnits] = useState<BusinessUnitSummary[]>([]);
  const [locations, setLocations] = useState<LocationSummary[]>([]);
  const [entitlement, setEntitlement] = useState<TenantEntitlementSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form modals
  const [showEntityModal, setShowEntityModal] = useState(false);
  const [entityName, setEntityName] = useState("");
  const [entityCountry, setEntityCountry] = useState("DE");
  const [entityRegNum, setEntityRegNum] = useState("");

  const [showUnitModal, setShowUnitModal] = useState(false);
  const [unitEntityId, setUnitEntityId] = useState("");
  const [unitName, setUnitName] = useState("");
  const [unitCode, setUnitCode] = useState("");
  const [unitDescription, setUnitDescription] = useState("");

  const [showLocModal, setShowLocModal] = useState(false);
  const [locEntityId, setLocEntityId] = useState("");
  const [locName, setLocName] = useState("");
  const [locCountry, setLocCountry] = useState("DE");
  const [locCity, setLocCity] = useState("");
  const [locAddress, setLocAddress] = useState("");

  const canManage = canManageOrganization(userRole);

  const loadData = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;

    try {
      setError(null);
      const [eData, uData, lData, entData] = await Promise.all([
        listLegalEntities(token, tenantId),
        listBusinessUnits(token, tenantId),
        listLocations(token, tenantId),
        getTenantEntitlement(token, tenantId).catch(() => null),
      ]);
      setEntities(eData);
      setUnits(uData);
      setLocations(lData);
      setEntitlement(entData);
      if (eData.length > 0 && !unitEntityId) {
        setUnitEntityId(eData[0].id);
        setLocEntityId(eData[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load organization data");
    } finally {
      setLoading(false);
    }
  }, [tenantId, unitEntityId]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await loadData();
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadData]);

  async function handleCreateEntity(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !entityName.trim()) return;

    try {
      await createLegalEntity(token, tenantId, {
        name: entityName.trim(),
        country: entityCountry.trim().toUpperCase(),
        registration_number: entityRegNum.trim() || null,
      });
      setShowEntityModal(false);
      setEntityName("");
      setEntityRegNum("");
      setSuccessMessage("Legal entity registered successfully.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create legal entity");
    }
  }

  async function handleCreateUnit(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !unitName.trim() || !unitEntityId) return;

    try {
      await createBusinessUnit(token, tenantId, {
        legal_entity_id: unitEntityId,
        name: unitName.trim(),
        code: unitCode.trim() || null,
        description: unitDescription.trim() || null,
      });
      setShowUnitModal(false);
      setUnitName("");
      setUnitCode("");
      setUnitDescription("");
      setSuccessMessage("Business unit created successfully.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create business unit");
    }
  }

  async function handleCreateLocation(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !locName.trim() || !locEntityId) return;

    try {
      await createLocation(token, tenantId, {
        legal_entity_id: locEntityId,
        name: locName.trim(),
        country: locCountry.trim().toUpperCase(),
        city: locCity.trim() || null,
        address: locAddress.trim() || null,
      });
      setShowLocModal(false);
      setLocName("");
      setLocCity("");
      setLocAddress("");
      setSuccessMessage("Location created successfully.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create location");
    }
  }

  return (
    <div className="workspace-container">
      <div className="workspace-header">
        <div>
          <h1 className="workspace-title">Organization & Entitlements</h1>
          <p className="workspace-subtitle">
            Manage legal entities, operational business units, locations, and tenant subscription limits.
          </p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {successMessage && <div className="success-banner">{successMessage}</div>}

      <div className="tab-bar">
        <button
          className={`tab-item${activeTab === "entities" ? " active" : ""}`}
          onClick={() => setActiveTab("entities")}
        >
          Legal Entities ({entities.length})
        </button>
        <button
          className={`tab-item${activeTab === "units" ? " active" : ""}`}
          onClick={() => setActiveTab("units")}
        >
          Business Units ({units.length})
        </button>
        <button
          className={`tab-item${activeTab === "locations" ? " active" : ""}`}
          onClick={() => setActiveTab("locations")}
        >
          Locations ({locations.length})
        </button>
        <button
          className={`tab-item${activeTab === "entitlements" ? " active" : ""}`}
          onClick={() => setActiveTab("entitlements")}
        >
          Entitlements & Limits
        </button>
      </div>

      {loading ? (
        <div className="loading-state">Loading organization structure...</div>
      ) : (
        <>
          {activeTab === "entities" && (
            <div className="app-card">
              <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h2 className="card-title">Legal Entities</h2>
                  <p className="card-subtitle">Corporate and statutory bodies under this tenant</p>
                </div>
                {canManage && (
                  <button className="primary" onClick={() => setShowEntityModal(true)}>
                    + Register Legal Entity
                  </button>
                )}
              </div>
              {entities.length === 0 ? (
                <div className="empty-state">No legal entities registered yet. Add your primary legal entity.</div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Entity Name</th>
                      <th>Country</th>
                      <th>Registration Number</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entities.map((e) => (
                      <tr key={e.id}>
                        <td style={{ fontWeight: 600 }}>{e.name}</td>
                        <td>
                          <span className="badge badge-info">{e.country}</span>
                        </td>
                        <td style={{ color: "var(--text-secondary)" }}>{e.registration_number || "—"}</td>
                        <td style={{ color: "var(--text-muted)" }}>{new Date(e.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === "units" && (
            <div className="app-card">
              <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h2 className="card-title">Business Units</h2>
                  <p className="card-subtitle">Operational divisions, departments, or branches</p>
                </div>
                {canManage && entities.length > 0 && (
                  <button className="primary" onClick={() => setShowUnitModal(true)}>
                    + Add Business Unit
                  </button>
                )}
              </div>
              {units.length === 0 ? (
                <div className="empty-state">No business units created. Group controls and members by department.</div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Unit Name</th>
                      <th>Code</th>
                      <th>Legal Entity</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {units.map((u) => {
                      const entity = entities.find((e) => e.id === u.legal_entity_id);
                      return (
                        <tr key={u.id}>
                          <td style={{ fontWeight: 600 }}>{u.name}</td>
                          <td>
                            {u.code ? <span className="badge badge-purple">{u.code}</span> : "—"}
                          </td>
                          <td>{entity ? entity.name : u.legal_entity_id}</td>
                          <td style={{ color: "var(--text-secondary)" }}>{u.description || "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === "locations" && (
            <div className="app-card">
              <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h2 className="card-title">Physical & Data Center Locations</h2>
                  <p className="card-subtitle">Geographic footprint and facility locations</p>
                </div>
                {canManage && entities.length > 0 && (
                  <button className="primary" onClick={() => setShowLocModal(true)}>
                    + Add Location
                  </button>
                )}
              </div>
              {locations.length === 0 ? (
                <div className="empty-state">No facility or data center locations registered.</div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Location Name</th>
                      <th>Country</th>
                      <th>City</th>
                      <th>Address</th>
                    </tr>
                  </thead>
                  <tbody>
                    {locations.map((loc) => (
                      <tr key={loc.id}>
                        <td style={{ fontWeight: 600 }}>{loc.name}</td>
                        <td>
                          <span className="badge badge-info">{loc.country}</span>
                        </td>
                        <td>{loc.city || "—"}</td>
                        <td style={{ color: "var(--text-secondary)" }}>{loc.address || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === "entitlements" && (
            <div className="app-card">
              <div className="card-header">
                <h2 className="card-title">Subscription Entitlements</h2>
                <p className="card-subtitle">Module access and tier capacity boundaries</p>
              </div>
              {entitlement ? (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1.5rem", padding: "1rem" }}>
                  <div className="metric-card">
                    <span className="metric-label">Current Plan</span>
                    <span className="metric-value" style={{ textTransform: "uppercase", color: "var(--accent)" }}>
                      {entitlement.plan_code}
                    </span>
                    <span className="metric-subtext">Deterministic Tier A Baseline</span>
                  </div>
                  <div className="metric-card">
                    <span className="metric-label">Seat Allowance</span>
                    <span className="metric-value">{entitlement.max_members}</span>
                    <span className="metric-subtext">Max active tenant memberships</span>
                  </div>
                  <div className="metric-card" style={{ gridColumn: "span 2" }}>
                    <span className="metric-label">Enabled Modules</span>
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
                      {entitlement.enabled_modules.map((mod) => (
                        <span key={mod} className="badge badge-success" style={{ fontSize: "0.85rem", padding: "0.4rem 0.8rem" }}>
                          ✓ {mod}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="empty-state">Default Pilot entitlements active.</div>
              )}
            </div>
          )}
        </>
      )}

      {/* Register Legal Entity Modal */}
      {showEntityModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Register Legal Entity</h3>
              <button className="ghost" onClick={() => setShowEntityModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateEntity}>
              <div className="form-group">
                <label>Entity Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Cyberdyne Systems GmbH"
                  value={entityName}
                  onChange={(e) => setEntityName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Country Code (ISO 3166-1) *</label>
                <input
                  type="text"
                  required
                  maxLength={2}
                  placeholder="DE"
                  value={entityCountry}
                  onChange={(e) => setEntityCountry(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Commercial Registration / Tax Number</label>
                <input
                  type="text"
                  placeholder="HRB 123456"
                  value={entityRegNum}
                  onChange={(e) => setEntityRegNum(e.target.value)}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setShowEntityModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Save Entity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Business Unit Modal */}
      {showUnitModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Add Business Unit</h3>
              <button className="ghost" onClick={() => setShowUnitModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateUnit}>
              <div className="form-group">
                <label>Parent Legal Entity *</label>
                <select value={unitEntityId} onChange={(e) => setUnitEntityId(e.target.value)} required>
                  {entities.map((e) => (
                    <option key={e.id} value={e.id}>{e.name} ({e.country})</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Unit Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Engineering, Cloud Operations"
                  value={unitName}
                  onChange={(e) => setUnitName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Unit Code</label>
                <input
                  type="text"
                  placeholder="ENG-01"
                  value={unitCode}
                  onChange={(e) => setUnitCode(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  rows={2}
                  placeholder="Scope and purpose of this business unit"
                  value={unitDescription}
                  onChange={(e) => setUnitDescription(e.target.value)}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setShowUnitModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Create Unit
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Location Modal */}
      {showLocModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Add Facility / Location</h3>
              <button className="ghost" onClick={() => setShowLocModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateLocation}>
              <div className="form-group">
                <label>Parent Legal Entity *</label>
                <select value={locEntityId} onChange={(e) => setLocEntityId(e.target.value)} required>
                  {entities.map((e) => (
                    <option key={e.id} value={e.id}>{e.name} ({e.country})</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Location Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Frankfurt Data Center DC1"
                  value={locName}
                  onChange={(e) => setLocName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Country *</label>
                <input
                  type="text"
                  required
                  maxLength={2}
                  placeholder="DE"
                  value={locCountry}
                  onChange={(e) => setLocCountry(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>City</label>
                <input
                  type="text"
                  placeholder="Frankfurt"
                  value={locCity}
                  onChange={(e) => setLocCity(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Address</label>
                <input
                  type="text"
                  placeholder="Mainzer Landstraße 100"
                  value={locAddress}
                  onChange={(e) => setLocAddress(e.target.value)}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setShowLocModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Save Location
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
