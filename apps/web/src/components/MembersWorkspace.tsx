import type { TenantRole } from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import {
  inviteTenantMember,
  listTenantMembers,
  revokeTenantMember,
  updateTenantMemberRole,
  type TenantMemberItem,
} from "../api";
import { canManageMemberships } from "../permissions";

interface MembersWorkspaceProps {
  token: string;
  tenantId: string;
  currentUserRole: TenantRole;
  currentUserId?: string;
}

const AVAILABLE_ROLES: { value: TenantRole; label: string; description: string }[] = [
  {
    value: "owner",
    label: "Owner",
    description: "Full tenant authority, administrative oversight, and governance control.",
  },
  {
    value: "administrator",
    label: "Administrator",
    description: "Platform management and membership administration (strict isolation from compliance data).",
  },
  {
    value: "compliance_manager",
    label: "Compliance Manager",
    description: "Operates compliance programs, manages evidence, reviews controls and policies.",
  },
  {
    value: "control_owner",
    label: "Control Owner",
    description: "Responsible for specific compliance controls, remediations, and evidence collection.",
  },
  {
    value: "reviewer",
    label: "Reviewer",
    description: "Independent assessor for pre-audit reviews and policy sign-offs.",
  },
  {
    value: "auditor",
    label: "External Auditor",
    description: "Read-only inspection rights for audit evidence and assessment verification.",
  },
  {
    value: "contributor",
    label: "Contributor",
    description: "Uploads evidence and completes assigned operational compliance tasks.",
  },
  {
    value: "viewer",
    label: "Viewer",
    description: "Read-only visibility across organizational compliance posture.",
  },
  {
    value: "employee",
    label: "Employee",
    description: "General staff access to published policies and whistleblower intake.",
  },
];

