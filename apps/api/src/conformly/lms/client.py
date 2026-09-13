import json
import time
from typing import Any

from conformly.integrations.service import compute_webhook_signature
from conformly.lms.contract import LmsAssignmentPayload, LmsCompletionPayload, LmsContract


class LmsPartnerSimulator(LmsContract):
    """Reference implementation and test simulator for external LMS partner systems."""

    def __init__(self, provider_name: str = "Conformly-LMS-Simulator") -> None:
        self.provider_name = provider_name
        self.received_assignments: list[LmsAssignmentPayload] = []

    def dispatch_assignment(
        self,
        payload: LmsAssignmentPayload,
    ) -> dict[str, Any]:
        self.received_assignments.append(payload)
        return {
            "status": "enrolled",
            "provider": self.provider_name,
            "assignment_id": payload.assignment_id,
            "learner_email": payload.learner_email,
            "course_id": payload.course_id,
        }

    def generate_signed_completion_event(
        self,
        payload: LmsCompletionPayload,
        signing_secret: str,
        timestamp: int | None = None,
        key_id: str = "cf_live_test",
    ) -> tuple[bytes, dict[str, str]]:
        ts = timestamp if timestamp is not None else int(time.time())
        data = {
            "event_id": payload.event_id,
            "topic": "lms.course_completion",
            "tenant_id": payload.tenant_id,
            "course_id": payload.course_id,
            "course_version": payload.course_version,
            "learner_email": payload.learner_email,
            "assignment_id": payload.assignment_id,
            "completed_at": payload.completed_at,
            "passed": payload.passed,
            "score": payload.score,
            "certificate_id": payload.certificate_id,
        }
        raw_body = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = compute_webhook_signature(raw_body, ts, signing_secret)

        headers = {
            "Content-Type": "application/json",
            "X-Conformly-Key-Id": key_id,
            "X-Conformly-Signature": signature,
            "X-Conformly-Timestamp": str(ts),
            "X-Conformly-Idempotency-Key": payload.event_id,
        }
        return raw_body, headers
