import type {
  ComplianceTaskSummary,
  ControlEntityType,
  ControlImplementationStatus,
  ControlMappingSummary,
  ControlStatusRecordSummary,
  CustomControlStatus,
  CustomControlSummary,
  DataClassification,
  DeletionProofSummary,
  DigestFrequency,
  EvidenceControlLinkSummary,
  EvidenceFileLinkSummary,
  EvidenceItemSummary,
  EvidenceStatus,
  ExportJobSummary,
  ExportManifestSummary,
  ExportScope,
  FindingSeverity,
  FindingSummary,
  FrameworkSummary,
  FrameworkVersionSummary,
  ImpactReportSummary,
  JobExecutionSummary,
  MappingType,
  OverlayApplicability,
  PolicyControlLinkSummary,
  PolicyStatus,
  PolicySummary,
  PreAuditCertificateSummary,
  PreAuditFindingSummary,
  PreAuditManifestSummary,
  PreAuditReportSummary,
  PreAuditSummary,
  PublicCredentialSummary,
  PublicProfileDetailSummary,
  PublicProfileView,
  PublicStatementSummary,
  RemediationStatus,
  SessionIdentity,
  StoredFileSummary,
  TaskPriority,
  TaskStatus,
  TenantCancellationStatus,
  TenantContext,
  TenantControlOverlaySummary,
  TenantFrameworkAdoptionSummary,
  TenantMembershipSummary,
  UserNotificationPreferenceSummary,
  WhistleblowerCaseAssignmentSummary,
  WhistleblowerCaseStatus,
  WhistleblowerCaseSummary,
  WhistleblowerMessageSummary,
  WhistleblowerPortalSummary,
  WhistleblowerPublicCaseSummary,
  WhistleblowerSubmissionResult,
  LegalEntitySummary,
  BusinessUnitSummary,
  LocationSummary,
  TenantEntitlementSummary,
  RiskItemSummary,
  RiskCategory,
  RiskStatus,
  RiskTreatmentStrategy,
  AssetItemSummary,
  AssetType,
  AssetCriticality,
  VendorItemSummary,
  VendorRiskTier,
  VendorStatus,
} from "@conformly/shared";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class SessionExpiredError extends Error {}
export class AccessDeniedError extends Error {}

async function apiRequest<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const defaultHeaders: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };
  if (!isFormData) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...defaultHeaders,
      ...init?.headers,
    },
  });
  if (response.status === 401) throw new SessionExpiredError("Your session has expired.");
  if (response.status === 403) throw new AccessDeniedError("You do not have access.");
  if (!response.ok) {
    let errorDetail = "The request could not be completed.";
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function publicApiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let errorDetail = "The request could not be completed.";
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}


export function bootstrapSession(token: string): Promise<SessionIdentity> {
  return apiRequest("/v1/auth/session", token, { method: "POST" });
}

export function listMyTenants(token: string): Promise<TenantMembershipSummary[]> {
  return apiRequest("/v1/me/tenants", token);
}

export function verifyTenant(token: string, tenantId: string): Promise<TenantContext> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/context`, token);
}

export function revokeSession(token: string): Promise<void> {
  return apiRequest("/v1/auth/session", token, { method: "DELETE" });
}

// Canonical Framework Catalog
export function listCanonicalFrameworks(token: string): Promise<FrameworkSummary[]> {
  return apiRequest("/v1/frameworks", token);
}

export function getCanonicalFramework(
  token: string,
  frameworkId: string
): Promise<FrameworkSummary> {
  return apiRequest(`/v1/frameworks/${encodeURIComponent(frameworkId)}`, token);
}

export function getCanonicalVersionDetails(
  token: string,
  frameworkId: string,
  versionId: string
): Promise<FrameworkVersionSummary> {
  return apiRequest(
    `/v1/frameworks/${encodeURIComponent(frameworkId)}/versions/${encodeURIComponent(versionId)}`,
    token
  );
}

export function compareFrameworkVersions(
  token: string,
  frameworkId: string,
  sourceVersionId: string,
  targetVersionId: string
): Promise<ImpactReportSummary> {
  const query = new URLSearchParams({
    source_version_id: sourceVersionId,
    target_version_id: targetVersionId,
  }).toString();
  return apiRequest(
    `/v1/frameworks/${encodeURIComponent(frameworkId)}/compare?${query}`,
    token
  );
}

// Tenant Framework Adoptions & Impact
export function listTenantAdoptions(
  token: string,
  tenantId: string
): Promise<TenantFrameworkAdoptionSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/frameworks/adoptions`, token);
}

