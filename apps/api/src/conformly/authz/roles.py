from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    COMPLIANCE_MANAGER = "compliance_manager"
    AUDITOR = "auditor"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class Capability(StrEnum):
    TENANT_READ = "tenant:read"
    TENANT_MANAGE = "tenant:manage"
    MEMBERSHIP_READ = "membership:read"
    MEMBERSHIP_MANAGE = "membership:manage"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    FILE_READ = "file:read"
    FILE_WRITE = "file:write"
    FILE_DELETE = "file:delete"
    FRAMEWORK_READ = "framework:read"
    FRAMEWORK_MANAGE = "framework:manage"
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_MANAGE = "evidence:manage"
    POLICY_READ = "policy:read"
    POLICY_MANAGE = "policy:manage"
    TASK_READ = "task:read"
    TASK_MANAGE = "task:manage"
    FINDING_READ = "finding:read"
    FINDING_MANAGE = "finding:manage"
    CONTROL_STATUS_MANAGE = "control_status:manage"
    PREAUDIT_READ = "preaudit:read"
    PREAUDIT_MANAGE = "preaudit:manage"
    WHISTLEBLOWER_PORTAL_MANAGE = "whistleblower:portal_manage"
    WHISTLEBLOWER_CASE_READ = "whistleblower:case_read"
    WHISTLEBLOWER_CASE_MANAGE = "whistleblower:case_manage"
    PUBLIC_PROFILE_MANAGE = "public_profile:manage"
    PUBLIC_PROFILE_READ = "public_profile:read"
    EXPORT_CREATE = "export:create"
    EXPORT_READ = "export:read"
    TENANT_CANCEL = "tenant:cancel"
    RETENTION_MANAGE = "retention:manage"


ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.OWNER: frozenset(Capability),
    Role.ADMINISTRATOR: frozenset(c for c in Capability if c != Capability.TENANT_CANCEL),
    Role.COMPLIANCE_MANAGER: frozenset(
        {
            Capability.TENANT_READ,
            Capability.MEMBERSHIP_READ,
            Capability.AUDIT_READ,
            Capability.AUDIT_EXPORT,
            Capability.FILE_READ,
            Capability.FILE_WRITE,
            Capability.FILE_DELETE,
            Capability.FRAMEWORK_READ,
            Capability.FRAMEWORK_MANAGE,
            Capability.EVIDENCE_READ,
            Capability.EVIDENCE_MANAGE,
            Capability.POLICY_READ,
            Capability.POLICY_MANAGE,
            Capability.TASK_READ,
            Capability.TASK_MANAGE,
            Capability.FINDING_READ,
            Capability.FINDING_MANAGE,
            Capability.CONTROL_STATUS_MANAGE,
            Capability.PREAUDIT_READ,
            Capability.PREAUDIT_MANAGE,
            Capability.WHISTLEBLOWER_PORTAL_MANAGE,
            Capability.WHISTLEBLOWER_CASE_READ,
            Capability.WHISTLEBLOWER_CASE_MANAGE,
            Capability.PUBLIC_PROFILE_MANAGE,
            Capability.PUBLIC_PROFILE_READ,
            Capability.EXPORT_CREATE,
            Capability.EXPORT_READ,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Capability.TENANT_READ,
            Capability.MEMBERSHIP_READ,
            Capability.AUDIT_READ,
            Capability.FILE_READ,
            Capability.FRAMEWORK_READ,
            Capability.EVIDENCE_READ,
            Capability.POLICY_READ,
            Capability.TASK_READ,
            Capability.FINDING_READ,
            Capability.PREAUDIT_READ,
            Capability.PUBLIC_PROFILE_READ,
            Capability.EXPORT_READ,
        }
    ),
    Role.CONTRIBUTOR: frozenset(
        {
            Capability.TENANT_READ,
            Capability.FILE_READ,
            Capability.FILE_WRITE,
            Capability.FRAMEWORK_READ,
            Capability.FRAMEWORK_MANAGE,
            Capability.EVIDENCE_READ,
            Capability.EVIDENCE_MANAGE,
            Capability.POLICY_READ,
            Capability.TASK_READ,
            Capability.TASK_MANAGE,
            Capability.FINDING_READ,
            Capability.FINDING_MANAGE,
            Capability.PREAUDIT_READ,
            Capability.PUBLIC_PROFILE_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Capability.TENANT_READ,
            Capability.FILE_READ,
            Capability.FRAMEWORK_READ,
            Capability.EVIDENCE_READ,
            Capability.POLICY_READ,
            Capability.TASK_READ,
            Capability.FINDING_READ,
            Capability.PREAUDIT_READ,
            Capability.PUBLIC_PROFILE_READ,
        }
    ),
}
