import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.identity.models import User


def test_email_is_canonicalized_before_storage(session: Session) -> None:
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject="subject-1",
        email="  Person@Example.TEST ",
        display_name="Person",
    )
    session.add(user)
    session.commit()

    assert user.email == "person@example.test"


def test_email_uniqueness_is_case_insensitive(session: Session) -> None:
    session.add(
        User(
            oidc_issuer="https://identity.example.test",
            oidc_subject="subject-1",
            email="person@example.test",
            display_name="Person One",
        )
    )
    session.commit()
    session.add(
        User(
            oidc_issuer="https://other-identity.example.test",
            oidc_subject="subject-2",
            email="PERSON@EXAMPLE.TEST",
            display_name="Person Two",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("email", ["", "not-an-email", "a" * 321])
def test_invalid_email_is_rejected(email: str) -> None:
    with pytest.raises(ValueError):
        User(
            oidc_issuer="https://identity.example.test",
            oidc_subject="subject",
            email=email,
            display_name="Person",
        )