export function getTenantImpactAnalysis(
  token: string,
  tenantId: string,
  frameworkId: string,
  targetVersionId: string
): Promise<ImpactReportSummary> {
  const query = new URLSearchParams({ target_version_id: targetVersionId }).toString();
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/frameworks/${encodeURIComponent(frameworkId)}/impact?${query}`,
    token
  );
}

export function adoptFrameworkVersion(
  token: string,
  tenantId: string,
  frameworkVersionId: string,
  acknowledgeImpact = true
): Promise<TenantFrameworkAdoptionSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/frameworks/adopt`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        framework_version_id: frameworkVersionId,
        acknowledge_impact: acknowledgeImpact,
      }),
    }
  );
}

// Tenant Overlays
export function listTenantOverlays(
  token: string,
  tenantId: string,
  adoptionId: string
): Promise<TenantControlOverlaySummary[]> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/frameworks/adoptions/${encodeURIComponent(adoptionId)}/overlays`,
    token
  );
}

export function manageTenantOverlay(
  token: string,
  tenantId: string,
  adoptionId: string,
  data: {
    canonical_control_id: string;
    applicability: OverlayApplicability;
    justification?: string | null;
    internal_notes?: string | null;
    custom_guidance?: string | null;
  }
): Promise<TenantControlOverlaySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/frameworks/adoptions/${encodeURIComponent(adoptionId)}/overlays`,
    token,
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export function deleteTenantOverlay(
  token: string,
  tenantId: string,
  adoptionId: string,
  overlayId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/frameworks/adoptions/${encodeURIComponent(adoptionId)}/overlays/${encodeURIComponent(overlayId)}`,
    token,
    { method: "DELETE" }
  );
}

// Tenant Custom Controls
export function listCustomControls(
  token: string,
  tenantId: string
): Promise<CustomControlSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/custom-controls`, token);
}

export function createCustomControl(
  token: string,
  tenantId: string,
  data: {
    identifier: string;
    title: string;
    description: string;
    category: string;
    guidance?: string | null;
  }
): Promise<CustomControlSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/custom-controls`,
    token,
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export function updateCustomControl(
  token: string,
  tenantId: string,
  controlId: string,
  data: {
    title: string;
    description: string;
    category: string;
    guidance?: string | null;
    status?: CustomControlStatus;
  }
): Promise<CustomControlSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/custom-controls/${encodeURIComponent(controlId)}`,
    token,
    {
      method: "PUT",
      body: JSON.stringify(data),
    }
  );
}

// Tenant Control Mappings
export function listControlMappings(
  token: string,
  tenantId: string
): Promise<ControlMappingSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/control-mappings`, token);
}

export function createControlMapping(
  token: string,
  tenantId: string,
  data: {
    source_type: ControlEntityType;
    source_control_id: string;
    target_type: ControlEntityType;
    target_control_id: string;
    mapping_type?: MappingType;
    rationale?: string | null;
  }
): Promise<ControlMappingSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/control-mappings`,
    token,
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export function deleteControlMapping(
  token: string,
  tenantId: string,
  mappingId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/control-mappings/${encodeURIComponent(mappingId)}`,
    token,
    { method: "DELETE" }
  );
}

// ----------------------------------------------------------------------------
// Compliance Workspace API
// ----------------------------------------------------------------------------

// Evidence
export function listEvidence(
  token: string,
  tenantId: string,
  params?: { status?: EvidenceStatus; classification?: string }
): Promise<EvidenceItemSummary[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.classification) query.set("classification", params.classification);
  const qStr = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence${qStr}`, token);
}

export function getEvidence(
  token: string,
  tenantId: string,
  evidenceId: string
): Promise<EvidenceItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence/${encodeURIComponent(evidenceId)}`,
    token
  );
}

export function createEvidence(
  token: string,
  tenantId: string,
  data: {
    title: string;
    description: string;
    classification?: DataClassification;
    owner_user_id: string;
    valid_from?: string | null;
    valid_until?: string | null;
    restricted_notes?: string | null;
  }
): Promise<EvidenceItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updateEvidence(
  token: string,
  tenantId: string,
  evidenceId: string,
  data: {
    expected_version: number;
    title?: string;
    description?: string;
    classification?: DataClassification;
    owner_user_id?: string;
    valid_from?: string | null;
    valid_until?: string | null;
    restricted_notes?: string | null;
  }
): Promise<EvidenceItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence/${encodeURIComponent(evidenceId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export function transitionEvidence(
  token: string,
  tenantId: string,
  evidenceId: string,
  data: {
    target_status: EvidenceStatus;
    expected_version: number;
    reason?: string;
  }
): Promise<EvidenceItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence/${encodeURIComponent(evidenceId)}/transition`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function attachFileToEvidence(
  token: string,
  tenantId: string,
  evidenceId: string,
  fileId: string
): Promise<EvidenceFileLinkSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence/${encodeURIComponent(evidenceId)}/files`,
    token,
    { method: "POST", body: JSON.stringify({ file_id: fileId }) }
  );
}

export function removeFileFromEvidence(
  token: string,
  tenantId: string,
  evidenceId: string,
  fileId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence/${encodeURIComponent(evidenceId)}/files/${encodeURIComponent(fileId)}`,
    token,
    { method: "DELETE" }
  );
}

