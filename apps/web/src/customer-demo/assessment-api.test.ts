import { describe, expect, it, vi } from "vitest";
import {
  ConflictError,
  ForbiddenError,
  NotFoundError,
  UnauthorizedError,
  ValidationError,
} from "./api";
import {
  fetchAssessmentHistory,
  fetchAssessmentWorkList,
  fetchProcedure,
  recordAssessment,
  recordRetest,
  updateFinding,
} from "./assessment-api";
import {
  AssessmentCreatePayload,
  AssessmentHistoryResponse,
  AssessmentReceipt,
  AssessmentWorkListResponse,
  FindingPatchPayload,
  Procedure,
  RetestCreatePayload,
} from "./assessment-types";
import { PayloadTooLargeError } from "./control-evidence-api";

describe("Customer Demo Assessment API Client", () => {
  it("fetches assessment work list and summary successfully", async () => {
    const mockResponse: AssessmentWorkListResponse = {
      tenant_id: "11111111-1111-4111-8111-111111111111",
      adoption_id: "22222222-2222-4222-8222-222222222222",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: {
        total_controls: 1,
        stale_work: 0,
        needs_information: 0,
        not_applicable: 0,
        unassessed: 1,
        unavailable_evidence: 0,
        stale_assessment: 0,
        insufficient_evidence: 0,
        fail: 0,
        partial: 0,
        pass_with_open_findings: 0,
        pass_count: 0,
        open_findings: 0,
        in_remediation_findings: 0,
        resolved_findings: 0,
        blocked_control_ids: [],
        reason_codes: [],
      },
      items: [
        {
          work_id: "33333333-3333-4333-8333-333333333333",
          control_version_id: "44444444-4444-4444-8444-444444444444",
          work_version: 1,
          assessment_revision: 0,
          procedure: {
            id: "55555555-5555-4555-8555-555555555555",
            version: "1.0.0",
            digest: "a".repeat(64),
            criteria: [],
            disclaimer: "Disclaimer",
          },
          latest_assessment: null,
          primary_state: "UNASSESSED",
          blockers: [],
          findings: [],
          history: [],
          requirement_results: [],
        },
      ],
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchAssessmentWorkList("11111111-1111-4111-8111-111111111111", "token-123");
    expect(result).toEqual(mockResponse);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/v2/tenants/11111111-1111-4111-8111-111111111111/customer-demo/assessment-work"
    );
  });

  it("fetches procedure for a work item", async () => {
    const mockProc: Procedure = {
      id: "55555555-5555-4555-8555-555555555555",
      version: "1.0.0",
      digest: "b".repeat(64),
      criteria: [
        {
          id: "implementation",
          title: "Implementation Criterion",
          description: "Verify config",
          sequence: 1,
        },
      ],
      disclaimer: "Synthetic disclaimer",
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockProc), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchProcedure("11111111-1111-4111-8111-111111111111", "token-123", "33333333-3333-4333-8333-333333333333");
    expect(result).toEqual(mockProc);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/v2/tenants/11111111-1111-4111-8111-111111111111/customer-demo/assessment-work/33333333-3333-4333-8333-333333333333/procedure"
    );
  });

  it("fetches chronological event history", async () => {
    const mockHist: AssessmentHistoryResponse = {
      work_id: "33333333-3333-4333-8333-333333333333",
      total: 1,
      items: [
        {
          event_id: "66666666-6666-4666-8666-666666666666",
          revision: 1,
          operation_id: "77777777-7777-4777-8777-777777777777",
          event_type: "ASSESSMENT",
          result: "PASS",
          observed_work_version: 1,
          actor_id: "88888888-8888-4888-8888-888888888888",
          created_at: "2026-10-25T08:00:00Z",
          details: { rationale: "Verified" },
        },
      ],
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockHist), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchAssessmentHistory("11111111-1111-4111-8111-111111111111", "token-123", "33333333-3333-4333-8333-333333333333");
    expect(result).toEqual(mockHist);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/v2/tenants/11111111-1111-4111-8111-111111111111/customer-demo/assessment-work/33333333-3333-4333-8333-333333333333/history"
    );
  });

  it("records human assessment via POST", async () => {
    const mockReceipt: AssessmentReceipt = {
      operation_id: "77777777-7777-4777-8777-777777777777",
      event_id: "66666666-6666-4666-8666-666666666666",
      applied_revision: 1,
      replayed: false,
      current_item: {
        work_id: "33333333-3333-4333-8333-333333333333",
        control_version_id: "44444444-4444-4444-8444-444444444444",
        work_version: 1,
        assessment_revision: 1,
        procedure: {
          id: "55555555-5555-4555-8555-555555555555",
          version: "1.0.0",
          digest: "c".repeat(64),
          criteria: [],
          disclaimer: "Disclaimer",
        },
        latest_assessment: null,
        primary_state: "FAIL",
        blockers: ["OPEN_FINDINGS"],
        findings: [
          {
            id: "99999999-9999-4999-8999-999999999999",
            source_event_id: "66666666-6666-4666-8666-666666666666",
            current_event_id: "66666666-6666-4666-8666-666666666666",
            severity: "MEDIUM",
            status: "OPEN",
            owner_user_id: "88888888-8888-4888-8888-888888888888",
            due_date: "2026-11-01",
            version: 1,
            created_at: "2026-10-25T08:00:00Z",
            updated_at: "2026-10-25T08:00:00Z",
          },
        ],
        history: [],
        requirement_results: [],
      },
      summary: {
        total_controls: 1,
        stale_work: 0,
        needs_information: 0,
        not_applicable: 0,
        unassessed: 0,
        unavailable_evidence: 0,
        stale_assessment: 0,
        insufficient_evidence: 0,
        fail: 1,
        partial: 0,
        pass_with_open_findings: 0,
        pass_count: 0,
        open_findings: 1,
        in_remediation_findings: 0,
        resolved_findings: 0,
        blocked_control_ids: ["44444444-4444-4444-8444-444444444444"],
        reason_codes: ["OPEN_FINDINGS"],
      },
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockReceipt), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload: AssessmentCreatePayload = {
      operation_id: "77777777-7777-4777-8777-777777777777",
      expected_answer_revision: 1,
      expected_selection_revision: 1,
      expected_work_version: 1,
      expected_assessment_revision: 0,
      procedure_id: "55555555-5555-4555-8555-555555555555",
      procedure_version: "1.0.0",
      procedure_digest: "a".repeat(64),
      evidence_link_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
      criterion_results: [{ criterion_id: "implementation", result: "FAIL" }],
      result: "FAIL",
      rationale: "Missing signoff",
      finding: {
        severity: "MEDIUM",
        owner_user_id: "88888888-8888-4888-8888-888888888888",
        due_date: "2026-11-01",
      },
    };

    const result = await recordAssessment("11111111-1111-4111-8111-111111111111", "token-123", "33333333-3333-4333-8333-333333333333", payload);
    expect(result).toEqual(mockReceipt);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/v2/tenants/11111111-1111-4111-8111-111111111111/customer-demo/assessment-work/33333333-3333-4333-8333-333333333333/assessments"
    );
  });

  it("updates finding via PATCH", async () => {
    const mockReceipt = {
      operation_id: "77777777-7777-4777-8777-777777777777",
      event_id: "66666666-6666-4666-8666-666666666666",
      applied_revision: 2,
      replayed: false,
    } as unknown as AssessmentReceipt;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockReceipt), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload: FindingPatchPayload = {
      operation_id: "77777777-7777-4777-8777-777777777777",
      expected_answer_revision: 1,
      expected_selection_revision: 1,
      expected_work_version: 1,
      expected_assessment_revision: 1,
      expected_finding_version: 1,
      severity: "MEDIUM",
      owner_user_id: "88888888-8888-4888-8888-888888888888",
      due_date: "2026-11-01",
      status: "IN_REMEDIATION",
      remediation_note: "Remediation underway",
    };

    const result = await updateFinding("11111111-1111-4111-8111-111111111111", "token-123", "99999999-9999-4999-8999-999999999999", payload);
    expect(result).toEqual(mockReceipt);
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/v2/tenants/11111111-1111-4111-8111-111111111111/customer-demo/assessment-work/findings/99999999-9999-4999-8999-999999999999"
    );
  });

  it("records explicit retest via POST", async () => {
    const mockReceipt = {
      operation_id: "77777777-7777-4777-8777-777777777777",
      event_id: "66666666-6666-4666-8666-666666666666",
      applied_revision: 3,
      replayed: false,
    } as unknown as AssessmentReceipt;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockReceipt), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload: RetestCreatePayload = {
      operation_id: "77777777-7777-4777-8777-777777777777",
      expected_answer_revision: 1,
      expected_selection_revision: 1,
      expected_work_version: 1,
      expected_assessment_revision: 2,
      procedure_id: "55555555-5555-4555-8555-555555555555",
      procedure_version: "1.0.0",
      procedure_digest: "a".repeat(64),
      evidence_link_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
      criterion_results: [{ criterion_id: "implementation", result: "PASS" }],
      result: "PASS",
      rationale: "Remediation verified",
      findings: [{ id: "99999999-9999-4999-8999-999999999999", expected_version: 2 }],
    };

    const result = await recordRetest("11111111-1111-4111-8111-111111111111", "token-123", "33333333-3333-4333-8333-333333333333", payload);
    expect(result).toEqual(mockReceipt);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/v2/tenants/11111111-1111-4111-8111-111111111111/customer-demo/assessment-work/33333333-3333-4333-8333-333333333333/retests"
    );
  });

  it("handles error statuses correctly", async () => {
    const makeErrorMock = (status: number, detail: string) =>
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail }), {
          status,
          headers: { "Content-Type": "application/json" },
        })
      );

    vi.stubGlobal("fetch", makeErrorMock(401, "Unauthorized"));
    await expect(fetchAssessmentWorkList("t-1", "tok")).rejects.toThrow(UnauthorizedError);

    vi.stubGlobal("fetch", makeErrorMock(403, "Forbidden"));
    await expect(fetchAssessmentWorkList("t-1", "tok")).rejects.toThrow(ForbiddenError);

    vi.stubGlobal("fetch", makeErrorMock(404, "Not Found"));
    await expect(fetchAssessmentWorkList("t-1", "tok")).rejects.toThrow(NotFoundError);

    vi.stubGlobal("fetch", makeErrorMock(409, "CAS Conflict"));
    await expect(fetchAssessmentWorkList("t-1", "tok")).rejects.toThrow(ConflictError);

    vi.stubGlobal("fetch", makeErrorMock(413, "Body > 16KiB"));
    await expect(fetchAssessmentWorkList("t-1", "tok")).rejects.toThrow(PayloadTooLargeError);

    vi.stubGlobal("fetch", makeErrorMock(422, "Validation error"));
    await expect(fetchAssessmentWorkList("t-1", "tok")).rejects.toThrow(ValidationError);
  });
});
