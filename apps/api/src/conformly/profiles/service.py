"""Public compliance profile and trust center service.

Handles explicit publication approval, public projection serialization,
Conformly readiness badge linking, third-party certification management,
and cache ETag validation.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.identity.models import Tenant
from conformly.preaudit.models import CertificateStatus, PreAuditCertificate
from conformly.profiles.models import (
    PublicCredential,
    PublicCredentialStatus,
    PublicCredentialType,
    PublicProfile,
    PublicStatement,
    is_valid_profile_slug,
)


class PublicProfileError(Exception):
    """Base exception for public profile domain errors."""


class PublicProfileNotFoundError(PublicProfileError):
    """Raised when a public profile is not found or not published."""


class PublicProfileSlugConflictError(PublicProfileError):
    """Raised when a requested profile slug is already in use."""


class PublicProfileInvalidSlugError(PublicProfileError):
    """Raised when a requested slug format is invalid."""


class PublicProfileConcurrencyConflictError(PublicProfileError):
    """Raised when an optimistic concurrency check fails."""


class PublicCredentialNotFoundError(PublicProfileError):
    """Raised when a public credential is not found."""


class PublicCredentialInvalidSourceError(PublicProfileError):
    """Raised when linking an invalid or inactive pre-audit certificate."""


CONFORMLY_DISCLAIMER = (
    "Conformly is an audit-readiness and compliance operations platform, "
    "not an accredited certification body. Pre-audit badges represent "
    "automated readiness evaluations, not accredited third-party certifications."
)


class PublicProfileService:
    """Domain service for public profiles and public credentials."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Public (Unauthenticated) Projections ─────────────────────────────────

    def get_public_profile_view(self, slug: str) -> tuple[dict[str, Any], str]:
        """Fetch an explicitly published public profile view and its ETag.

        Returns (profile_view_dict, etag).
        Raises PublicProfileNotFoundError if not found or unpublished.
        """
        clean_slug = slug.strip().lower()
        stmt = (
            select(PublicProfile)
            .options(
                selectinload(PublicProfile.credentials),
                selectinload(PublicProfile.statements),
            )
            .where(
                func.lower(PublicProfile.slug) == clean_slug,
                PublicProfile.is_published.is_(True),
            )
        )
        profile = self._session.scalar(stmt)
        if profile is None:
            raise PublicProfileNotFoundError(f"Public profile '{slug}' not found.")

        self._session.refresh(profile, ["credentials", "statements"])

        # Filter active visible credentials and statements
        now = datetime.now(UTC)
        visible_credentials: list[dict[str, Any]] = []
        for cred in profile.credentials:
            if not cred.is_publicly_visible:
                continue

            # Auto-expire credentials past their valid_until date
            status = cred.status
            if status == PublicCredentialStatus.ACTIVE and cred.valid_until:
                valid_until_dt = cred.valid_until
                if valid_until_dt.tzinfo is None:
                    valid_until_dt = valid_until_dt.replace(tzinfo=UTC)
                if valid_until_dt < now:
                    status = PublicCredentialStatus.EXPIRED

            status_val = status.value if hasattr(status, "value") else str(status)
            if status_val != PublicCredentialStatus.ACTIVE.value:
                continue

            cred_type = (
                cred.credential_type.value
                if hasattr(cred.credential_type, "value")
                else str(cred.credential_type)
            )

            visible_credentials.append(
                {
                    "id": str(cred.id),
                    "credential_type": cred_type,
                    "title": cred.title,
                    "issuer_name": cred.issuer_name,
                    "scope_description": cred.scope_description,
                    "issued_at": cred.issued_at.isoformat(),
                    "valid_until": cred.valid_until.isoformat() if cred.valid_until else None,
                    "status": status_val,
                    "verification_url": cred.verification_url,
                    "source_certificate_id": str(cred.source_certificate_id)
                    if cred.source_certificate_id
                    else None,
                    "display_order": cred.display_order,
                }
            )

        visible_statements: list[dict[str, Any]] = [
            {
                "id": str(st.id),
                "title": st.title,
                "statement_content": st.statement_content,
                "display_order": st.display_order,
            }
            for st in profile.statements
            if st.is_publicly_visible
        ]

        payload: dict[str, Any] = {
            "id": str(profile.id),
            "slug": profile.slug,
            "display_name": profile.display_name,
            "description": profile.description,
            "logo_url": profile.logo_url,
            "website_url": profile.website_url,
            "primary_contact_email": profile.primary_contact_email,
            "published_at": profile.published_at.isoformat() if profile.published_at else None,
            "credentials": visible_credentials,
            "statements": visible_statements,
            "conformly_verified": any(
                c["credential_type"] == PublicCredentialType.CONFORMLY_READINESS.value
                and c["status"] == PublicCredentialStatus.ACTIVE.value
                for c in visible_credentials
            ),
            "disclaimer": CONFORMLY_DISCLAIMER,
        }

        # Calculate strong ETag
        etag_raw = (
            f"{profile.id}:{profile.version}:{profile.updated_at.isoformat()}:"
            f"{len(visible_credentials)}"
        )
        etag = f'"{hashlib.sha256(etag_raw.encode("utf-8")).hexdigest()[:16]}"'

        return payload, etag

    # ── Authenticated Tenant Operations ──────────────────────────────────────

    def get_or_create_tenant_profile(
        self,
        tenant_id: UUID,
        principal: Principal,
        context: TenantContext,
    ) -> PublicProfile:
        """Get or initialize the tenant's public profile record."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_READ)

        stmt = (
            select(PublicProfile)
            .options(
                selectinload(PublicProfile.credentials),
                selectinload(PublicProfile.statements),
            )
            .where(PublicProfile.tenant_id == tenant_id)
        )
        profile = self._session.scalar(stmt)
        if profile is not None:
            return profile

        # Initialize default draft profile
        tenant = self._session.get(Tenant, tenant_id)
        default_slug = tenant.slug if tenant else str(tenant_id)[:8]
        # Check collision
        collision = self._session.scalar(
            select(PublicProfile).where(PublicProfile.slug == default_slug)
        )
        if collision:
            default_slug = f"{default_slug}-{secrets.token_hex(2)}"

        profile = PublicProfile(
            id=uuid4(),
            tenant_id=tenant_id,
            slug=default_slug,
            display_name=tenant.name if tenant else "Organization Compliance",
            description="Compliance and security trust center.",
            is_published=False,
            version=1,
        )
        self._session.add(profile)
        self._session.flush()
        return profile

    def configure_profile(
        self,
        tenant_id: UUID,
        display_name: str,
        description: str | None,
        logo_url: str | None,
        website_url: str | None,
        primary_contact_email: str | None,
        slug: str | None,
        expected_version: int,
        principal: Principal,
        context: TenantContext,
    ) -> PublicProfile:
        """Update public profile configuration with OCC."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        profile = self.get_or_create_tenant_profile(tenant_id, principal, context)
        if profile.version != expected_version:
            raise PublicProfileConcurrencyConflictError(
                f"Profile version conflict. Expected {expected_version}, found {profile.version}."
            )

        if slug:
            clean_slug = slug.strip().lower()
            if clean_slug != profile.slug:
                if not is_valid_profile_slug(clean_slug):
                    raise PublicProfileInvalidSlugError(
                        f"Slug '{slug}' is invalid. "
                        "Must be 3-64 lowercase alphanumeric chars and hyphens."
                    )
                existing = self._session.scalar(
                    select(PublicProfile).where(
                        PublicProfile.slug == clean_slug,
                        PublicProfile.id != profile.id,
                    )
                )
                if existing:
                    raise PublicProfileSlugConflictError(f"Slug '{clean_slug}' is already taken.")
                profile.slug = clean_slug

        profile.display_name = display_name.strip()
        profile.description = description.strip() if description else None
        profile.logo_url = logo_url.strip() if logo_url else None
        profile.website_url = website_url.strip() if website_url else None
        profile.primary_contact_email = (
            primary_contact_email.strip() if primary_contact_email else None
        )
        profile.version += 1
        profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_profile.configured",
            resource_type="public_profile",
            resource_id=str(profile.id),
            request_id=f"profile:configure:{profile.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "slug": profile.slug,
                "display_name": profile.display_name,
                "version": profile.version,
            },
        )
        self._session.flush()
        return profile

    def publish_profile(
        self,
        tenant_id: UUID,
        expected_version: int,
        principal: Principal,
        context: TenantContext,
    ) -> PublicProfile:
        """Publish the profile to the public internet."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        profile = self.get_or_create_tenant_profile(tenant_id, principal, context)
        if profile.version != expected_version:
            raise PublicProfileConcurrencyConflictError("Profile version conflict.")

        profile.is_published = True
        profile.published_at = datetime.now(UTC)
        profile.version += 1
        profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_profile.published",
            resource_type="public_profile",
            resource_id=str(profile.id),
            request_id=f"profile:publish:{profile.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"slug": profile.slug, "version": profile.version},
        )
        self._session.flush()
        return profile

    def unpublish_profile(
        self,
        tenant_id: UUID,
        expected_version: int,
        principal: Principal,
        context: TenantContext,
    ) -> PublicProfile:
        """Unpublish the profile immediately revoking public visibility."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        profile = self.get_or_create_tenant_profile(tenant_id, principal, context)
        if profile.version != expected_version:
            raise PublicProfileConcurrencyConflictError("Profile version conflict.")

        profile.is_published = False
        profile.version += 1
        profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_profile.unpublished",
            resource_type="public_profile",
            resource_id=str(profile.id),
            request_id=f"profile:unpublish:{profile.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"slug": profile.slug, "version": profile.version},
        )
        self._session.flush()
        return profile

    # ── Credential Operations ────────────────────────────────────────────────

    def add_third_party_credential(
        self,
        tenant_id: UUID,
        title: str,
        issuer_name: str,
        scope_description: str,
        issued_at: datetime,
        valid_until: datetime | None,
        verification_url: str | None,
        is_publicly_visible: bool,
        display_order: int,
        principal: Principal,
        context: TenantContext,
    ) -> PublicCredential:
        """Add a customer-supplied third-party certification."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        profile = self.get_or_create_tenant_profile(tenant_id, principal, context)

        cred = PublicCredential(
            id=uuid4(),
            profile_id=profile.id,
            tenant_id=tenant_id,
            credential_type=PublicCredentialType.THIRD_PARTY,
            title=title.strip(),
            issuer_name=issuer_name.strip(),
            scope_description=scope_description.strip(),
            issued_at=issued_at,
            valid_until=valid_until,
            status=PublicCredentialStatus.ACTIVE,
            verification_url=verification_url.strip() if verification_url else None,
            source_certificate_id=None,
            is_publicly_visible=is_publicly_visible,
            display_order=display_order,
        )
        self._session.add(cred)

        profile.version += 1
        profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_credential.created",
            resource_type="public_credential",
            resource_id=str(cred.id),
            request_id=f"credential:create:{cred.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "badge_type": str(cred.credential_type),
                "title": cred.title,
                "issuer_name": cred.issuer_name,
            },
        )
        self._session.flush()
        return cred

    def link_preaudit_credential(
        self,
        tenant_id: UUID,
        certificate_id: UUID,
        is_publicly_visible: bool,
        display_order: int,
        principal: Principal,
        context: TenantContext,
    ) -> PublicCredential:
        """Project an existing active PreAuditCertificate as a public readiness badge."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        profile = self.get_or_create_tenant_profile(tenant_id, principal, context)

        # Lookup and verify source certificate
        cert = self._session.scalar(
            select(PreAuditCertificate).where(
                PreAuditCertificate.id == certificate_id,
                PreAuditCertificate.tenant_id == tenant_id,
            )
        )
        if cert is None:
            raise PublicCredentialInvalidSourceError(f"Certificate '{certificate_id}' not found.")

        cert_status_val = cert.status.value if hasattr(cert.status, "value") else str(cert.status)
        if cert_status_val != CertificateStatus.ACTIVE.value:
            raise PublicCredentialInvalidSourceError(
                f"Cannot link certificate with status '{cert_status_val}'."
            )

        # Check if already linked
        existing = self._session.scalar(
            select(PublicCredential).where(
                PublicCredential.profile_id == profile.id,
                PublicCredential.source_certificate_id == certificate_id,
            )
        )
        if existing:
            existing.status = PublicCredentialStatus.ACTIVE
            existing.is_publicly_visible = is_publicly_visible
            existing.display_order = display_order
            existing.updated_at = datetime.now(UTC)
            self._session.flush()
            return existing

        pre_audit = cert.pre_audit
        assessment_title = (
            pre_audit.title if pre_audit and pre_audit.title else cert.certificate_number
        )
        rule_ver = pre_audit.rule_version if pre_audit else "v1.0"
        score_text = (
            f" Overall readiness score: {pre_audit.overall_score * 100:.1f}%."
            if pre_audit and pre_audit.overall_score is not None
            else ""
        )

        cred = PublicCredential(
            id=uuid4(),
            profile_id=profile.id,
            tenant_id=tenant_id,
            credential_type=PublicCredentialType.CONFORMLY_READINESS,
            title=f"Conformly Pre-Audit Readiness: {assessment_title}",
            issuer_name="Conformly Automated Compliance",
            scope_description=(
                f"Evaluation against rule set {rule_ver}.{score_text} "
                f"Conformly Certificate: {cert.certificate_number}."
            ),
            issued_at=cert.issued_at,
            valid_until=cert.expires_at,
            status=PublicCredentialStatus.ACTIVE,
            verification_url=f"/v1/public/certificates/{cert.certificate_number}",
            source_certificate_id=cert.id,
            is_publicly_visible=is_publicly_visible,
            display_order=display_order,
        )
        self._session.add(cred)

        profile.version += 1
        profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_credential.created",
            resource_type="public_credential",
            resource_id=str(cred.id),
            request_id=f"credential:link:{cred.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "badge_type": str(cred.credential_type),
                "title": cred.title,
                "certificate_id": str(cert.id),
            },
        )
        self._session.flush()
        return cred

    def update_credential(
        self,
        tenant_id: UUID,
        credential_id: UUID,
        title: str,
        issuer_name: str,
        scope_description: str,
        valid_until: datetime | None,
        verification_url: str | None,
        is_publicly_visible: bool,
        display_order: int,
        principal: Principal,
        context: TenantContext,
    ) -> PublicCredential:
        """Update credential attributes."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        cred = self._session.scalar(
            select(PublicCredential).where(
                PublicCredential.id == credential_id,
                PublicCredential.tenant_id == tenant_id,
            )
        )
        if cred is None:
            raise PublicCredentialNotFoundError(f"Credential '{credential_id}' not found.")

        cred.title = title.strip()
        cred.issuer_name = issuer_name.strip()
        cred.scope_description = scope_description.strip()
        cred.valid_until = valid_until
        cred.verification_url = verification_url.strip() if verification_url else None
        cred.is_publicly_visible = is_publicly_visible
        cred.display_order = display_order
        cred.updated_at = datetime.now(UTC)

        profile = self._session.get(PublicProfile, cred.profile_id)
        if profile:
            profile.version += 1
            profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_credential.updated",
            resource_type="public_credential",
            resource_id=str(cred.id),
            request_id=f"credential:update:{cred.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"badge_id": str(cred.id), "title": cred.title},
        )
        self._session.flush()
        return cred

    def revoke_credential(
        self,
        tenant_id: UUID,
        credential_id: UUID,
        reason: str,
        principal: Principal,
        context: TenantContext,
    ) -> PublicCredential:
        """Mark credential as revoked so it no longer verifies publicly."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        cred = self._session.scalar(
            select(PublicCredential).where(
                PublicCredential.id == credential_id,
                PublicCredential.tenant_id == tenant_id,
            )
        )
        if cred is None:
            raise PublicCredentialNotFoundError(f"Credential '{credential_id}' not found.")

        cred.status = PublicCredentialStatus.REVOKED
        cred.updated_at = datetime.now(UTC)

        profile = self._session.get(PublicProfile, cred.profile_id)
        if profile:
            profile.version += 1
            profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_credential.revoked",
            resource_type="public_credential",
            resource_id=str(cred.id),
            request_id=f"credential:revoke:{cred.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"badge_id": str(cred.id), "reason": reason},
        )
        self._session.flush()
        return cred

    def delete_credential(
        self,
        tenant_id: UUID,
        credential_id: UUID,
        principal: Principal,
        context: TenantContext,
    ) -> None:
        """Permanently delete a credential from the profile."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        cred = self._session.scalar(
            select(PublicCredential).where(
                PublicCredential.id == credential_id,
                PublicCredential.tenant_id == tenant_id,
            )
        )
        if cred is None:
            raise PublicCredentialNotFoundError(f"Credential '{credential_id}' not found.")

        profile_id = cred.profile_id
        self._session.delete(cred)

        profile = self._session.get(PublicProfile, profile_id)
        if profile:
            profile.version += 1
            profile.updated_at = datetime.now(UTC)

        record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="public_credential.deleted",
            resource_type="public_credential",
            resource_id=str(credential_id),
            request_id=f"credential:delete:{credential_id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"badge_id": str(credential_id)},
        )
        self._session.flush()

    # ── Statement Operations ─────────────────────────────────────────────────

    def add_statement(
        self,
        tenant_id: UUID,
        title: str,
        statement_content: str,
        display_order: int,
        is_publicly_visible: bool,
        principal: Principal,
        context: TenantContext,
    ) -> PublicStatement:
        """Add a public compliance pledge or policy statement."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        profile = self.get_or_create_tenant_profile(tenant_id, principal, context)

        st = PublicStatement(
            id=uuid4(),
            profile_id=profile.id,
            tenant_id=tenant_id,
            title=title.strip(),
            statement_content=statement_content.strip(),
            display_order=display_order,
            is_publicly_visible=is_publicly_visible,
        )
        self._session.add(st)

        profile.version += 1
        profile.updated_at = datetime.now(UTC)
        self._session.flush()
        return st

    def delete_statement(
        self,
        tenant_id: UUID,
        statement_id: UUID,
        principal: Principal,
        context: TenantContext,
    ) -> None:
        """Remove a public statement."""
        authorize(principal, context, Capability.PUBLIC_PROFILE_MANAGE)

        st = self._session.scalar(
            select(PublicStatement).where(
                PublicStatement.id == statement_id,
                PublicStatement.tenant_id == tenant_id,
            )
        )
        if st is not None:
            profile = self._session.get(PublicProfile, st.profile_id)
            self._session.delete(st)
            if profile:
                profile.version += 1
                profile.updated_at = datetime.now(UTC)
            self._session.flush()