export function linkControlToEvidence(
  token: string,
  tenantId: string,
  evidenceId: string,
  controlType: ControlEntityType,
  controlId: string
): Promise<EvidenceControlLinkSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence/${encodeURIComponent(evidenceId)}/controls`,
    token,
    { method: "POST", body: JSON.stringify({ control_type: controlType, control_id: controlId }) }
  );
}

export function unlinkControlFromEvidence(
  token: string,
  tenantId: string,
  evidenceId: string,
  controlType: ControlEntityType,
  controlId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/evidence/${encodeURIComponent(evidenceId)}/controls/${encodeURIComponent(controlType)}/${encodeURIComponent(controlId)}`,
    token,
    { method: "DELETE" }
  );
}

// Policies
export function listPolicies(
  token: string,
  tenantId: string,
  status?: PolicyStatus
): Promise<PolicySummary[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies${query}`, token);
}

export function getPolicy(
  token: string,
  tenantId: string,
  policyId: string
): Promise<PolicySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}`,
    token
  );
}

export function createPolicy(
  token: string,
  tenantId: string,
  data: {
    title: string;
    description: string;
    version_string?: string;
    review_cycle_days?: number;
    content?: string | null;
    classification?: DataClassification;
    restricted_content?: string | null;
  }
): Promise<PolicySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updatePolicy(
  token: string,
  tenantId: string,
  policyId: string,
  data: {
    expected_version: number;
    title?: string;
    description?: string;
    version_string?: string;
    review_cycle_days?: number;
    content?: string | null;
    classification?: DataClassification;
    restricted_content?: string | null;
  }
): Promise<PolicySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export function submitPolicyReview(
  token: string,
  tenantId: string,
  policyId: string,
  expectedVersion: number
): Promise<PolicySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}/submit-review`,
    token,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) }
  );
}

export function approvePolicy(
  token: string,
  tenantId: string,
  policyId: string,
  expectedVersion: number
): Promise<PolicySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}/approve`,
    token,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) }
  );
}

export function publishPolicy(
  token: string,
  tenantId: string,
  policyId: string,
  expectedVersion: number
): Promise<PolicySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}/publish`,
    token,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) }
  );
}

export function archivePolicy(
  token: string,
  tenantId: string,
  policyId: string,
  expectedVersion: number
): Promise<PolicySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}/archive`,
    token,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) }
  );
}

export function linkControlToPolicy(
  token: string,
  tenantId: string,
  policyId: string,
  controlType: ControlEntityType,
  controlId: string
): Promise<PolicyControlLinkSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}/controls`,
    token,
    { method: "POST", body: JSON.stringify({ control_type: controlType, control_id: controlId }) }
  );
}

export function unlinkControlFromPolicy(
  token: string,
  tenantId: string,
  policyId: string,
  controlType: ControlEntityType,
  controlId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/policies/${encodeURIComponent(policyId)}/controls/${encodeURIComponent(controlType)}/${encodeURIComponent(controlId)}`,
    token,
    { method: "DELETE" }
  );
}

// Tasks
export function listTasks(
  token: string,
  tenantId: string,
  params?: { status?: TaskStatus; priority?: TaskPriority }
): Promise<ComplianceTaskSummary[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.priority) query.set("priority", params.priority);
  const qStr = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks${qStr}`, token);
}

export function getTask(
  token: string,
  tenantId: string,
  taskId: string
): Promise<ComplianceTaskSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks/${encodeURIComponent(taskId)}`,
    token
  );
}

