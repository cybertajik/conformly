from uuid import uuid4

from sqlalchemy.orm import Session

from conformly.tenancy.rls import set_rls_context


def test_rls_context_is_a_noop_for_non_postgresql_sessions(session: Session) -> None:
    set_rls_context(
        session,
        user_id=uuid4(),
        tenant_id=uuid4(),
        tenant_verified=False,
    )

    assert session.in_transaction() is False
