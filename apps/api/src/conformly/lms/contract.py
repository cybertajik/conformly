from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class LmsAssignmentPayload:
    """Standardized payload dispatched to external LMS when training is assigned in Conformly."""

    assignment_id: str
    tenant_id: str
    course_id: str
    learner_email: str
    learner_name: str
    due_date: str
    callback_url: str


@dataclass(frozen=True, slots=True)
class LmsCompletionPayload:
    """Standardized payload received from external LMS upon learner course completion."""

    event_id: str
    tenant_id: str
    course_id: str
    course_version: str
    learner_email: str
    completed_at: str
    passed: bool
    assignment_id: str | None = None
    score: float | None = None
    certificate_id: str | None = None


class LmsContract(Protocol):
    """Protocol defining the external LMS integration boundary."""

    def dispatch_assignment(
        self,
        payload: LmsAssignmentPayload,
    ) -> dict[str, Any]:
        """Dispatch course assignment notification to external LMS."""
        ...

    def generate_signed_completion_event(
        self,
        payload: LmsCompletionPayload,
        signing_secret: str,
        timestamp: int | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        """Generate signed webhook payload and HTTP headers for simulated or client-side callback."""
        ...