export function createTask(
  token: string,
  tenantId: string,
  data: {
    title: string;
    description: string;
    due_date: string;
    priority?: TaskPriority;
    assignee_user_id?: string | null;
    control_type?: ControlEntityType | null;
    control_id?: string | null;
    evidence_id?: string | null;
    policy_id?: string | null;
  }
): Promise<ComplianceTaskSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updateTask(
  token: string,
  tenantId: string,
  taskId: string,
  data: {
    expected_version: number;
    title?: string;
    description?: string;
    due_date?: string;
    priority?: TaskPriority;
    assignee_user_id?: string | null;
    status?: TaskStatus;
  }
): Promise<ComplianceTaskSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks/${encodeURIComponent(taskId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export function completeTask(
  token: string,
  tenantId: string,
  taskId: string,
  expectedVersion: number
): Promise<ComplianceTaskSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks/${encodeURIComponent(taskId)}/complete`,
    token,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) }
  );
}

// Findings
export function listFindings(
  token: string,
  tenantId: string,
  params?: { severity?: FindingSeverity; remediation_status?: RemediationStatus }
): Promise<FindingSummary[]> {
  const query = new URLSearchParams();
  if (params?.severity) query.set("severity", params.severity);
  if (params?.remediation_status) query.set("remediation_status", params.remediation_status);
  const qStr = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/compliance/findings${qStr}`, token);
}

export function getFinding(
  token: string,
  tenantId: string,
  findingId: string
): Promise<FindingSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/findings/${encodeURIComponent(findingId)}`,
    token
  );
}

export function createFinding(
  token: string,
  tenantId: string,
  data: {
    title: string;
    description: string;
    severity?: FindingSeverity;
    due_date?: string | null;
    owner_user_id?: string | null;
    control_type?: ControlEntityType | null;
    control_id?: string | null;
    remediation_plan?: string | null;
  }
): Promise<FindingSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/findings`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updateFinding(
  token: string,
  tenantId: string,
  findingId: string,
  data: {
    expected_version: number;
    title?: string;
    description?: string;
    severity?: FindingSeverity;
    due_date?: string | null;
    owner_user_id?: string | null;
    remediation_plan?: string | null;
  }
): Promise<FindingSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/findings/${encodeURIComponent(findingId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export function remediateFinding(
  token: string,
  tenantId: string,
  findingId: string,
  data: {
    expected_version: number;
    remediation_status: RemediationStatus;
    remediation_summary?: string | null;
  }
): Promise<FindingSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/findings/${encodeURIComponent(findingId)}/remediation`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

// Posture & Preferences & Jobs
export function listControlStatuses(
  token: string,
  tenantId: string
): Promise<ControlStatusRecordSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/compliance/control-statuses`, token);
}

export function upsertControlStatus(
  token: string,
  tenantId: string,
  controlType: ControlEntityType,
  controlId: string,
  data: {
    status: ControlImplementationStatus;
    assigned_owner_user_id?: string | null;
    notes?: string | null;
    expected_version?: number | null;
  }
): Promise<ControlStatusRecordSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/control-statuses/${encodeURIComponent(controlType)}/${encodeURIComponent(controlId)}`,
    token,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export function getUserPreferences(
  token: string,
  tenantId: string
): Promise<UserNotificationPreferenceSummary> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/compliance/preferences`, token);
}

export function updateUserPreferences(
  token: string,
  tenantId: string,
  data: {
    email_enabled?: boolean;
    digest_frequency?: DigestFrequency;
    notify_task_assigned?: boolean;
    notify_task_due?: boolean;
    notify_evidence_expired?: boolean;
    notify_policy_review?: boolean;
    notify_finding_raised?: boolean;
  }
): Promise<UserNotificationPreferenceSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/preferences`,
    token,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export function runComplianceJobs(
  token: string,
  tenantId: string
): Promise<JobExecutionSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/compliance/jobs/run-expirations`,
    token,
    { method: "POST" }
  );
}

// ── Pre-Audit (Readiness Assessments) ─────────────────────────────────────

export function listPreAudits(
  token: string,
  tenantId: string
): Promise<PreAuditSummary[]> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/`,
    token
  );
}

export function createPreAudit(
  token: string,
  tenantId: string,
  data: {
    title: string;
    description?: string;
    framework_adoption_id: string;
    lead_user_id: string;
  }
): Promise<PreAuditSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function getPreAudit(
  token: string,
  tenantId: string,
  preAuditId: string
): Promise<PreAuditSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}`,
    token
  );
}