export function MembersWorkspace({
  token,
  tenantId,
  currentUserRole,
  currentUserId,
}: MembersWorkspaceProps) {
  const [members, setMembers] = useState<TenantMemberItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Invite modal / form state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<TenantRole>("contributor");
  const [submittingInvite, setSubmittingInvite] = useState(false);
  const [showInviteForm, setShowInviteForm] = useState(false);

  // Updating role state
  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);

  const canManage = canManageMemberships(currentUserRole);

  const loadMembers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listTenantMembers(token, tenantId);
      setMembers(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tenant members.");
    } finally {
      setLoading(false);
    }
  }, [token, tenantId]);

  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  async function handleInviteSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    try {
      setSubmittingInvite(true);
      setError(null);
      setSuccess(null);
      await inviteTenantMember(token, tenantId, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      setSuccess(`Invitation successfully sent to ${inviteEmail.trim()}`);
      setInviteEmail("");
      setShowInviteForm(false);
      await loadMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send invitation.");
    } finally {
      setSubmittingInvite(false);
    }
  }

  async function handleRoleChange(membershipId: string, newRole: TenantRole) {
    try {
      setUpdatingMemberId(membershipId);
      setError(null);
      setSuccess(null);
      await updateTenantMemberRole(token, tenantId, membershipId, newRole);
      setSuccess("Member role updated successfully.");
      await loadMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update member role.");
    } finally {
      setUpdatingMemberId(null);
    }
  }

  async function handleRevoke(member: TenantMemberItem) {
    const confirm = window.confirm(
      `Are you sure you want to revoke access for ${member.display_name || member.email}?`
    );
    if (!confirm) return;

    try {
      setError(null);
      setSuccess(null);
      await revokeTenantMember(token, tenantId, member.id);
      setSuccess(`Revoked access for ${member.display_name || member.email}`);
      await loadMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke member.");
    }
  }

  return (
    <div className="workspace-container" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="workspace-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
            Team & Access Management
          </h1>
          <p style={{ color: "var(--text-secondary)", margin: "0.25rem 0 0 0", fontSize: "0.95rem" }}>
            Govern tenant memberships, assign compliance roles, and maintain segregation of duties.
          </p>
        </div>
        {canManage && (
          <button
            type="button"
            className="button primary"
            onClick={() => setShowInviteForm((prev) => !prev)}
          >
            {showInviteForm ? "Cancel Invitation" : "+ Invite Member"}
          </button>
        )}
      </div>

      {error && (
        <div className="alert error" style={{ padding: "0.75rem 1rem", borderRadius: "8px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid var(--accent-danger)", color: "var(--accent-danger)" }}>
          {error}
        </div>
      )}

      {success && (
        <div className="alert success" style={{ padding: "0.75rem 1rem", borderRadius: "8px", background: "rgba(34, 197, 94, 0.1)", border: "1px solid var(--accent-success)", color: "var(--accent-success)" }}>
          {success}
        </div>
      )}

      {/* Segregation of Duties Notice */}
      <div className="card" style={{ padding: "1rem 1.25rem", background: "var(--bg-subtle)", border: "1px solid var(--border-subtle)", borderRadius: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.25rem" }}>
          <span>🛡️</span>
          <span>Segregation of Duties & Compliance Isolation</span>
        </div>
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>
          Conformly strictly enforces segregation of duties: Pre-Audit assessment leads cannot serve as their own independent reviewers, policy authors cannot approve their own policies, and administrators are strictly isolated from sensitive compliance evidence.
        </p>
      </div>

      {/* Invite Form */}
      {showInviteForm && canManage && (
        <div className="card" style={{ padding: "1.5rem", borderRadius: "10px", border: "1px solid var(--border-focus)" }}>
          <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem" }}>Invite New Tenant Member</h3>
          <form onSubmit={(e) => void handleInviteSubmit(e)} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                  Work Email Address
                </label>
                <input
                  type="email"
                  required
                  placeholder="colleague@example.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "6px", border: "1px solid var(--border-default)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                  Assigned Role
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as TenantRole)}
                  style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "6px", border: "1px solid var(--border-default)" }}
                >
                  {AVAILABLE_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label} — {r.description}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button
                type="button"
                className="button secondary"
                onClick={() => setShowInviteForm(false)}
                disabled={submittingInvite}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="button primary"
                disabled={submittingInvite || !inviteEmail.trim()}
              >
                {submittingInvite ? "Sending..." : "Send Invitation"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Members Table */}
      <div className="card" style={{ padding: "1.25rem", borderRadius: "10px" }}>
        <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem" }}>
          Active Members ({members.length})
        </h3>

        {loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
            Loading member directory...
          </div>
        ) : members.length === 0 ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
            No members found for this tenant.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--border-subtle)", color: "var(--text-secondary)" }}>
                  <th style={{ padding: "0.75rem 0.5rem" }}>User</th>
                  <th style={{ padding: "0.75rem 0.5rem" }}>Email</th>
                  <th style={{ padding: "0.75rem 0.5rem" }}>Role</th>
                  <th style={{ padding: "0.75rem 0.5rem" }}>Status</th>
                  {canManage && <th style={{ padding: "0.75rem 0.5rem", textAlign: "right" }}>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {members.map((member) => {
                  const isSelf = currentUserId && member.user_id === currentUserId;
                  const isUpdating = updatingMemberId === member.id;

                  return (
                    <tr key={member.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "0.75rem 0.5rem", fontWeight: 600 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <div
                            style={{
                              width: "32px",
                              height: "32px",
                              borderRadius: "50%",
                              background: "var(--accent-primary)",
                              color: "#fff",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: "0.8rem",
                              fontWeight: 700,
                            }}
                          >
                            {(member.display_name || member.email)[0].toUpperCase()}
                          </div>
                          <div>
                            <div>{member.display_name || "Anonymous Member"}</div>
                            {isSelf && (
                              <span style={{ fontSize: "0.75rem", color: "var(--accent-primary)" }}>
                                (You)
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: "0.75rem 0.5rem", color: "var(--text-secondary)" }}>
                        {member.email}
                      </td>
                      <td style={{ padding: "0.75rem 0.5rem" }}>
                        {canManage && !isSelf ? (
                          <select
                            value={member.role}
                            disabled={isUpdating}
                            onChange={(e) => void handleRoleChange(member.id, e.target.value as TenantRole)}
                            style={{
                              padding: "0.3rem 0.5rem",
                              borderRadius: "6px",
                              fontSize: "0.85rem",
                              border: "1px solid var(--border-default)",
                            }}
                          >
                            {AVAILABLE_ROLES.map((r) => (
                              <option key={r.value} value={r.value}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span
                            className="badge"
                            style={{
                              background:
                                member.role === "owner"
                                  ? "rgba(147, 51, 234, 0.15)"
                                  : member.role === "reviewer" || member.role === "auditor"
                                  ? "rgba(59, 130, 246, 0.15)"
                                  : "rgba(107, 114, 128, 0.15)",
                              color:
                                member.role === "owner"
                                  ? "#9333ea"
                                  : member.role === "reviewer" || member.role === "auditor"
                                  ? "#2563eb"
                                  : "var(--text-primary)",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "4px",
                              fontSize: "0.8rem",
                              fontWeight: 600,
                            }}
                          >
                            {member.role.replaceAll("_", " ")}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "0.75rem 0.5rem" }}>
                        <span
                          className="badge"
                          style={{
                            background:
                              member.status === "active"
                                ? "rgba(34, 197, 94, 0.15)"
                                : "rgba(239, 68, 68, 0.15)",
                            color: member.status === "active" ? "#16a34a" : "#dc2626",
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontSize: "0.8rem",
                            fontWeight: 600,
                          }}
                        >
                          {member.status}
                        </span>
                      </td>
                      {canManage && (
                        <td style={{ padding: "0.75rem 0.5rem", textAlign: "right" }}>
                          {!isSelf && member.status === "active" && (
                            <button
                              type="button"
                              className="button secondary danger"
                              onClick={() => void handleRevoke(member)}
                              style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                            >
                              Revoke
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
