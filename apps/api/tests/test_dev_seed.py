import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conformly.dev.seed import UnsafeSeedEnvironmentError, seed_development_fixtures
from conformly.identity.models import AuthSession, Membership, Tenant, User


def test_development_seed_is_idempotent_and_contains_no_credentials(session: Session) -> None:
    seed_development_fixtures(session, environment="development")
    seed_development_fixtures(session, environment="development")

    assert session.scalar(select(func.count()).select_from(User)) == 1
    assert session.scalar(select(func.count()).select_from(Tenant)) == 1
    assert session.scalar(select(func.count()).select_from(Membership)) == 1
    assert session.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_development_seed_refuses_production(session: Session) -> None:
    with pytest.raises(UnsafeSeedEnvironmentError):
        seed_development_fixtures(session, environment="production")

    assert session.scalar(select(func.count()).select_from(User)) == 0