export function runPreAuditChecks(
  token: string,
  tenantId: string,
  preAuditId: string
): Promise<PreAuditSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/run-checks`,
    token,
    { method: "POST" }
  );
}

export function addPreAuditFinding(
  token: string,
  tenantId: string,
  preAuditId: string,
  data: {
    title: string;
    description: string;
    severity?: FindingSeverity;
    recommendation?: string | null;
    check_id?: string | null;
  }
): Promise<PreAuditFindingSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/findings`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updatePreAuditFinding(
  token: string,
  tenantId: string,
  preAuditId: string,
  findingId: string,
  data: {
    expected_version: number;
    title?: string;
    description?: string;
    severity?: FindingSeverity;
    recommendation?: string | null;
    remediation_status?: RemediationStatus;
  }
): Promise<PreAuditFindingSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/findings/${encodeURIComponent(findingId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export function submitPreAuditForReview(
  token: string,
  tenantId: string,
  preAuditId: string,
  data: {
    reviewer_user_id: string;
    expected_version: number;
  }
): Promise<PreAuditSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/submit-review`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function completePreAuditReview(
  token: string,
  tenantId: string,
  preAuditId: string,
  data: {
    expected_version: number;
  }
): Promise<PreAuditSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/complete-review`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function cancelPreAudit(
  token: string,
  tenantId: string,
  preAuditId: string,
  data: {
    expected_version: number;
  }
): Promise<PreAuditSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/cancel`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function generatePreAuditReport(
  token: string,
  tenantId: string,
  preAuditId: string,
  data: {
    file_id: string;
    report_type?: string;
  }
): Promise<PreAuditReportSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/generate-report`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function generatePreAuditManifest(
  token: string,
  tenantId: string,
  preAuditId: string,
  data: {
    file_id: string;
    manifest_content: string;
  }
): Promise<PreAuditManifestSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/generate-manifest`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function issuePreAuditCertificate(
  token: string,
  tenantId: string,
  preAuditId: string,
  data?: {
    validity_days?: number;
  }
): Promise<PreAuditCertificateSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/issue-certificate`,
    token,
    { method: "POST", body: JSON.stringify(data ?? {}) }
  );
}

export function revokePreAuditCertificate(
  token: string,
  tenantId: string,
  preAuditId: string,
  certificateId: string,
  data: {
    reason: string;
  }
): Promise<PreAuditCertificateSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/pre-audits/${encodeURIComponent(preAuditId)}/certificates/${encodeURIComponent(certificateId)}/revoke`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

// ── Whistleblower ──────────────────────────────────────────────────────────

// Public Anonymous Endpoints
export function getPublicWhistleblowerPortal(
  slug: string
): Promise<WhistleblowerPortalSummary> {
  return publicApiRequest(`/v1/public/whistleblower/${encodeURIComponent(slug)}`);
}

export function submitWhistleblowerReport(
  slug: string,
  data: {
    category: string;
    title: string;
    summary: string;
  }
): Promise<WhistleblowerSubmissionResult> {
  return publicApiRequest(`/v1/public/whistleblower/${encodeURIComponent(slug)}/submit`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function accessWhistleblowerCasePublic(
  slug: string,
  data: {
    public_case_id: string;
    return_secret: string;
  }
): Promise<WhistleblowerPublicCaseSummary> {
  return publicApiRequest(`/v1/public/whistleblower/${encodeURIComponent(slug)}/access`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function addWhistleblowerReporterMessage(
  slug: string,
  data: {
    public_case_id: string;
    return_secret: string;
    body: string;
  }
): Promise<WhistleblowerMessageSummary> {
  return publicApiRequest(`/v1/public/whistleblower/${encodeURIComponent(slug)}/messages`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Authenticated Handler Endpoints
export function getTenantWhistleblowerPortal(
  token: string,
  tenantId: string
): Promise<WhistleblowerPortalSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/whistleblower/portal`,
    token
  );
}

export function setupOrUpdateWhistleblowerPortal(
  token: string,
  tenantId: string,
  data: {
    slug: string;
    title: string;
    welcome_text: string;
    is_active: boolean;
    expected_version?: number;
  }
): Promise<WhistleblowerPortalSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/whistleblower/portal`,
    token,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export function listWhistleblowerCases(
  token: string,
  tenantId: string,
  params?: {
    status?: WhistleblowerCaseStatus;
    category?: string;
    limit?: number;
    offset?: number;
  }
): Promise<{ items: WhistleblowerCaseSummary[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.category) query.set("category", params.category);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qStr = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/whistleblower/cases${qStr}`,
    token
  );
}

