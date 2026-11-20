import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { ConflictError, ForbiddenError, UnauthorizedError, ValidationError } from "./api";
import {
  createTrainingAssignment,
  createTrainingCourse,
  fetchTrainingAssignments,
  fetchTrainingCompletions,
  fetchTrainingCourses,
} from "./training-api";
import {
  CreateAssignmentPayload,
  CreateCoursePayload,
  TrainingAssignment,
  TrainingCourse,
  TrainingCompletion,
  TrainingSubTab,
} from "./training-types";
import "./training-workspace.css";

export interface TrainingWorkspaceProps {
  tenantId: string;
  token: string;
  userRole?: string;
  isActive?: boolean;
  onSessionExpired?: () => void;
}

const PAGE_SIZE = 10;

export const TrainingWorkspace: React.FC<TrainingWorkspaceProps> = ({
  tenantId,
  token,
  userRole,
  isActive = true,
  onSessionExpired,
}) => {
  const { t } = useTranslation();

  // ── Authoritative Role Fencing ──────────────────────────────────────────────
  // The customer demo remains whole-tenant Owner/ComplianceManager only.
  const normalizedRole = (userRole || "").toLowerCase();
  const isAuthorized = normalizedRole === "owner" || normalizedRole === "compliance_manager";

  // ── State ───────────────────────────────────────────────────────────────────
  const [subTab, setSubTab] = useState<TrainingSubTab>("assignments");
  const [courses, setCourses] = useState<TrainingCourse[]>([]);
  const [assignments, setAssignments] = useState<TrainingAssignment[]>([]);
  const [completions, setCompletions] = useState<TrainingCompletion[]>([]);

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isDenied, setIsDenied] = useState<boolean>(false);

  // Pagination per sub-tab
  const [assignmentPage, setAssignmentPage] = useState<number>(1);
  const [coursePage, setCoursePage] = useState<number>(1);
  const [completionPage, setCompletionPage] = useState<number>(1);

  // Assignment status filter
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Selected completion for details drawer
  const [selectedCompletion, setSelectedCompletion] = useState<TrainingCompletion | null>(null);

  // Modals
  const [showCourseModal, setShowCourseModal] = useState<boolean>(false);
  const [showAssignModal, setShowAssignModal] = useState<boolean>(false);

  // Course Form State
  const [courseForm, setCourseForm] = useState<CreateCoursePayload>({
    course_id: "",
    title: "",
    description: "",
    version: "1.0",
    provider: "lms",
    duration_minutes: 30,
    validity_period_days: 365,
  });
  const [courseSubmitting, setCourseSubmitting] = useState<boolean>(false);
  const [courseFormError, setCourseFormError] = useState<string | null>(null);
  const [uncertainCoursePayload, setUncertainCoursePayload] = useState<CreateCoursePayload | null>(null);
  const [courseReconcileStatus, setCourseReconcileStatus] = useState<string | null>(null);

  // Assignment Form State
  const [assignForm, setAssignForm] = useState<CreateAssignmentPayload>({
    course_id: "",
    workforce_email: "",
    due_date: "",
  });
  const [assignSubmitting, setAssignSubmitting] = useState<boolean>(false);
  const [assignFormError, setAssignFormError] = useState<string | null>(null);
  const [uncertainAssignPayload, setUncertainAssignPayload] = useState<CreateAssignmentPayload | null>(null);
  const [assignReconcileStatus, setAssignReconcileStatus] = useState<string | null>(null);

  // Reconciliation explicit decisions
  const [courseReconcileDecision, setCourseReconcileDecision] = useState<
    "adopt" | "resubmit" | "mismatch" | "absent" | null
  >(null);
  const [matchedServerCourse, setMatchedServerCourse] = useState<TrainingCourse | null>(null);

  const [assignReconcileDecision, setAssignReconcileDecision] = useState<
    "adopt" | "resubmit" | "mismatch" | "absent" | null
  >(null);
  const [matchedServerAssignment, setMatchedServerAssignment] = useState<TrainingAssignment | null>(null);

  // Fencing and request cancellation
  const isMountedRef = useRef<boolean>(true);
  const contextGenRef = useRef<number>(0);
  const refreshGenRef = useRef<number>(0);
  const courseReconcileAttemptRef = useRef<number>(0);
  const assignReconcileAttemptRef = useRef<number>(0);
  const courseReconcileAbortRef = useRef<AbortController | null>(null);
  const assignReconcileAbortRef = useRef<AbortController | null>(null);
  const uncertainCoursePayloadRef = useRef<CreateCoursePayload | null>(null);
  const uncertainAssignPayloadRef = useRef<CreateAssignmentPayload | null>(null);
  const committedCourseIdsRef = useRef<Set<string>>(new Set());
  const committedAssignmentIdsRef = useRef<Set<string>>(new Set());
  const sessionRef = useRef({ tenantId, token });
  const activeAbortRef = useRef<AbortController | null>(null);
  const onSessionExpiredRef = useRef(onSessionExpired);

  const contextKey = `${tenantId}:${token}:${normalizedRole}:${isActive}`;
  const [prevContextKey, setPrevContextKey] = useState(contextKey);

  if (contextKey !== prevContextKey) {
    setPrevContextKey(contextKey);
    setCourses([]);
    setAssignments([]);
    setCompletions([]);
    setSelectedCompletion(null);
    setShowCourseModal(false);
    setShowAssignModal(false);
    setCourseSubmitting(false);
    setAssignSubmitting(false);
    setCourseForm({
      course_id: "",
      title: "",
      description: "",
      version: "1.0",
      provider: "lms",
      duration_minutes: 30,
      validity_period_days: 365,
    });
    setAssignForm({
      course_id: "",
      workforce_email: "",
      due_date: "",
    });
    setCourseFormError(null);
    setAssignFormError(null);
    setError(null);
    setIsDenied(false);
    setUncertainCoursePayload(null);
    setUncertainAssignPayload(null);
    setCourseReconcileStatus(null);
    setAssignReconcileStatus(null);
    setCourseReconcileDecision(null);
    setAssignReconcileDecision(null);
    setMatchedServerCourse(null);
    setMatchedServerAssignment(null);
    setAssignmentPage(1);
    setCoursePage(1);
    setCompletionPage(1);
  }

  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  }, [onSessionExpired]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      contextGenRef.current += 1;
      if (activeAbortRef.current) {
        activeAbortRef.current.abort();
      }
      if (courseReconcileAbortRef.current) {
        courseReconcileAbortRef.current.abort();
      }
      if (assignReconcileAbortRef.current) {
        assignReconcileAbortRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    sessionRef.current = { tenantId, token };
    contextGenRef.current += 1;
    committedCourseIdsRef.current.clear();
    committedAssignmentIdsRef.current.clear();
    if (activeAbortRef.current) {
      activeAbortRef.current.abort();
    }
    if (courseReconcileAbortRef.current) {
      courseReconcileAbortRef.current.abort();
      courseReconcileAbortRef.current = null;
    }
    if (assignReconcileAbortRef.current) {
      assignReconcileAbortRef.current.abort();
      assignReconcileAbortRef.current = null;
    }
    courseReconcileAttemptRef.current += 1;
    assignReconcileAttemptRef.current += 1;
    uncertainCoursePayloadRef.current = null;
    uncertainAssignPayloadRef.current = null;
  }, [tenantId, token, normalizedRole, isActive]);

  // ── Load All Data ───────────────────────────────────────────────────────────
  const loadTrainingData = useCallback(async () => {
    if (!isAuthorized || !isActive) return;

    if (activeAbortRef.current) {
      activeAbortRef.current.abort();
    }
    const controller = new AbortController();
    activeAbortRef.current = controller;

    const currentContextGen = contextGenRef.current;
    const currentRefreshGen = ++refreshGenRef.current;
    const currentTenant = tenantId;
    const currentToken = token;

    setLoading(true);
    setError(null);
    setIsDenied(false);

    try {
      const [fetchedCourses, fetchedAssignments, fetchedCompletions] = await Promise.all([
        fetchTrainingCourses(currentTenant, currentToken, controller.signal),
        fetchTrainingAssignments(currentTenant, currentToken, undefined, controller.signal),
        fetchTrainingCompletions(currentTenant, currentToken, controller.signal),
      ]);

      if (!isMountedRef.current || contextGenRef.current !== currentContextGen || refreshGenRef.current !== currentRefreshGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      setCourses((prev) => {
        const fetchedIds = new Set(fetchedCourses.map((c) => c.course_id));
        const retained = prev.filter(
          (c) => committedCourseIdsRef.current.has(c.course_id) && !fetchedIds.has(c.course_id)
        );
        return [...retained, ...fetchedCourses];
      });
      setAssignments((prev) => {
        const fetchedIds = new Set(fetchedAssignments.map((a) => a.id));
        const retained = prev.filter(
          (a) => committedAssignmentIdsRef.current.has(a.id) && !fetchedIds.has(a.id)
        );
        return [...retained, ...fetchedAssignments];
      });
      setCompletions(fetchedCompletions);
      setLoading(false);
    } catch (err: unknown) {
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen || refreshGenRef.current !== currentRefreshGen) return;
      if (controller.signal.aborted) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      setLoading(false);
      if (err instanceof UnauthorizedError) {
        onSessionExpiredRef.current?.();
        return;
      }
      if (err instanceof ForbiddenError) {
        setIsDenied(true);
        setError(err.message || "Access denied: LMS module not entitled or role unauthorized.");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load training data.");
    }
  }, [isAuthorized, isActive, tenantId, token]);

  // Trigger load on session or active state change
  useEffect(() => {
    let ignore = false;
    if (isActive && isAuthorized) {
      void Promise.resolve().then(() => {
        if (!ignore) {
          void loadTrainingData();
        }
      });
    }
    return () => {
      ignore = true;
    };
  }, [isActive, isAuthorized, tenantId, token, loadTrainingData]);

  // ── Sub-tab Switching ───────────────────────────────────────────────────────
  const handleSelectSubTab = (tab: TrainingSubTab) => {
    setSubTab(tab);
    setError(null);
  };

  // ── Filtered & Paginated Data ───────────────────────────────────────────────
  const filteredAssignments = useMemo(() => {
    if (statusFilter === "all") return assignments;
    return assignments.filter((a) => a.status.toLowerCase() === statusFilter.toLowerCase());
  }, [assignments, statusFilter]);

  const paginatedAssignments = useMemo(() => {
    const start = (assignmentPage - 1) * PAGE_SIZE;
    return filteredAssignments.slice(start, start + PAGE_SIZE);
  }, [filteredAssignments, assignmentPage]);

  const totalAssignmentPages = Math.max(1, Math.ceil(filteredAssignments.length / PAGE_SIZE));

  const paginatedCourses = useMemo(() => {
    const start = (coursePage - 1) * PAGE_SIZE;
    return courses.slice(start, start + PAGE_SIZE);
  }, [courses, coursePage]);

  const totalCoursePages = Math.max(1, Math.ceil(courses.length / PAGE_SIZE));

  const paginatedCompletions = useMemo(() => {
    const start = (completionPage - 1) * PAGE_SIZE;
    return completions.slice(start, start + PAGE_SIZE);
  }, [completions, completionPage]);

  const totalCompletionPages = Math.max(1, Math.ceil(completions.length / PAGE_SIZE));

  // ── Course Registration ─────────────────────────────────────────────────────
  const handleRegisterCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (uncertainCoursePayload) return;
    if (!courseForm.course_id.trim() || !courseForm.title.trim() || !courseForm.description.trim()) {
      setCourseFormError("Please provide course ID, title, and description.");
      return;
    }

    if (courseReconcileAbortRef.current) {
      courseReconcileAbortRef.current.abort();
      courseReconcileAbortRef.current = null;
    }
    courseReconcileAttemptRef.current += 1;
    uncertainCoursePayloadRef.current = null;

    setCourseSubmitting(true);
    setCourseFormError(null);
    setUncertainCoursePayload(null);
    setCourseReconcileStatus(null);
    setCourseReconcileDecision(null);
    setMatchedServerCourse(null);

    const payload = { ...courseForm };
    const currentContextGen = contextGenRef.current;
    const currentTenant = tenantId;
    const currentToken = token;

    try {
      const created = await createTrainingCourse(currentTenant, currentToken, payload);
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      committedCourseIdsRef.current.add(created.course_id);
      setCourses((prev) => [created, ...prev.filter((c) => c.course_id !== created.course_id)]);
      setShowCourseModal(false);
      setCourseForm({
        course_id: "",
        title: "",
        description: "",
        version: "1.0",
        provider: "lms",
        duration_minutes: 30,
        validity_period_days: 365,
      });
    } catch (err: unknown) {
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      if (err instanceof UnauthorizedError) {
        onSessionExpiredRef.current?.();
        return;
      }
      if (err instanceof ConflictError) {
        setCourseFormError("A course with this ID already exists (409 Conflict).");
      } else if (err instanceof ValidationError) {
        setCourseFormError(err.message || "Validation failed for course payload.");
      } else if (err instanceof ForbiddenError) {
        setCourseFormError("Permission denied to register courses.");
      } else {
        uncertainCoursePayloadRef.current = payload;
        setUncertainCoursePayload(payload);
        setCourseFormError("Network error during registration. Course status is uncertain.");
      }
    } finally {
      if (isMountedRef.current && contextGenRef.current === currentContextGen && sessionRef.current.tenantId === currentTenant) {
        setCourseSubmitting(false);
      }
    }
  };

  const handleReconcileCourse = async () => {
    if (!uncertainCoursePayload) return;
    const targetPayload = uncertainCoursePayload;
    const currentContextGen = contextGenRef.current;
    const currentAttempt = ++courseReconcileAttemptRef.current;
    const currentTenant = tenantId;
    const currentToken = token;

    if (courseReconcileAbortRef.current) {
      courseReconcileAbortRef.current.abort();
    }
    const controller = new AbortController();
    courseReconcileAbortRef.current = controller;

    setCourseReconcileStatus("Checking server records...");
    setCourseReconcileDecision(null);
    setMatchedServerCourse(null);

    try {
      const freshCourses = await fetchTrainingCourses(currentTenant, currentToken, controller.signal);
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (controller.signal.aborted) return;
      if (currentAttempt !== courseReconcileAttemptRef.current) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;
      if (uncertainCoursePayloadRef.current !== targetPayload) return;

      setCourses(freshCourses);
      const candidates = freshCourses.filter((c) => c.course_id === targetPayload.course_id);

      if (candidates.length === 0) {
        setMatchedServerCourse(null);
        setCourseReconcileDecision("absent");
        setCourseReconcileStatus(
          "Course not found on server. You may resubmit the registration or abandon the draft."
        );
      } else if (candidates.length > 1) {
        setMatchedServerCourse(null);
        setCourseReconcileDecision("mismatch");
        setCourseReconcileStatus(
          "Multiple registrations found for this course ID on the server. Registration remains uncertain; please review before proceeding."
        );
      } else {
        const match = candidates[0];
        const isExactMatch =
          match.title === targetPayload.title &&
          (match.description || "") === (targetPayload.description || "") &&
          (match.version || "1.0") === (targetPayload.version || "1.0") &&
          (match.provider || "lms") === (targetPayload.provider || "lms") &&
          (match.duration_minutes ?? null) === (targetPayload.duration_minutes ?? null) &&
          (match.validity_period_days ?? 365) === (targetPayload.validity_period_days ?? 365);

        setMatchedServerCourse(match);
        if (isExactMatch) {
          setCourseReconcileDecision("adopt");
          setCourseReconcileStatus("Course verified on server! Registration confirmed.");
        } else {
          setCourseReconcileDecision("mismatch");
          setCourseReconcileStatus(
            "An existing course with this ID was found on the server, but with different details. Please review before proceeding."
          );
        }
      }
    } catch (err: unknown) {
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (controller.signal.aborted) return;
      if (currentAttempt !== courseReconcileAttemptRef.current) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;
      if (uncertainCoursePayloadRef.current !== targetPayload) return;

      if (err instanceof UnauthorizedError) {
        onSessionExpiredRef.current?.();
        return;
      }
      setCourseReconcileStatus(
        `Reconciliation check failed: ${err instanceof Error ? err.message : "Network error"}`
      );
    }
  };

  const handleResubmitCourse = async () => {
    if (!uncertainCoursePayload) return;
    const payload = { ...uncertainCoursePayload };
    if (courseReconcileAbortRef.current) {
      courseReconcileAbortRef.current.abort();
      courseReconcileAbortRef.current = null;
    }
    courseReconcileAttemptRef.current += 1;
    uncertainCoursePayloadRef.current = null;

    setUncertainCoursePayload(null);
    setCourseReconcileDecision(null);
    setCourseReconcileStatus(null);
    setCourseSubmitting(true);
    setCourseFormError(null);

    const currentContextGen = contextGenRef.current;
    const currentTenant = tenantId;
    const currentToken = token;

    try {
      const created = await createTrainingCourse(currentTenant, currentToken, payload);
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      committedCourseIdsRef.current.add(created.course_id);
      setCourses((prev) => [created, ...prev.filter((c) => c.course_id !== created.course_id)]);
      setShowCourseModal(false);
      setCourseForm({
        course_id: "",
        title: "",
        description: "",
        version: "1.0",
        provider: "lms",
        duration_minutes: 30,
        validity_period_days: 365,
      });
    } catch (err: unknown) {
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      if (err instanceof UnauthorizedError) {
        onSessionExpiredRef.current?.();
        return;
      }
      if (err instanceof ConflictError) {
        setCourseFormError("A course with this ID already exists (409 Conflict).");
      } else if (err instanceof ValidationError) {
        setCourseFormError(err.message || "Validation failed for course payload.");
      } else if (err instanceof ForbiddenError) {
        setCourseFormError("Permission denied to register courses.");
      } else {
        uncertainCoursePayloadRef.current = payload;
        setUncertainCoursePayload(payload);
        setCourseFormError("Network error during registration. Course status is uncertain.");
      }
    } finally {
      if (isMountedRef.current && contextGenRef.current === currentContextGen && sessionRef.current.tenantId === currentTenant) {
        setCourseSubmitting(false);
      }
    }
  };

  const handleAdoptCourse = (course?: TrainingCourse) => {
    courseReconcileAttemptRef.current += 1;
    if (courseReconcileAbortRef.current) {
      courseReconcileAbortRef.current.abort();
      courseReconcileAbortRef.current = null;
    }
    const toAdopt = course || matchedServerCourse;
    if (toAdopt) {
      setCourses((prev) => [toAdopt, ...prev.filter((c) => c.course_id !== toAdopt.course_id)]);
    }
    uncertainCoursePayloadRef.current = null;
    setUncertainCoursePayload(null);
    setCourseReconcileDecision(null);
    setCourseReconcileStatus(null);
    setShowCourseModal(false);
    setCourseFormError(null);
  };

  const handleAbandonCourse = () => {
    courseReconcileAttemptRef.current += 1;
    if (courseReconcileAbortRef.current) {
      courseReconcileAbortRef.current.abort();
      courseReconcileAbortRef.current = null;
    }
    uncertainCoursePayloadRef.current = null;
    setUncertainCoursePayload(null);
    setCourseReconcileDecision(null);
    setCourseReconcileStatus(null);
    setCourseFormError(null);
  };

  // ── Training Assignment ─────────────────────────────────────────────────────
  const handleAssignTraining = async (e: React.FormEvent) => {
    e.preventDefault();
    if (uncertainAssignPayload) return;
    if (!assignForm.course_id.trim() || !assignForm.workforce_email.trim() || !assignForm.due_date.trim()) {
      setAssignFormError("Please provide course ID, workforce email, and due date.");
      return;
    }

    if (assignReconcileAbortRef.current) {
      assignReconcileAbortRef.current.abort();
      assignReconcileAbortRef.current = null;
    }
    assignReconcileAttemptRef.current += 1;
    uncertainAssignPayloadRef.current = null;

    setAssignSubmitting(true);
    setAssignFormError(null);
    setUncertainAssignPayload(null);
    setAssignReconcileStatus(null);
    setAssignReconcileDecision(null);
    setMatchedServerAssignment(null);

    const payload = { ...assignForm };
    const currentContextGen = contextGenRef.current;
    const currentTenant = tenantId;
    const currentToken = token;

    try {
      const created = await createTrainingAssignment(currentTenant, currentToken, payload);
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      committedAssignmentIdsRef.current.add(created.id);
      setAssignments((prev) => [created, ...prev.filter((a) => a.id !== created.id)]);
      setShowAssignModal(false);
      setAssignForm({
        course_id: "",
        workforce_email: "",
        due_date: "",
      });
    } catch (err: unknown) {
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      if (err instanceof UnauthorizedError) {
        onSessionExpiredRef.current?.();
        return;
      }
      if (err instanceof ValidationError) {
        setAssignFormError(err.message || "Learner email must belong to an active tenant member.");
      } else if (err instanceof ForbiddenError) {
        setAssignFormError("Permission denied to assign training.");
      } else {
        uncertainAssignPayloadRef.current = payload;
        setUncertainAssignPayload(payload);
        setAssignFormError("Network error during assignment. Assignment status is uncertain.");
      }
    } finally {
      if (isMountedRef.current && contextGenRef.current === currentContextGen && sessionRef.current.tenantId === currentTenant) {
        setAssignSubmitting(false);
      }
    }
  };

  const handleReconcileAssignment = async () => {
    if (!uncertainAssignPayload) return;
    const targetPayload = uncertainAssignPayload;
    const currentContextGen = contextGenRef.current;
    const currentAttempt = ++assignReconcileAttemptRef.current;
    const currentTenant = tenantId;
    const currentToken = token;

    if (assignReconcileAbortRef.current) {
      assignReconcileAbortRef.current.abort();
    }
    const controller = new AbortController();
    assignReconcileAbortRef.current = controller;

    setAssignReconcileStatus("Checking server records...");
    setAssignReconcileDecision(null);
    setMatchedServerAssignment(null);

    try {
      const freshAssignments = await fetchTrainingAssignments(currentTenant, currentToken, undefined, controller.signal);
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (controller.signal.aborted) return;
      if (currentAttempt !== assignReconcileAttemptRef.current) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;
      if (uncertainAssignPayloadRef.current !== targetPayload) return;

      setAssignments(freshAssignments);
      const candidates = freshAssignments.filter(
        (a) =>
          a.course_id === targetPayload.course_id &&
          a.workforce_email.toLowerCase() === targetPayload.workforce_email.toLowerCase()
      );

      if (candidates.length === 0) {
        setMatchedServerAssignment(null);
        setAssignReconcileDecision("absent");
        setAssignReconcileStatus(
          "Assignment not found on server. You may resubmit the assignment or abandon the draft."
        );
      } else if (candidates.length > 1) {
        setMatchedServerAssignment(null);
        setAssignReconcileDecision("mismatch");
        setAssignReconcileStatus(
          "Multiple candidate assignments found for this course and learner on the server. Status remains uncertain; please review before proceeding."
        );
      } else {
        const candidate = candidates[0];
        const attemptedTime = new Date(targetPayload.due_date).getTime();
        const matchTime = new Date(candidate.due_date).getTime();
        const isDueDateMatch = !isNaN(attemptedTime) && !isNaN(matchTime) && attemptedTime === matchTime;

        // User ID check: if explicit user_id was submitted, must match candidate.user_id
        // If omitted, server-resolved user is compatible
        const isUserMatch = !targetPayload.user_id || candidate.user_id === targetPayload.user_id;

        // Control reference check: must strictly match intent
        const attemptedCtrlId = targetPayload.control_id ? String(targetPayload.control_id).toLowerCase() : null;
        const candidateCtrlId = candidate.control_id ? String(candidate.control_id).toLowerCase() : null;
        const isControlIdMatch = attemptedCtrlId === candidateCtrlId;

        const attemptedCtrlType = targetPayload.control_type ? String(targetPayload.control_type).toLowerCase() : null;
        const candidateCtrlType = candidate.control_type ? String(candidate.control_type).toLowerCase() : null;
        const isControlTypeMatch = attemptedCtrlType === candidateCtrlType;

        const isExactMatch = isDueDateMatch && isUserMatch && isControlIdMatch && isControlTypeMatch;

        setMatchedServerAssignment(candidate);
        if (isExactMatch) {
          setAssignReconcileDecision("adopt");
          setAssignReconcileStatus("Assignment verified on server! Assignment confirmed.");
        } else {
          setAssignReconcileDecision("mismatch");
          setAssignReconcileStatus(
            "An existing assignment for this course and learner was found with different details."
          );
        }
      }
    } catch (err: unknown) {
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (controller.signal.aborted) return;
      if (currentAttempt !== assignReconcileAttemptRef.current) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;
      if (uncertainAssignPayloadRef.current !== targetPayload) return;

      if (err instanceof UnauthorizedError) {
        onSessionExpiredRef.current?.();
        return;
      }
      setAssignReconcileStatus(
        `Reconciliation check failed: ${err instanceof Error ? err.message : "Network error"}`
      );
    }
  };

  const handleResubmitAssignment = async () => {
    if (!uncertainAssignPayload) return;
    const payload = { ...uncertainAssignPayload };
    if (assignReconcileAbortRef.current) {
      assignReconcileAbortRef.current.abort();
      assignReconcileAbortRef.current = null;
    }
    assignReconcileAttemptRef.current += 1;
    uncertainAssignPayloadRef.current = null;

    setUncertainAssignPayload(null);
    setAssignReconcileDecision(null);
    setAssignReconcileStatus(null);
    setAssignSubmitting(true);
    setAssignFormError(null);

    const currentContextGen = contextGenRef.current;
    const currentTenant = tenantId;
    const currentToken = token;

    try {
      const created = await createTrainingAssignment(currentTenant, currentToken, payload);
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      committedAssignmentIdsRef.current.add(created.id);
      setAssignments((prev) => [created, ...prev.filter((a) => a.id !== created.id)]);
      setShowAssignModal(false);
      setAssignForm({
        course_id: "",
        workforce_email: "",
        due_date: "",
      });
    } catch (err: unknown) {
      if (!isMountedRef.current || contextGenRef.current !== currentContextGen) return;
      if (sessionRef.current.tenantId !== currentTenant || sessionRef.current.token !== currentToken) return;

      if (err instanceof UnauthorizedError) {
        onSessionExpiredRef.current?.();
        return;
      }
      if (err instanceof ValidationError) {
        setAssignFormError(err.message || "Learner email must belong to an active tenant member.");
      } else if (err instanceof ForbiddenError) {
        setAssignFormError("Permission denied to assign training.");
      } else {
        uncertainAssignPayloadRef.current = payload;
        setUncertainAssignPayload(payload);
        setAssignFormError("Network error during assignment. Assignment status is uncertain.");
      }
    } finally {
      if (isMountedRef.current && contextGenRef.current === currentContextGen && sessionRef.current.tenantId === currentTenant) {
        setAssignSubmitting(false);
      }
    }
  };

  const handleAdoptAssignment = (assignment?: TrainingAssignment) => {
    assignReconcileAttemptRef.current += 1;
    if (assignReconcileAbortRef.current) {
      assignReconcileAbortRef.current.abort();
      assignReconcileAbortRef.current = null;
    }
    const toAdopt = assignment || matchedServerAssignment;
    if (toAdopt) {
      setAssignments((prev) => [toAdopt, ...prev.filter((a) => a.id !== toAdopt.id)]);
    }
    uncertainAssignPayloadRef.current = null;
    setUncertainAssignPayload(null);
    setAssignReconcileDecision(null);
    setAssignReconcileStatus(null);
    setShowAssignModal(false);
    setAssignFormError(null);
  };

  const handleAbandonAssignment = () => {
    assignReconcileAttemptRef.current += 1;
    if (assignReconcileAbortRef.current) {
      assignReconcileAbortRef.current.abort();
      assignReconcileAbortRef.current = null;
    }
    uncertainAssignPayloadRef.current = null;
    setUncertainAssignPayload(null);
    setAssignReconcileDecision(null);
    setAssignReconcileStatus(null);
    setAssignFormError(null);
  };

  // ── Render Access Denied ────────────────────────────────────────────────────
  if (!isAuthorized) {
    return (
      <div
        className="mw-card"
        data-testid="training-role-denied"
        role="status"
        style={{ padding: "1.5rem", borderLeft: "4px solid #d97706", backgroundColor: "#fffbeb" }}
      >
        <h3 style={{ marginTop: 0 }}>{t("portal.accessDenied") || "Access Denied (403 Forbidden)"}</h3>
        <p style={{ margin: 0 }}>
          {t("portal.operationsDeniedNotice") ||
            "Only Tenant Owners and Compliance Managers have permission to view or manage compliance training records."}
        </p>
      </div>
    );
  }

  return (
    <div className="training-workspace" data-testid="training-workspace">
      {/* Workspace Header */}
      <div className="training-header">
        <div className="training-header-titles">
          <h2>{t("portal.tabTraining") || "Training & LMS"}</h2>
          <p>
            {t("portal.trainingSubtitle") ||
              "Manage compliance training requirements, course catalog references, and verified completion evidence."}
          </p>
        </div>
        <div className="training-actions">
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="refresh-training-btn"
            disabled={loading}
            onClick={() => void loadTrainingData()}
          >
            {loading ? t("portal.refreshingOperationsBtn") || "Refreshing..." : t("common.refresh") || "Refresh"}
          </button>
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="open-register-course-btn"
            onClick={() => {
              setShowCourseModal(true);
              setCourseFormError(null);
            }}
          >
            {t("portal.registerCourseBtn") || "Register Course Reference"}
          </button>
          <button
            type="button"
            className="mw-btn mw-btn-primary"
            data-testid="open-assign-modal-btn"
            onClick={() => {
              setShowAssignModal(true);
              setAssignFormError(null);
            }}
          >
            {t("portal.assignTrainingBtn") || "Assign Training"}
          </button>
        </div>
      </div>

      {/* Partner Connection Status Banner */}
      <div className="training-partner-banner" data-testid="partner-status-banner">
        <div>
          <span className="training-partner-banner-status" data-testid="training-partner-status">
            ✓ {t("portal.trainingPartnerStatus") || "Simulated LMS Integration (Local Contract Verification)"}
          </span>
          <div style={{ marginTop: "0.25rem", color: "#15803d", fontSize: "0.8125rem" }}>
            Conformly manages compliance requirements, assignments, and verified completion evidence. Course content,
            lessons, quizzes, and learner portals are hosted and delivered by the external LMS platform.
          </div>
        </div>
      </div>

      {/* Error / Denied Notices */}
      {isDenied && (
        <div
          role="status"
          className="mw-card"
          data-testid="training-denied"
          style={{ padding: "1.25rem", borderLeft: "4px solid #ef4444", backgroundColor: "#fef2f2" }}
        >
          <h4 style={{ margin: "0 0 0.25rem 0", color: "#991b1b" }}>Module Access Denied</h4>
          <p style={{ margin: 0, color: "#b91c1c" }}>
            {error || "The LMS integration module is not enabled for this tenant tier or your session lacks permission."}
          </p>
        </div>
      )}

      {error && !isDenied && (
        <div
          role="status"
          className="mw-card"
          data-testid="training-error"
          style={{ padding: "1rem", borderLeft: "4px solid #ef4444", backgroundColor: "#fef2f2" }}
        >
          <p style={{ margin: 0, color: "#b91c1c" }}>{error}</p>
        </div>
      )}

      {/* Sub-tab Navigation */}
      <div className="training-subtabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={subTab === "assignments"}
          className={`training-subtab-btn ${subTab === "assignments" ? "active" : ""}`}
          data-testid="subtab-assignments"
          onClick={() => handleSelectSubTab("assignments")}
        >
          {t("portal.trainingAssignmentsTitle") || "Training Assignments"}
          <span className="training-subtab-badge" data-testid="badge-assignments-count">
            {assignments.length}
          </span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={subTab === "courses"}
          className={`training-subtab-btn ${subTab === "courses" ? "active" : ""}`}
          data-testid="subtab-courses"
          onClick={() => handleSelectSubTab("courses")}
        >
          {t("portal.trainingCoursesTitle") || "Course Catalog References"}
          <span className="training-subtab-badge" data-testid="badge-courses-count">
            {courses.length}
          </span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={subTab === "completions"}
          className={`training-subtab-btn ${subTab === "completions" ? "active" : ""}`}
          data-testid="subtab-completions"
          onClick={() => handleSelectSubTab("completions")}
        >
          {t("portal.trainingCompletionsTitle") || "Verified Completions"}
          <span className="training-subtab-badge" data-testid="badge-completions-count">
            {completions.length}
          </span>
        </button>
      </div>

      {/* ── Sub-tab 1: Assignments ─────────────────────────────────────────── */}
      {subTab === "assignments" && (
        <div data-testid="training-assignments-panel">
          <div className="training-filters">
            <label htmlFor="assignment-filter" style={{ fontSize: "0.8125rem", fontWeight: 600 }}>
              {t("common.status") || "Status"}:
            </label>
            <select
              id="assignment-filter"
              className="training-form-select"
              data-testid="assignment-status-filter"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setAssignmentPage(1);
              }}
            >
              <option value="all">{t("common.all") || "All Statuses"}</option>
              <option value="assigned">Assigned</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="overdue">Overdue</option>
            </select>
            <span style={{ fontSize: "0.75rem", color: "#6b7280", marginLeft: "auto" }}>
              Total: {filteredAssignments.length}
            </span>
          </div>

          <div className="training-table-container" style={{ marginTop: "0.75rem" }}>
            {filteredAssignments.length === 0 ? (
              <div className="training-empty-state" data-testid="assignments-empty">
                <h4>No Training Assignments Found</h4>
                <p>Assign courses to active workforce members to track compliance requirements.</p>
              </div>
            ) : (
              <>
                <table className="training-table" data-testid="assignments-table">
                  <thead>
                    <tr>
                      <th>Course ID</th>
                      <th>Learner Email</th>
                      <th>Due Date</th>
                      <th>Status</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedAssignments.map((a) => (
                      <tr key={a.id} data-testid={`assignment-row-${a.id}`}>
                        <td>
                          <strong>{a.course_id}</strong>
                        </td>
                        <td>{a.workforce_email}</td>
                        <td>{new Date(a.due_date).toLocaleDateString()}</td>
                        <td>
                          <span
                            className={`training-status-badge status-${a.status.toLowerCase().replace("_", "-")}`}
                            data-testid={`assignment-status-${a.id}`}
                          >
                            {a.status}
                          </span>
                        </td>
                        <td>{new Date(a.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="training-pagination">
                  <span data-testid="assignment-page-range">
                    Showing {filteredAssignments.length === 0 ? 0 : (assignmentPage - 1) * PAGE_SIZE + 1}–
                    {Math.min(assignmentPage * PAGE_SIZE, filteredAssignments.length)} of {filteredAssignments.length}{" "}
                    loaded
                  </span>
                  <div className="training-pagination-controls">
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="prev-assignment-page"
                      disabled={assignmentPage <= 1}
                      onClick={() => setAssignmentPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="next-assignment-page"
                      disabled={assignmentPage >= totalAssignmentPages}
                      onClick={() => setAssignmentPage((p) => Math.min(totalAssignmentPages, p + 1))}
                    >
                      Next
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Sub-tab 2: Course Catalog References ────────────────────────────── */}
      {subTab === "courses" && (
        <div data-testid="training-courses-panel">
          <div className="training-table-container">
            {courses.length === 0 ? (
              <div className="training-empty-state" data-testid="courses-empty">
                <h4>No Courses Registered</h4>
                <p>Register reference metadata for external courses to assign them to your team.</p>
              </div>
            ) : (
              <>
                <table className="training-table" data-testid="courses-table">
                  <thead>
                    <tr>
                      <th>Course ID</th>
                      <th>Title</th>
                      <th>Version</th>
                      <th>Provider</th>
                      <th>Duration</th>
                      <th>Validity</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedCourses.map((c) => (
                      <tr key={c.id} data-testid={`course-row-${c.course_id}`}>
                        <td>
                          <strong>{c.course_id}</strong>
                        </td>
                        <td>{c.title}</td>
                        <td>{c.version}</td>
                        <td>{c.provider}</td>
                        <td>{c.duration_minutes} min</td>
                        <td>{c.validity_period_days} days</td>
                        <td>
                          <span
                            className="training-status-badge status-completed"
                            style={{ backgroundColor: c.is_active ? "#ecfdf5" : "#f3f4f6" }}
                          >
                            {c.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="training-pagination">
                  <span data-testid="course-page-range">
                    Showing {courses.length === 0 ? 0 : (coursePage - 1) * PAGE_SIZE + 1}–
                    {Math.min(coursePage * PAGE_SIZE, courses.length)} of {courses.length} loaded
                  </span>
                  <div className="training-pagination-controls">
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="prev-course-page"
                      disabled={coursePage <= 1}
                      onClick={() => setCoursePage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="next-course-page"
                      disabled={coursePage >= totalCoursePages}
                      onClick={() => setCoursePage((p) => Math.min(totalCoursePages, p + 1))}
                    >
                      Next
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Sub-tab 3: Verified Completions ─────────────────────────────────── */}
      {subTab === "completions" && (
        <div data-testid="training-completions-panel">
          <div className="training-table-container">
            {completions.length === 0 ? (
              <div className="training-empty-state" data-testid="completions-empty">
                <h4>No Verified Completions Recorded</h4>
                <p>Completions are submitted by the external LMS through the signed callback endpoint.</p>
              </div>
            ) : (
              <>
                <table className="training-table" data-testid="completions-table">
                  <thead>
                    <tr>
                      <th>Course</th>
                      <th>Learner Email</th>
                      <th>Completed At</th>
                      <th>Score</th>
                      <th>Verification</th>
                      <th>Evidence ID</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedCompletions.map((comp) => (
                      <tr key={comp.id} data-testid={`completion-row-${comp.id}`}>
                        <td>
                          <strong>{comp.course_id}</strong> (v{comp.course_version})
                        </td>
                        <td>{comp.workforce_email}</td>
                        <td>{new Date(comp.completed_at).toLocaleString()}</td>
                        <td>{comp.score !== null && comp.score !== undefined ? `${comp.score}%` : "—"}</td>
                        <td>{comp.verified_via}</td>
                        <td>
                          {comp.evidence_id ? (
                            <span className="evidence-badge" data-testid="evidence-id">
                              {comp.evidence_id.slice(0, 8)}...
                            </span>
                          ) : (
                            <span style={{ color: "#9ca3af", fontSize: "0.75rem" }}>None</span>
                          )}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                            data-testid={`view-completion-${comp.id}`}
                            onClick={() => setSelectedCompletion(comp)}
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="training-pagination">
                  <span data-testid="completion-page-range">
                    Showing {completions.length === 0 ? 0 : (completionPage - 1) * PAGE_SIZE + 1}–
                    {Math.min(completionPage * PAGE_SIZE, completions.length)} of {completions.length} loaded
                  </span>
                  <div className="training-pagination-controls">
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="prev-completion-page"
                      disabled={completionPage <= 1}
                      onClick={() => setCompletionPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="next-completion-page"
                      disabled={completionPage >= totalCompletionPages}
                      onClick={() => setCompletionPage((p) => Math.min(totalCompletionPages, p + 1))}
                    >
                      Next
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Completion Detail Modal ────────────────────────────────────────── */}
      {selectedCompletion && (
        <div className="training-modal-overlay" data-testid="completion-detail-modal">
          <div className="training-modal">
            <div className="training-modal-header">
              <h3>Verified Completion Evidence</h3>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="close-completion-detail-btn"
                onClick={() => setSelectedCompletion(null)}
              >
                ✕
              </button>
            </div>
            <div className="training-modal-body">
              <div className="training-form-group">
                <label>Course Identifier & Version</label>
                <div data-testid="detail-course">
                  {selectedCompletion.course_id} (Version {selectedCompletion.course_version})
                </div>
              </div>
              <div className="training-form-group">
                <label>Learner Workforce Email</label>
                <div data-testid="detail-learner">{selectedCompletion.workforce_email}</div>
              </div>
              <div className="training-form-group">
                <label>Completion Timestamp</label>
                <div data-testid="detail-completed-at">{new Date(selectedCompletion.completed_at).toUTCString()}</div>
              </div>
              <div className="training-form-group">
                <label>Score</label>
                <div data-testid="detail-score">
                  {selectedCompletion.score !== null && selectedCompletion.score !== undefined
                    ? `${selectedCompletion.score}%`
                    : "Not graded"}
                </div>
              </div>
              {selectedCompletion.certificate_id && (
                <div className="training-form-group">
                  <label>Certificate ID</label>
                  <div data-testid="detail-certificate">{selectedCompletion.certificate_id}</div>
                </div>
              )}
              <div className="training-form-group">
                <label>Verification Method</label>
                <div data-testid="detail-verification-method">{selectedCompletion.verified_via}</div>
              </div>
              <div className="training-form-group">
                <label>Compliance Evidence Linkage</label>
                <div data-testid="detail-evidence-linkage">
                  {selectedCompletion.evidence_id ? (
                    <span className="evidence-badge" data-testid="detail-evidence-id">
                      {selectedCompletion.evidence_id}
                    </span>
                  ) : (
                    <span style={{ color: "#ef4444" }}>No evidence minted (attempt did not meet passing criteria)</span>
                  )}
                </div>
              </div>
            </div>
            <div className="training-modal-footer">
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                onClick={() => setSelectedCompletion(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Register Course Modal ─────────────────────────────────────────── */}
      {showCourseModal && (
        <div className="training-modal-overlay" data-testid="register-course-modal">
          <div className="training-modal">
            <form onSubmit={handleRegisterCourse}>
              <div className="training-modal-header">
                <h3>{t("portal.registerCourseBtn") || "Register Course Reference"}</h3>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  data-testid="cancel-register-course-btn"
                  onClick={() => setShowCourseModal(false)}
                >
                  ✕
                </button>
              </div>

              <div className="training-modal-body">
                {uncertainCoursePayload && (
                  <div className="training-uncertain-notice" data-testid="uncertain-course-notice">
                    <strong>Connection Interrupted</strong>
                    <span>
                      The registration request timed out or returned an uncertain status. Please verify before
                      re-submitting to prevent duplicate courses.
                    </span>
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem", flexWrap: "wrap" }}>
                      {!courseReconcileDecision && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-primary"
                            data-testid="reconcile-course-btn"
                            onClick={() => void handleReconcileCourse()}
                          >
                            Reconcile with Server
                          </button>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="dismiss-uncertain-course-btn"
                            onClick={handleAbandonCourse}
                          >
                            Dismiss
                          </button>
                        </>
                      )}
                      {courseReconcileDecision === "absent" && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-primary"
                            data-testid="reconcile-resubmit-btn"
                            onClick={() => void handleResubmitCourse()}
                          >
                            Resubmit Registration
                          </button>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="reconcile-abandon-btn"
                            onClick={handleAbandonCourse}
                          >
                            Abandon Draft
                          </button>
                        </>
                      )}
                      {(courseReconcileDecision === "adopt" || (courseReconcileDecision === "mismatch" && matchedServerCourse !== null)) && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-primary"
                            data-testid="reconcile-adopt-btn"
                            onClick={() => handleAdoptCourse()}
                          >
                            {courseReconcileDecision === "mismatch" ? "Adopt Server Course" : "Confirm & Adopt"}
                          </button>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="reconcile-abandon-btn"
                            onClick={handleAbandonCourse}
                          >
                            Abandon Draft
                          </button>
                        </>
                      )}
                      {courseReconcileDecision === "mismatch" && matchedServerCourse === null && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="reconcile-abandon-btn"
                            onClick={handleAbandonCourse}
                          >
                            Abandon Draft
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {courseReconcileStatus && (
                  <div
                    data-testid="reconcile-course-status"
                    style={{
                      padding: "0.5rem",
                      borderRadius: "4px",
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                      backgroundColor: courseReconcileStatus.includes("verified") ? "#ecfdf5" : "#fffbeb",
                      color: courseReconcileStatus.includes("verified") ? "#065f46" : "#92400e",
                    }}
                  >
                    {courseReconcileStatus}
                  </div>
                )}

                {courseFormError && (
                  <div style={{ color: "#b91c1c", fontSize: "0.875rem", backgroundColor: "#fef2f2", padding: "0.5rem", borderRadius: "4px" }}>
                    {courseFormError}
                  </div>
                )}

                <div className="training-form-group">
                  <label htmlFor="course-id">Course Identifier (ID) *</label>
                  <input
                    id="course-id"
                    type="text"
                    className="training-form-input"
                    data-testid="input-course-id"
                    required
                    value={courseForm.course_id}
                    onChange={(e) => setCourseForm({ ...courseForm, course_id: e.target.value })}
                    placeholder="e.g. sec-aware-2026"
                  />
                  <span className="training-form-help">Matches the external LMS course ID.</span>
                </div>

                <div className="training-form-group">
                  <label htmlFor="course-title">Course Title *</label>
                  <input
                    id="course-title"
                    type="text"
                    className="training-form-input"
                    data-testid="input-course-title"
                    required
                    value={courseForm.title}
                    onChange={(e) => setCourseForm({ ...courseForm, title: e.target.value })}
                    placeholder="e.g. Security Awareness & Phishing"
                  />
                </div>

                <div className="training-form-group">
                  <label htmlFor="course-desc">Description *</label>
                  <textarea
                    id="course-desc"
                    className="training-form-textarea"
                    data-testid="input-course-description"
                    rows={2}
                    required
                    value={courseForm.description}
                    onChange={(e) => setCourseForm({ ...courseForm, description: e.target.value })}
                    placeholder="Brief description of learning objectives..."
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="training-form-group">
                    <label htmlFor="course-version">Version</label>
                    <input
                      id="course-version"
                      type="text"
                      className="training-form-input"
                      data-testid="input-course-version"
                      value={courseForm.version}
                      onChange={(e) => setCourseForm({ ...courseForm, version: e.target.value })}
                    />
                  </div>
                  <div className="training-form-group">
                    <label htmlFor="course-provider">Provider</label>
                    <input
                      id="course-provider"
                      type="text"
                      className="training-form-input"
                      data-testid="input-course-provider"
                      value={courseForm.provider}
                      onChange={(e) => setCourseForm({ ...courseForm, provider: e.target.value })}
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="training-form-group">
                    <label htmlFor="course-duration">Duration (Minutes)</label>
                    <input
                      id="course-duration"
                      type="number"
                      min={1}
                      className="training-form-input"
                      data-testid="input-course-duration"
                      value={courseForm.duration_minutes}
                      onChange={(e) => setCourseForm({ ...courseForm, duration_minutes: Number(e.target.value) })}
                    />
                  </div>
                  <div className="training-form-group">
                    <label htmlFor="course-validity">Validity (Days)</label>
                    <input
                      id="course-validity"
                      type="number"
                      min={1}
                      className="training-form-input"
                      data-testid="input-course-validity"
                      value={courseForm.validity_period_days}
                      onChange={(e) => setCourseForm({ ...courseForm, validity_period_days: Number(e.target.value) })}
                    />
                  </div>
                </div>
              </div>

              <div className="training-modal-footer">
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => setShowCourseModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="mw-btn mw-btn-primary"
                  data-testid="submit-register-course-btn"
                  disabled={courseSubmitting || Boolean(uncertainCoursePayload)}
                >
                  {courseSubmitting ? "Registering..." : "Register Course"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Assign Training Modal ─────────────────────────────────────────── */}
      {showAssignModal && (
        <div className="training-modal-overlay" data-testid="assign-training-modal">
          <div className="training-modal">
            <form onSubmit={handleAssignTraining}>
              <div className="training-modal-header">
                <h3>{t("portal.assignTrainingBtn") || "Assign Training"}</h3>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  data-testid="cancel-assign-training-btn"
                  onClick={() => setShowAssignModal(false)}
                >
                  ✕
                </button>
              </div>

              <div className="training-modal-body">
                {uncertainAssignPayload && (
                  <div className="training-uncertain-notice" data-testid="uncertain-assignment-notice">
                    <strong>Connection Interrupted</strong>
                    <span>
                      The assignment request timed out. Please check before retrying to prevent duplicate assignments.
                    </span>
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem", flexWrap: "wrap" }}>
                      {!assignReconcileDecision && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-primary"
                            data-testid="reconcile-assignment-btn"
                            onClick={() => void handleReconcileAssignment()}
                          >
                            Reconcile with Server
                          </button>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="dismiss-uncertain-assignment-btn"
                            onClick={handleAbandonAssignment}
                          >
                            Dismiss
                          </button>
                        </>
                      )}
                      {assignReconcileDecision === "absent" && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-primary"
                            data-testid="reconcile-resubmit-btn"
                            onClick={() => void handleResubmitAssignment()}
                          >
                            Resubmit Assignment
                          </button>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="reconcile-abandon-btn"
                            onClick={handleAbandonAssignment}
                          >
                            Abandon Draft
                          </button>
                        </>
                      )}
                      {(assignReconcileDecision === "adopt" || (assignReconcileDecision === "mismatch" && matchedServerAssignment !== null)) && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-primary"
                            data-testid="reconcile-adopt-btn"
                            onClick={() => handleAdoptAssignment()}
                          >
                            {assignReconcileDecision === "mismatch" ? "Adopt Server Assignment" : "Confirm & Adopt"}
                          </button>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="reconcile-abandon-btn"
                            onClick={handleAbandonAssignment}
                          >
                            Abandon Draft
                          </button>
                        </>
                      )}
                      {assignReconcileDecision === "mismatch" && matchedServerAssignment === null && (
                        <>
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            data-testid="reconcile-abandon-btn"
                            onClick={handleAbandonAssignment}
                          >
                            Abandon Draft
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {assignReconcileStatus && (
                  <div
                    data-testid="reconcile-assignment-status"
                    style={{
                      padding: "0.5rem",
                      borderRadius: "4px",
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                      backgroundColor: assignReconcileStatus.includes("verified") ? "#ecfdf5" : "#fffbeb",
                      color: assignReconcileStatus.includes("verified") ? "#065f46" : "#92400e",
                    }}
                  >
                    {assignReconcileStatus}
                  </div>
                )}

                {assignFormError && (
                  <div style={{ color: "#b91c1c", fontSize: "0.875rem", backgroundColor: "#fef2f2", padding: "0.5rem", borderRadius: "4px" }}>
                    {assignFormError}
                  </div>
                )}

                <div className="training-form-group">
                  <label htmlFor="assign-course-id">Select Course Reference *</label>
                  {courses.length > 0 ? (
                    <select
                      id="assign-course-id"
                      className="training-form-select"
                      data-testid="input-assignment-course-id"
                      required
                      value={assignForm.course_id}
                      onChange={(e) => setAssignForm({ ...assignForm, course_id: e.target.value })}
                    >
                      <option value="">-- Choose a registered course --</option>
                      {courses.map((c) => (
                        <option key={c.id} value={c.course_id}>
                          {c.title} ({c.course_id})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id="assign-course-id"
                      type="text"
                      className="training-form-input"
                      data-testid="input-assignment-course-id"
                      required
                      placeholder="e.g. sec-aware-2026"
                      value={assignForm.course_id}
                      onChange={(e) => setAssignForm({ ...assignForm, course_id: e.target.value })}
                    />
                  )}
                </div>

                <div className="training-form-group">
                  <label htmlFor="assign-email">Learner Workforce Email *</label>
                  <input
                    id="assign-email"
                    type="email"
                    className="training-form-input"
                    data-testid="input-assignment-email"
                    required
                    placeholder="colleague@company.com"
                    value={assignForm.workforce_email}
                    onChange={(e) => setAssignForm({ ...assignForm, workforce_email: e.target.value })}
                  />
                  <span className="training-form-help">Must match an active workforce member in this tenant.</span>
                </div>

                <div className="training-form-group">
                  <label htmlFor="assign-due-date">Due Date *</label>
                  <input
                    id="assign-due-date"
                    type="date"
                    className="training-form-input"
                    data-testid="input-assignment-due-date"
                    required
                    value={assignForm.due_date}
                    onChange={(e) => setAssignForm({ ...assignForm, due_date: e.target.value })}
                  />
                </div>
              </div>

              <div className="training-modal-footer">
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => setShowAssignModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="mw-btn mw-btn-primary"
                  data-testid="submit-assign-training-btn"
                  disabled={assignSubmitting || Boolean(uncertainAssignPayload)}
                >
                  {assignSubmitting ? "Assigning..." : "Assign Training"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
