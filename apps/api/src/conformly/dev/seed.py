from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.db.session import SessionLocal
from conformly.identity.models import Membership, MembershipStatus, Tenant, User
from conformly.tenancy.rls import set_rls_context

DEVELOPMENT_ENVIRONMENTS = frozenset({"development", "local", "test"})


class UnsafeSeedEnvironmentError(RuntimeError):
    """Raised before fixture data can be written outside a development environment."""


def seed_development_fixtures(database: Session, *, environment: str) -> None:
    if environment.casefold() not in DEVELOPMENT_ENVIRONMENTS:
        raise UnsafeSeedEnvironmentError("development fixtures are disabled in this environment")

    tenant = database.scalar(select(Tenant).where(Tenant.slug == "example-organization"))
    if tenant is None:
        tenant = Tenant(name="Example Organization", slug="example-organization")
        database.add(tenant)

    user = database.scalar(
        select(User).where(
            User.oidc_issuer == "https://development.invalid",
            User.oidc_subject == "example-user",
        )
    )
    if user is None:
        user = User(
            oidc_issuer="https://development.invalid",
            oidc_subject="example-user",
            email="example-user@development.invalid",
            display_name="Example User",
        )
        database.add(user)
    database.flush()
    set_rls_context(
        database,
        user_id=user.id,
        tenant_id=tenant.id,
        tenant_verified=True,
    )
    membership = database.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant.id,
            Membership.user_id == user.id,
        )
    )
    if membership is None:
        database.add(
            Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
    database.flush()


def main() -> None:
    settings = get_settings()
    with SessionLocal() as database:
        seed_development_fixtures(database, environment=settings.environment)
        database.commit()


if __name__ == "__main__":
    main()