export function getWhistleblowerCaseDetail(
  token: string,
  tenantId: string,
  caseId: string
): Promise<WhistleblowerCaseSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/whistleblower/cases/${encodeURIComponent(caseId)}`,
    token
  );
}

export function addWhistleblowerHandlerMessage(
  token: string,
  tenantId: string,
  caseId: string,
  data: {
    body: string;
  }
): Promise<WhistleblowerMessageSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/whistleblower/cases/${encodeURIComponent(caseId)}/messages`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updateWhistleblowerCaseStatus(
  token: string,
  tenantId: string,
  caseId: string,
  data: {
    status: WhistleblowerCaseStatus;
    closed_reason?: string | null;
    expected_version?: number;
  }
): Promise<WhistleblowerCaseSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/whistleblower/cases/${encodeURIComponent(caseId)}/status`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function assignWhistleblowerHandler(
  token: string,
  tenantId: string,
  caseId: string,
  data: {
    handler_user_id: string;
  }
): Promise<WhistleblowerCaseAssignmentSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/whistleblower/cases/${encodeURIComponent(caseId)}/assign`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

// ---------------------------------------------------------------------------
// Phase 8 — Public Profiles & Compliance Trust Center
// ---------------------------------------------------------------------------

export async function getPublicProfile(
  slug: string,
  ifNoneMatch?: string
): Promise<{ data: PublicProfileView | null; notModified: boolean; etag?: string }> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (ifNoneMatch) {
    headers["If-None-Match"] = ifNoneMatch;
  }
  const response = await fetch(`${API_BASE_URL}/v1/public/profiles/${encodeURIComponent(slug)}`, {
    headers,
  });
  if (response.status === 304) {
    return { data: null, notModified: true, etag: ifNoneMatch };
  }
  if (!response.ok) {
    let errorDetail = "Profile not found.";
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  const etag = response.headers.get("ETag") ?? undefined;
  const data = (await response.json()) as PublicProfileView;
  return { data, notModified: false, etag };
}

export function getTenantPublicProfile(
  token: string,
  tenantId: string
): Promise<PublicProfileDetailSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile`,
    token
  );
}

export function configureTenantPublicProfile(
  token: string,
  tenantId: string,
  data: {
    display_name: string;
    description?: string | null;
    logo_url?: string | null;
    website_url?: string | null;
    primary_contact_email?: string | null;
    slug?: string | null;
    expected_version: number;
  }
): Promise<PublicProfileDetailSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile`,
    token,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export function publishTenantPublicProfile(
  token: string,
  tenantId: string,
  expected_version: number
): Promise<PublicProfileDetailSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/publish`,
    token,
    { method: "POST", body: JSON.stringify({ expected_version }) }
  );
}

export function unpublishTenantPublicProfile(
  token: string,
  tenantId: string,
  expected_version: number
): Promise<PublicProfileDetailSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/unpublish`,
    token,
    { method: "POST", body: JSON.stringify({ expected_version }) }
  );
}

export function addTenantPublicCredential(
  token: string,
  tenantId: string,
  data: {
    title: string;
    issuer_name: string;
    scope_description: string;
    issued_at: string;
    valid_until?: string | null;
    verification_url?: string | null;
    is_publicly_visible: boolean;
    display_order: number;
  }
): Promise<PublicCredentialSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/credentials`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function linkPreAuditPublicCredential(
  token: string,
  tenantId: string,
  data: {
    certificate_id: string;
    is_publicly_visible: boolean;
    display_order: number;
  }
): Promise<PublicCredentialSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/credentials/link-preaudit`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updateTenantPublicCredential(
  token: string,
  tenantId: string,
  credentialId: string,
  data: {
    title: string;
    issuer_name: string;
    scope_description: string;
    valid_until?: string | null;
    verification_url?: string | null;
    is_publicly_visible: boolean;
    display_order: number;
  }
): Promise<PublicCredentialSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/credentials/${encodeURIComponent(credentialId)}`,
    token,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export function revokeTenantPublicCredential(
  token: string,
  tenantId: string,
  credentialId: string,
  reason: string
): Promise<PublicCredentialSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/credentials/${encodeURIComponent(credentialId)}/revoke`,
    token,
    { method: "POST", body: JSON.stringify({ reason }) }
  );
}

export function deleteTenantPublicCredential(
  token: string,
  tenantId: string,
  credentialId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/credentials/${encodeURIComponent(credentialId)}`,
    token,
    { method: "DELETE" }
  );
}

export function addTenantPublicStatement(
  token: string,
  tenantId: string,
  data: {
    title: string;
    statement_content: string;
    display_order: number;
    is_publicly_visible: boolean;
  }
): Promise<PublicStatementSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/statements`,
    token,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function deleteTenantPublicStatement(
  token: string,
  tenantId: string,
  statementId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/public-profile/statements/${encodeURIComponent(statementId)}`,
    token,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// Phase 9: Export, Retention & Deletion Lifecycle
// ---------------------------------------------------------------------------

export function createExportJob(
  token: string,
  tenantId: string,
  scope: ExportScope = "full"
): Promise<ExportJobSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/exports`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ scope }),
    }
  );
}

export function listExportJobs(
  token: string,
  tenantId: string
): Promise<ExportJobSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/exports`, token);
}

export function getExportJob(
  token: string,
  tenantId: string,
  exportId: string
): Promise<ExportJobSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/exports/${encodeURIComponent(exportId)}`,
    token
  );
}

export function getExportManifest(
  token: string,
  tenantId: string,
  exportId: string
): Promise<ExportManifestSummary> {
  return apiRequest<ExportJobSummary>(
    `/v1/tenants/${encodeURIComponent(tenantId)}/exports/${encodeURIComponent(exportId)}`,
    token
  ).then((job) => {
    if (!job.manifest) throw new Error("The export manifest is not available yet.");
    return job.manifest;
  });
}

export async function downloadExportArchive(
  token: string,
  tenantId: string,
  exportId: string
): Promise<Blob> {
  const response = await fetch(
    `${API_BASE_URL}/v1/tenants/${encodeURIComponent(tenantId)}/exports/${encodeURIComponent(exportId)}/download`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  if (!response.ok) {
    if (response.status === 401) {
      throw new SessionExpiredError("Session expired");
    }
    if (response.status === 403) {
      throw new AccessDeniedError("Access denied");
    }
    const errorData = await response.json().catch(() => ({ detail: "Failed to download export" }));
    throw new Error(errorData.detail || "Failed to download export");
  }
  return response.blob();
}

export function getCancellationStatus(
  token: string,
  tenantId: string
): Promise<TenantCancellationStatus> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/cancellation`, token);
}

export function requestTenantCancellation(
  token: string,
  tenantId: string,
  data: { reason: string; confirm_slug: string }
): Promise<TenantCancellationStatus> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/cancellation`,
    token,
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export function setLegalHold(
  token: string,
  tenantId: string,
  enabled: boolean,
  reason: string
): Promise<TenantCancellationStatus> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/legal-hold`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ enabled, reason }),
    }
  );
}

export function listDeletionProofs(
  token: string,
  tenantId: string
): Promise<DeletionProofSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/deletion-proofs`, token);
}

// ---------------------------------------------------------------------------
// File Storage & Evidence Uploads
// ---------------------------------------------------------------------------

export function uploadStoredFile(
  token: string,
  tenantId: string,
  file: File | Blob,
  filename?: string,
  classification: DataClassification = "Internal"
): Promise<StoredFileSummary> {
  const formData = new FormData();
  if (filename) {
    formData.append("file", file, filename);
  } else {
    formData.append("file", file);
  }
  formData.append("classification", classification);

  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/files`,
    token,
    {
      method: "POST",
      body: formData,
    }
  );
}

export function listStoredFiles(
  token: string,
  tenantId: string
): Promise<StoredFileSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/files`, token);
}

export function getStoredFileMetadata(
  token: string,
  tenantId: string,
  fileId: string
): Promise<StoredFileSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/files/${encodeURIComponent(fileId)}`,
    token
  );
}

export async function downloadStoredFile(
  token: string,
  tenantId: string,
  fileId: string
): Promise<Blob> {
  const response = await fetch(
    `${API_BASE_URL}/v1/tenants/${encodeURIComponent(tenantId)}/files/${encodeURIComponent(fileId)}/download`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  if (!response.ok) {
    if (response.status === 401) {
      throw new SessionExpiredError("Your session has expired.");
    }
    if (response.status === 403) {
      throw new AccessDeniedError("You do not have access.");
    }
    let errorDetail = "File download failed.";
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return response.blob();
}

export function deleteStoredFile(
  token: string,
  tenantId: string,
  fileId: string
): Promise<void> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/files/${encodeURIComponent(fileId)}`,
    token,
    { method: "DELETE" }
  );
}

// ── Organizational Scopes (Section 8) ─────────────────────────────────────────

export function listLegalEntities(
  token: string,
  tenantId: string
): Promise<LegalEntitySummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/organization/legal-entities`, token);
}

export function createLegalEntity(
  token: string,
  tenantId: string,
  payload: { name: string; country: string; registration_number?: string | null }
): Promise<LegalEntitySummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/organization/legal-entities`,
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export function listBusinessUnits(
  token: string,
  tenantId: string
): Promise<BusinessUnitSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/organization/business-units`, token);
}

export function createBusinessUnit(
  token: string,
  tenantId: string,
  payload: { legal_entity_id: string; name: string; code?: string | null; description?: string | null }
): Promise<BusinessUnitSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/organization/business-units`,
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export function listLocations(
  token: string,
  tenantId: string
): Promise<LocationSummary[]> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/organization/locations`, token);
}

export function createLocation(
  token: string,
  tenantId: string,
  payload: { legal_entity_id: string; name: string; country: string; city?: string | null; address?: string | null }
): Promise<LocationSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/organization/locations`,
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

// ── Entitlements (Section 4 & 5) ──────────────────────────────────────────────

export function getTenantEntitlement(
  token: string,
  tenantId: string
): Promise<TenantEntitlementSummary> {
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/entitlements`, token);
}

export function updateTenantEntitlement(
  token: string,
  tenantId: string,
  payload: { plan_code?: string; max_members?: number; enabled_modules?: string[] }
): Promise<TenantEntitlementSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/entitlements`,
    token,
    { method: "PUT", body: JSON.stringify(payload) }
  );
}

// ── Operational Registers: Risks (Section 15, Card 17) ────────────────────────

export function listRisks(
  token: string,
  tenantId: string,
  params?: { status?: RiskStatus; category?: RiskCategory }
): Promise<RiskItemSummary[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.category) query.set("category", params.category);
  const qStr = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/risks${qStr}`, token);
}

export function createRisk(
  token: string,
  tenantId: string,
  payload: {
    title: string;
    category: RiskCategory;
    inherent_likelihood: number;
    inherent_impact: number;
    description?: string | null;
    owner_id?: string | null;
  }
): Promise<RiskItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/risks`,
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export function updateRisk(
  token: string,
  tenantId: string,
  riskId: string,
  payload: {
    status?: RiskStatus;
    residual_likelihood?: number | null;
    residual_impact?: number | null;
    treatment_strategy?: RiskTreatmentStrategy | null;
    treatment_plan?: string | null;
    review_date?: string | null;
  }
): Promise<RiskItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/risks/${encodeURIComponent(riskId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(payload) }
  );
}

// ── Operational Registers: Assets (Section 15, Card 17) ───────────────────────

export function listAssets(
  token: string,
  tenantId: string,
  params?: { asset_type?: AssetType; criticality?: AssetCriticality }
): Promise<AssetItemSummary[]> {
  const query = new URLSearchParams();
  if (params?.asset_type) query.set("asset_type", params.asset_type);
  if (params?.criticality) query.set("criticality", params.criticality);
  const qStr = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/assets${qStr}`, token);
}

export function createAsset(
  token: string,
  tenantId: string,
  payload: {
    name: string;
    asset_type: AssetType;
    criticality: AssetCriticality;
    classification: string;
    identifier?: string | null;
    owner_id?: string | null;
    location?: string | null;
    description?: string | null;
  }
): Promise<AssetItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/assets`,
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export function updateAsset(
  token: string,
  tenantId: string,
  assetId: string,
  payload: {
    name?: string;
    criticality?: AssetCriticality;
    classification?: string;
    location?: string | null;
    description?: string | null;
  }
): Promise<AssetItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/assets/${encodeURIComponent(assetId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(payload) }
  );
}

// ── Operational Registers: Vendors (Section 15, Card 17) ──────────────────────

export function listVendors(
  token: string,
  tenantId: string,
  params?: { status?: VendorStatus; risk_tier?: VendorRiskTier }
): Promise<VendorItemSummary[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.risk_tier) query.set("risk_tier", params.risk_tier);
  const qStr = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`/v1/tenants/${encodeURIComponent(tenantId)}/vendors${qStr}`, token);
}

export function createVendor(
  token: string,
  tenantId: string,
  payload: {
    name: string;
    risk_tier: VendorRiskTier;
    status?: VendorStatus;
    service_description?: string | null;
    business_owner_id?: string | null;
    dpa_signed?: boolean;
    security_review_date?: string | null;
    next_assessment_due?: string | null;
  }
): Promise<VendorItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/vendors`,
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export function updateVendor(
  token: string,
  tenantId: string,
  vendorId: string,
  payload: {
    status?: VendorStatus;
    risk_tier?: VendorRiskTier;
    dpa_signed?: boolean;
    security_review_date?: string | null;
    next_assessment_due?: string | null;
  }
): Promise<VendorItemSummary> {
  return apiRequest(
    `/v1/tenants/${encodeURIComponent(tenantId)}/vendors/${encodeURIComponent(vendorId)}`,
    token,
    { method: "PATCH", body: JSON.stringify(payload) }
  );
}

