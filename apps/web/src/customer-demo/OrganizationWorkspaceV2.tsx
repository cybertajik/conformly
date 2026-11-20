import type { TenantRole } from "@conformly/shared";
import React, { FC, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { canManageOrganization } from "../permissions";
import { ConflictError, CustomerDemoApiError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationError } from "./api";
import {
  createBusinessUnit,
  createLegalEntity,
  createLocation,
  fetchBusinessUnits,
  fetchEntitlements,
  fetchLegalEntities,
  fetchLocations,
  fetchMemberships,
} from "./organization-api";
import {
  BusinessUnit,
  LegalEntity,
  Location,
  Membership,
  SectionStatus,
  TenantEntitlement,
} from "./organization-types";
import "./modern-workspace.css";

export interface OrganizationWorkspaceProps {
  tenantId: string;
  token: string;
  userRole?: string;
  onSessionExpired?: () => void;
}

interface AmbiguousEntityPayload {
  name: string;
  registration_number: string | null;
  country: string;
  is_primary: boolean;
}

interface AmbiguousUnitPayload {
  legalEntityId: string;
  name: string;
  code: string | null;
}

interface AmbiguousLocationPayload {
  legalEntityId: string;
  name: string;
  country: string;
  city: string;
  address: string | null;
}

export interface AmbiguousMatch {
  id: string;
  name: string;
  summary: string;
  exactMatch: boolean;
}

export type AmbiguousPostState =
  | {
      type: "entity";
      payload: AmbiguousEntityPayload;
      reconciled?: boolean;
      matches?: AmbiguousMatch[];
    }
  | {
      type: "unit";
      payload: AmbiguousUnitPayload;
      reconciled?: boolean;
      matches?: AmbiguousMatch[];
    }
  | {
      type: "location";
      payload: AmbiguousLocationPayload;
      reconciled?: boolean;
      matches?: AmbiguousMatch[];
    };

function isUncertainTransportError(err: unknown): boolean {
  if (
    err instanceof UnauthorizedError ||
    err instanceof ForbiddenError ||
    err instanceof NotFoundError ||
    err instanceof ValidationError ||
    err instanceof ConflictError
  ) {
    return false;
  }
  if (err instanceof CustomerDemoApiError) {
    if (err.status >= 400 && err.status < 500) {
      return false;
    }
  }
  return true;
}

export const OrganizationWorkspaceV2: FC<OrganizationWorkspaceProps> = ({
  tenantId,
  token,
  userRole,
  onSessionExpired,
}) => {
  const { t } = useTranslation();
  const canManage = Boolean(userRole && canManageOrganization(userRole as TenantRole));

  // Primary data states
  const [legalEntities, setLegalEntities] = useState<LegalEntity[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState<boolean>(true);
  const [entitiesError, setEntitiesError] = useState<string | null>(null);

  const [selectedBuEntityId, setSelectedBuEntityId] = useState<string>("");
  const [businessUnits, setBusinessUnits] = useState<BusinessUnit[]>([]);
  const [unitsLoading, setUnitsLoading] = useState<boolean>(false);
  const [unitsError, setUnitsError] = useState<string | null>(null);

  const [selectedLocEntityId, setSelectedLocEntityId] = useState<string>("");
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationsLoading, setLocationsLoading] = useState<boolean>(false);
  const [locationsError, setLocationsError] = useState<string | null>(null);

  // Independent read-only sections
  const [membershipsStatus, setMembershipsStatus] = useState<SectionStatus<Membership[]>>({
    state: "loading",
    data: null,
  });

  const [entitlementsStatus, setEntitlementsStatus] = useState<SectionStatus<TenantEntitlement>>({
    state: "loading",
    data: null,
  });

  // Action / Feedback
  const [actionMessage, setActionMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [ambiguousPost, setAmbiguousPost] = useState<AmbiguousPostState | null>(null);
  const [isReconciling, setIsReconciling] = useState<boolean>(false);

  // Form states: Legal Entity
  const [entityName, setEntityName] = useState<string>("");
  const [entityReg, setEntityReg] = useState<string>("");
  const [entityCountry, setEntityCountry] = useState<string>("DE");
  const [entityPrimary, setEntityPrimary] = useState<boolean>(false);
  const [submittingEntity, setSubmittingEntity] = useState<boolean>(false);
  const [entityFormError, setEntityFormError] = useState<string | null>(null);

  // Form states: Business Unit
  const [buName, setBuName] = useState<string>("");
  const [buCode, setBuCode] = useState<string>("");
  const [submittingBu, setSubmittingBu] = useState<boolean>(false);
  const [buFormError, setBuFormError] = useState<string | null>(null);

  // Form states: Location
  const [locName, setLocName] = useState<string>("");
  const [locCountry, setLocCountry] = useState<string>("DE");
  const [locCity, setLocCity] = useState<string>("");
  const [locAddress, setLocAddress] = useState<string>("");
  const [submittingLoc, setSubmittingLoc] = useState<boolean>(false);
  const [locFormError, setLocFormError] = useState<string | null>(null);

  // Session & abort & generation refs
  const sessionGenRef = useRef<number>(0);
  const buGenRef = useRef<number>(0);
  const locGenRef = useRef<number>(0);
  const entityMutationGenRef = useRef<number>(0);
  const buMutationGenRef = useRef<number>(0);
  const locMutationGenRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const tenantIdRef = useRef(tenantId);
  useEffect(() => {
    tenantIdRef.current = tenantId;
  }, [tenantId]);

  const tokenRef = useRef(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const selectedBuEntityIdRef = useRef(selectedBuEntityId);
  useEffect(() => {
    selectedBuEntityIdRef.current = selectedBuEntityId;
  }, [selectedBuEntityId]);

  const selectedLocEntityIdRef = useRef(selectedLocEntityId);
  useEffect(() => {
    selectedLocEntityIdRef.current = selectedLocEntityId;
  }, [selectedLocEntityId]);

  const onSessionExpiredRef = useRef(onSessionExpired);
  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  }, [onSessionExpired]);

  const handleUnauthorized = useCallback(() => {
    sessionGenRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLegalEntities([]);
    setBusinessUnits([]);
    setLocations([]);
    setMembershipsStatus({ state: "denied", data: null, errorMessage: "Unauthorized" });
    setEntitlementsStatus({ state: "denied", data: null, errorMessage: "Unauthorized" });
    setActionMessage({ type: "error", text: "Session expired. Please sign in again." });
    onSessionExpiredRef.current?.();
  }, []);

  // Primary data loading effect on tenant/token changes
  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const ac = new AbortController();
    abortControllerRef.current = ac;
    const currentSessionGen = ++sessionGenRef.current;
    let isCancelled = false;

    if (!tenantId || !token) {
      return;
    }

    // 1. Legal Entities
    fetchLegalEntities(tenantId, token, ac.signal)
      .then((entities) => {
        if (!isCancelled && sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          setLegalEntities(entities);
          setEntitiesLoading(false);
          if (entities.length > 0) {
            const firstId = entities[0].id;
            setSelectedBuEntityId((prev) => prev || firstId);
            setSelectedLocEntityId((prev) => prev || firstId);
          }
        }
      })
      .catch((err) => {
        if (!isCancelled && sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          setEntitiesError(err instanceof Error ? err.message : "Failed to load legal entities");
          setEntitiesLoading(false);
        }
      });

    // 2. Memberships (independent read-only)
    fetchMemberships(tenantId, token, ac.signal)
      .then((members) => {
        if (!isCancelled && sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          setMembershipsStatus({ state: "loaded", data: members });
        }
      })
      .catch((err) => {
        if (!isCancelled && sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          if (err instanceof ForbiddenError) {
            setMembershipsStatus({ state: "denied", data: null, errorMessage: t("portal.membersDenied") });
          } else {
            setMembershipsStatus({ state: "error", data: null, errorMessage: err instanceof Error ? err.message : "Error" });
          }
        }
      });

    // 3. Entitlements (independent read-only)
    fetchEntitlements(tenantId, token, ac.signal)
      .then((entitlement) => {
        if (!isCancelled && sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          setEntitlementsStatus({ state: "loaded", data: entitlement });
        }
      })
      .catch((err) => {
        if (!isCancelled && sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          if (err instanceof ForbiddenError) {
            setEntitlementsStatus({ state: "denied", data: null, errorMessage: t("portal.entitlementsDenied") });
          } else {
            setEntitlementsStatus({ state: "error", data: null, errorMessage: err instanceof Error ? err.message : "Error" });
          }
        }
      });

    return () => {
      isCancelled = true;
      ac.abort();
    };
  }, [tenantId, token, handleUnauthorized, t]);

  // Load business units when selectedBuEntityId changes
  useEffect(() => {
    if (!selectedBuEntityId || !tenantId || !token) {
      return;
    }
    const currentBuGen = ++buGenRef.current;
    let isCancelled = false;

    fetchBusinessUnits(tenantId, token, selectedBuEntityId)
      .then((units) => {
        if (!isCancelled && buGenRef.current === currentBuGen && selectedBuEntityIdRef.current === selectedBuEntityId) {
          setBusinessUnits(units);
          setUnitsLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled && buGenRef.current === currentBuGen && selectedBuEntityIdRef.current === selectedBuEntityId) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          setUnitsError(err instanceof Error ? err.message : "Failed to load business units");
          setUnitsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedBuEntityId, tenantId, token, handleUnauthorized]);

  // Load locations when selectedLocEntityId changes
  useEffect(() => {
    if (!selectedLocEntityId || !tenantId || !token) {
      return;
    }
    const currentLocGen = ++locGenRef.current;
    let isCancelled = false;

    fetchLocations(tenantId, token, selectedLocEntityId)
      .then((locs) => {
        if (!isCancelled && locGenRef.current === currentLocGen && selectedLocEntityIdRef.current === selectedLocEntityId) {
          setLocations(locs);
          setLocationsLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled && locGenRef.current === currentLocGen && selectedLocEntityIdRef.current === selectedLocEntityId) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          setLocationsError(err instanceof Error ? err.message : "Failed to load locations");
          setLocationsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedLocEntityId, tenantId, token, handleUnauthorized]);

  // Refresh all sections and sublists cleanly
  const handleRefreshAll = useCallback(async () => {
    setEntitiesLoading(true);
    setEntitiesError(null);
    setUnitsLoading(true);
    setUnitsError(null);
    setLocationsLoading(true);
    setLocationsError(null);
    setMembershipsStatus({ state: "loading", data: null });
    setEntitlementsStatus({ state: "loading", data: null });
    setActionMessage(null);

    const ac = new AbortController();
    abortControllerRef.current = ac;
    const currentSessionGen = ++sessionGenRef.current;
    const currentBuGen = ++buGenRef.current;
    const currentLocGen = ++locGenRef.current;

    const pEntities = fetchLegalEntities(tenantId, token, ac.signal)
      .then((entities) => {
        if (sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          setLegalEntities(entities);
          setEntitiesLoading(false);
        }
      })
      .catch((err) => {
        if (sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          setEntitiesError(err instanceof Error ? err.message : "Failed to load legal entities");
          setEntitiesLoading(false);
        }
      });

    const pBu = selectedBuEntityIdRef.current
      ? fetchBusinessUnits(tenantId, token, selectedBuEntityIdRef.current)
          .then((units) => {
            if (buGenRef.current === currentBuGen) {
              setBusinessUnits(units);
              setUnitsLoading(false);
            }
          })
          .catch((err) => {
            if (buGenRef.current === currentBuGen) {
              setUnitsError(err instanceof Error ? err.message : "Failed to load business units");
              setUnitsLoading(false);
            }
          })
      : Promise.resolve();

    const pLoc = selectedLocEntityIdRef.current
      ? fetchLocations(tenantId, token, selectedLocEntityIdRef.current)
          .then((locs) => {
            if (locGenRef.current === currentLocGen) {
              setLocations(locs);
              setLocationsLoading(false);
            }
          })
          .catch((err) => {
            if (locGenRef.current === currentLocGen) {
              setLocationsError(err instanceof Error ? err.message : "Failed to load locations");
              setLocationsLoading(false);
            }
          })
      : Promise.resolve();

    const pMembers = fetchMemberships(tenantId, token, ac.signal)
      .then((members) => {
        if (sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          setMembershipsStatus({ state: "loaded", data: members });
        }
      })
      .catch((err) => {
        if (sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          if (err instanceof ForbiddenError) {
            setMembershipsStatus({ state: "denied", data: null, errorMessage: t("portal.membersDenied") });
          } else {
            setMembershipsStatus({ state: "error", data: null, errorMessage: err instanceof Error ? err.message : "Error" });
          }
        }
      });

    const pEntitlements = fetchEntitlements(tenantId, token, ac.signal)
      .then((entitlement) => {
        if (sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          setEntitlementsStatus({ state: "loaded", data: entitlement });
        }
      })
      .catch((err) => {
        if (sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return;
          }
          if (err instanceof ForbiddenError) {
            setEntitlementsStatus({ state: "denied", data: null, errorMessage: t("portal.entitlementsDenied") });
          } else {
            setEntitlementsStatus({ state: "error", data: null, errorMessage: err instanceof Error ? err.message : "Error" });
          }
        }
      });

    await Promise.allSettled([pEntities, pBu, pLoc, pMembers, pEntitlements]);
  }, [tenantId, token, handleUnauthorized, t]);

  // Reconciliation Handler for Ambiguous POST outcomes
  const handleReconcile = async () => {
    if (!ambiguousPost) return;
    setIsReconciling(true);
    setActionMessage(null);

    try {
      if (ambiguousPost.type === "entity") {
        const entities = await fetchLegalEntities(tenantId, token);
        setLegalEntities(entities);
        const p = ambiguousPost.payload;
        const matches: AmbiguousMatch[] = entities
          .filter((e) => e.name.trim().toLowerCase() === p.name.trim().toLowerCase())
          .map((e) => ({
            id: e.id,
            name: e.name,
            summary: `Reg: ${e.registration_number || "none"}, Country: ${e.country}, Primary: ${String(e.is_primary)}`,
            exactMatch:
              e.name.trim().toLowerCase() === p.name.trim().toLowerCase() &&
              (e.registration_number || null) === (p.registration_number || null) &&
              e.country.toUpperCase() === p.country.toUpperCase() &&
              Boolean(e.is_primary) === Boolean(p.is_primary),
          }));

        setAmbiguousPost({
          ...ambiguousPost,
          reconciled: true,
          matches,
        });
      } else if (ambiguousPost.type === "unit") {
        const p = ambiguousPost.payload;
        const units = await fetchBusinessUnits(tenantId, token, p.legalEntityId);
        if (selectedBuEntityIdRef.current === p.legalEntityId) {
          setBusinessUnits(units);
        }
        const matches: AmbiguousMatch[] = units
          .filter((u) => u.name.trim().toLowerCase() === p.name.trim().toLowerCase())
          .map((u) => ({
            id: u.id,
            name: u.name,
            summary: `Code: ${u.code || "none"}`,
            exactMatch:
              u.name.trim().toLowerCase() === p.name.trim().toLowerCase() &&
              (u.code || null) === (p.code || null),
          }));

        setAmbiguousPost({
          ...ambiguousPost,
          reconciled: true,
          matches,
        });
      } else if (ambiguousPost.type === "location") {
        const p = ambiguousPost.payload;
        const locs = await fetchLocations(tenantId, token, p.legalEntityId);
        if (selectedLocEntityIdRef.current === p.legalEntityId) {
          setLocations(locs);
        }
        const matches: AmbiguousMatch[] = locs
          .filter((l) => l.name.trim().toLowerCase() === p.name.trim().toLowerCase())
          .map((l) => ({
            id: l.id,
            name: l.name,
            summary: `City: ${l.city}, Country: ${l.country}, Address: ${l.address || "none"}`,
            exactMatch:
              l.name.trim().toLowerCase() === p.name.trim().toLowerCase() &&
              l.city.trim().toLowerCase() === p.city.trim().toLowerCase() &&
              l.country.toUpperCase() === p.country.toUpperCase() &&
              (l.address || null) === (p.address || null),
          }));

        setAmbiguousPost({
          ...ambiguousPost,
          reconciled: true,
          matches,
        });
      }
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      setActionMessage({ type: "error", text: err instanceof Error ? err.message : "Reconciliation query failed" });
    } finally {
      setIsReconciling(false);
    }
  };

  const handleConfirmReconciled = (match: AmbiguousMatch) => {
    if (!ambiguousPost) return;
    if (ambiguousPost.type === "entity") {
      setEntityName("");
      setEntityReg("");
      setEntityCountry("DE");
      setEntityPrimary(false);
      setEntityFormError(null);
    } else if (ambiguousPost.type === "unit") {
      setBuName("");
      setBuCode("");
      setBuFormError(null);
    } else if (ambiguousPost.type === "location") {
      setLocName("");
      setLocCity("");
      setLocAddress("");
      setLocCountry("DE");
      setLocFormError(null);
    }
    setAmbiguousPost(null);
    setActionMessage({ type: "success", text: `${t("portal.reconciledSuccess")} (${match.name})` });
  };

  const handleDismissAmbiguous = () => {
    setAmbiguousPost(null);
    setEntityFormError(null);
    setBuFormError(null);
    setLocFormError(null);
  };

  // Create Legal Entity Handler (Fenced by tenant, token, entity mutation generation)
  const handleCreateEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage) return;

    if (!entityName.trim()) {
      setEntityFormError(t("portal.entityNameRequired"));
      return;
    }
    if (entityCountry.trim().length !== 2) {
      setEntityFormError(t("portal.countryTwoLetters"));
      return;
    }

    const targetTenantId = tenantId;
    const targetToken = token;
    const mutationGen = ++entityMutationGenRef.current;

    setSubmittingEntity(true);
    setEntityFormError(null);
    setActionMessage(null);

    const payload: AmbiguousEntityPayload = {
      name: entityName,
      registration_number: entityReg || null,
      country: entityCountry,
      is_primary: entityPrimary,
    };

    try {
      const created = await createLegalEntity(targetTenantId, targetToken, payload);

      if (
        tenantIdRef.current !== targetTenantId ||
        tokenRef.current !== targetToken ||
        entityMutationGenRef.current !== mutationGen
      ) {
        return;
      }

      setLegalEntities((prev) => [...prev, created]);
      if (!selectedBuEntityId) setSelectedBuEntityId(created.id);
      if (!selectedLocEntityId) setSelectedLocEntityId(created.id);

      setEntityName("");
      setEntityReg("");
      setEntityCountry("DE");
      setEntityPrimary(false);
      setActionMessage({ type: "success", text: `${t("portal.entityCreatedSuccess")} (${created.name})` });
    } catch (err: unknown) {
      if (
        tenantIdRef.current !== targetTenantId ||
        tokenRef.current !== targetToken ||
        entityMutationGenRef.current !== mutationGen
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      if (isUncertainTransportError(err)) {
        setAmbiguousPost({ type: "entity", payload });
        setEntityFormError(t("portal.postAmbiguousNotice"));
      } else {
        setEntityFormError(err instanceof Error ? err.message : "Failed to create entity");
      }
    } finally {
      if (entityMutationGenRef.current === mutationGen) {
        setSubmittingEntity(false);
      }
    }
  };

  // Create Business Unit Handler (Fenced by entity selection, tenant, token, bu mutation generation)
  const handleCreateBusinessUnit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage) return;

    if (!selectedBuEntityId) {
      setBuFormError(t("portal.selectEntityRequired"));
      return;
    }
    if (!buName.trim()) {
      setBuFormError(t("portal.unitNameRequired"));
      return;
    }

    const targetEntityId = selectedBuEntityId;
    const targetTenantId = tenantId;
    const targetToken = token;
    const mutationGen = ++buMutationGenRef.current;

    setSubmittingBu(true);
    setBuFormError(null);
    setActionMessage(null);

    const payload: AmbiguousUnitPayload = {
      legalEntityId: targetEntityId,
      name: buName,
      code: buCode || null,
    };

    try {
      const created = await createBusinessUnit(targetTenantId, targetToken, {
        legal_entity_id: targetEntityId,
        name: buName,
        code: buCode || null,
      });

      if (
        selectedBuEntityIdRef.current !== targetEntityId ||
        tenantIdRef.current !== targetTenantId ||
        tokenRef.current !== targetToken ||
        buMutationGenRef.current !== mutationGen
      ) {
        return;
      }

      setBusinessUnits((prev) => [...prev, created]);
      setBuName("");
      setBuCode("");
      setActionMessage({ type: "success", text: `${t("portal.unitCreatedSuccess")} (${created.name})` });
    } catch (err: unknown) {
      if (
        selectedBuEntityIdRef.current !== targetEntityId ||
        tenantIdRef.current !== targetTenantId ||
        tokenRef.current !== targetToken ||
        buMutationGenRef.current !== mutationGen
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      if (isUncertainTransportError(err)) {
        setAmbiguousPost({ type: "unit", payload });
        setBuFormError(t("portal.postAmbiguousNotice"));
      } else {
        setBuFormError(err instanceof Error ? err.message : "Failed to create business unit");
      }
    } finally {
      if (buMutationGenRef.current === mutationGen) {
        setSubmittingBu(false);
      }
    }
  };

  // Create Location Handler (Fenced by entity selection, tenant, token, location mutation generation)
  const handleCreateLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage) return;

    if (!selectedLocEntityId) {
      setLocFormError(t("portal.selectEntityRequired"));
      return;
    }
    if (!locName.trim()) {
      setLocFormError(t("portal.locationNameRequired"));
      return;
    }
    if (!locCity.trim()) {
      setLocFormError(t("portal.cityRequired"));
      return;
    }
    if (locCountry.trim().length !== 2) {
      setLocFormError(t("portal.countryTwoLetters"));
      return;
    }

    const targetEntityId = selectedLocEntityId;
    const targetTenantId = tenantId;
    const targetToken = token;
    const mutationGen = ++locMutationGenRef.current;

    setSubmittingLoc(true);
    setLocFormError(null);
    setActionMessage(null);

    const payload: AmbiguousLocationPayload = {
      legalEntityId: targetEntityId,
      name: locName,
      country: locCountry,
      city: locCity,
      address: locAddress || null,
    };

    try {
      const created = await createLocation(targetTenantId, targetToken, {
        legal_entity_id: targetEntityId,
        name: locName,
        country: locCountry,
        city: locCity,
        address: locAddress || null,
      });

      if (
        selectedLocEntityIdRef.current !== targetEntityId ||
        tenantIdRef.current !== targetTenantId ||
        tokenRef.current !== targetToken ||
        locMutationGenRef.current !== mutationGen
      ) {
        return;
      }

      setLocations((prev) => [...prev, created]);
      setLocName("");
      setLocCity("");
      setLocAddress("");
      setLocCountry("DE");
      setActionMessage({ type: "success", text: `${t("portal.locationCreatedSuccess")} (${created.name})` });
    } catch (err: unknown) {
      if (
        selectedLocEntityIdRef.current !== targetEntityId ||
        tenantIdRef.current !== targetTenantId ||
        tokenRef.current !== targetToken ||
        locMutationGenRef.current !== mutationGen
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      if (isUncertainTransportError(err)) {
        setAmbiguousPost({ type: "location", payload });
        setLocFormError(t("portal.postAmbiguousNotice"));
      } else {
        setLocFormError(err instanceof Error ? err.message : "Failed to create location");
      }
    } finally {
      if (locMutationGenRef.current === mutationGen) {
        setSubmittingLoc(false);
      }
    }
  };

  return (
    <div className="mw-workspace-root" data-testid="organization-workspace" data-user-role={userRole}>
      {/* Header */}
      <header className="mw-section-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1 className="mw-section-title" data-testid="org-workspace-title">
            {t("portal.orgTitle")}
          </h1>
          <p className="mw-section-subtitle">
            {t("portal.orgSubtitle")}
          </p>
        </div>
        <button
          type="button"
          className="mw-btn mw-btn-secondary"
          onClick={() => void handleRefreshAll()}
          data-testid="org-refresh-btn"
          disabled={entitiesLoading}
        >
          {entitiesLoading ? t("portal.refreshingOrgBtn") : t("portal.refreshOrgBtn")}
        </button>
      </header>

      {/* Action / Notification Banner */}
      {actionMessage && (
        <div
          role="status"
          className="mw-notice-banner"
          style={{
            borderColor: actionMessage.type === "success" ? "#28a745" : "#dc3545",
            background: actionMessage.type === "success" ? "#f8fff9" : "#fff8f8",
            color: actionMessage.type === "success" ? "#155724" : "#721c24",
            marginBottom: "1.25rem",
          }}
        >
          {actionMessage.text}
        </div>
      )}

      {/* Ambiguous POST Reconciliation Banner */}
      {ambiguousPost && (
        <div
          role="alert"
          data-testid="ambiguous-post-banner"
          className="mw-notice-banner"
          style={{
            borderColor: "#ff9500",
            background: "#fffdf5",
            color: "#856404",
            marginBottom: "1.25rem",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>
            {t("portal.postAmbiguousNotice")}
          </div>
          <div style={{ fontSize: "0.85rem", marginBottom: "0.4rem" }}>
            Record Name: <strong>{ambiguousPost.payload.name}</strong>
          </div>

          {/* Preserved Full Attempted Details */}
          <div style={{ fontSize: "0.8rem", color: "#666", marginBottom: "0.75rem", background: "rgba(0,0,0,0.03)", padding: "0.4rem 0.6rem", borderRadius: "4px" }}>
            Attempted details:{" "}
            {ambiguousPost.type === "entity" && (
              <span>Reg: {ambiguousPost.payload.registration_number || "none"}, Country: {ambiguousPost.payload.country}, Primary: {String(ambiguousPost.payload.is_primary)}</span>
            )}
            {ambiguousPost.type === "unit" && (
              <span>Code: {ambiguousPost.payload.code || "none"}</span>
            )}
            {ambiguousPost.type === "location" && (
              <span>City: {ambiguousPost.payload.city}, Country: {ambiguousPost.payload.country}, Address: {ambiguousPost.payload.address || "none"}</span>
            )}
          </div>

          {/* Results after scoped GET reconciliation query */}
          {ambiguousPost.reconciled && (
            <div data-testid="reconciliation-results" style={{ marginBottom: "0.75rem" }}>
              {(!ambiguousPost.matches || ambiguousPost.matches.length === 0) ? (
                <div style={{ fontSize: "0.85rem", color: "#666", fontStyle: "italic" }}>
                  {t("portal.reconcileNotFound")} (Note: write may still be pending or delayed)
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  {ambiguousPost.matches.map((m) => (
                    <div
                      key={m.id}
                      data-testid={`match-row-${m.id}`}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "0.4rem 0.6rem",
                        border: m.exactMatch ? "1px solid #28a745" : "1px dashed #ff9500",
                        borderRadius: "4px",
                        background: m.exactMatch ? "#f8fff9" : "#fffbf0",
                      }}
                    >
                      <div style={{ fontSize: "0.85rem" }}>
                        <strong>{m.name}</strong> ({m.summary})
                        {!m.exactMatch && <span style={{ color: "#d9534f", marginLeft: "0.4rem", fontSize: "0.75rem" }}>(Differs from attempted payload)</span>}
                      </div>
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid={`confirm-match-btn-${m.id}`}
                        onClick={() => handleConfirmReconciled(m)}
                        style={{ fontSize: "0.8rem", padding: "0.2rem 0.5rem" }}
                      >
                        Confirm Match
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="reconcile-post-btn"
              onClick={() => void handleReconcile()}
              disabled={isReconciling}
              style={{ fontSize: "0.85rem", padding: "0.35rem 0.75rem" }}
            >
              {isReconciling ? "Checking Server..." : t("portal.checkReconcileBtn")}
            </button>
            {ambiguousPost.reconciled && (
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="dismiss-ambiguous-btn"
                onClick={handleDismissAmbiguous}
                disabled={isReconciling}
                style={{ fontSize: "0.85rem", padding: "0.35rem 0.75rem" }}
              >
                {t("portal.dismissRetryBtn")}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Grid of Sections */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* SECTION 1: Legal Entities */}
        <section className="mw-card" data-testid="legal-entities-section" aria-labelledby="legal-entities-heading">
          <div className="mw-card-header">
            <h2 id="legal-entities-heading" className="mw-card-title">
              {t("portal.legalEntitiesTitle")}
            </h2>
            <p className="mw-card-subtitle">
              {t("portal.legalEntitiesSubtitle")}
            </p>
          </div>
          <div className="mw-card-body">
            {entitiesError && (
              <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24", marginBottom: "1rem" }}>
                {entitiesError}
              </div>
            )}

            {entitiesLoading ? (
              <div role="status" className="mw-loading-indicator">
                {t("portal.loadingEntities")}
              </div>
            ) : legalEntities.length === 0 ? (
              <p style={{ color: "#666", fontSize: "0.9rem" }}>{t("portal.noEntitiesYet")}</p>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0.75rem", marginBottom: "1.5rem" }}>
                {legalEntities.map((ent) => (
                  <div
                    key={ent.id}
                    data-testid={`entity-card-${ent.id}`}
                    style={{
                      padding: "0.75rem",
                      borderRadius: "6px",
                      border: "1px solid var(--mw-border-color)",
                      background: "rgba(0, 0, 0, 0.02)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong>{ent.name}</strong>
                      {ent.is_primary && (
                        <span
                          data-testid={`primary-badge-${ent.id}`}
                          style={{
                            fontSize: "0.7rem",
                            padding: "0.15rem 0.4rem",
                            borderRadius: "4px",
                            background: "#0066cc",
                            color: "#fff",
                            fontWeight: 700,
                          }}
                        >
                          {t("portal.primaryBadge")}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "#666", marginTop: "0.25rem" }}>
                      Country: <strong>{ent.country}</strong> {ent.registration_number ? `| Reg: ${ent.registration_number}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Read-Only Role Notice or Create Legal Entity Form */}
            {!canManage ? (
              <div role="status" className="mw-notice-banner" style={{ background: "rgba(0,0,0,0.03)", borderColor: "var(--mw-border-color)", marginTop: "1rem" }}>
                {t("portal.orgManageReadOnlyNotice")}
              </div>
            ) : (
              <form onSubmit={handleCreateEntity} style={{ marginTop: "1rem", borderTop: "1px solid var(--mw-border-color)", paddingTop: "1rem" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.75rem" }}>
                  {t("portal.addEntityHeading")}
                </h3>
                {entityFormError && (
                  <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24", marginBottom: "0.75rem", fontSize: "0.85rem" }}>
                    {entityFormError}
                  </div>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem", marginBottom: "0.75rem" }}>
                  <div>
                    <label htmlFor="entity-name-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.entityNameLabel")} *
                    </label>
                    <input
                      id="entity-name-input"
                      data-testid="entity-name-input"
                      type="text"
                      className="mw-input"
                      value={entityName}
                      onChange={(e) => setEntityName(e.target.value)}
                      placeholder="Acme GmbH"
                      disabled={submittingEntity || Boolean(ambiguousPost)}
                    />
                  </div>
                  <div>
                    <label htmlFor="entity-reg-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.regNumberLabel")}
                    </label>
                    <input
                      id="entity-reg-input"
                      data-testid="entity-reg-input"
                      type="text"
                      className="mw-input"
                      value={entityReg}
                      onChange={(e) => setEntityReg(e.target.value)}
                      placeholder="HRB 123456"
                      disabled={submittingEntity || Boolean(ambiguousPost)}
                    />
                  </div>
                  <div>
                    <label htmlFor="entity-country-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.countryLabel")}
                    </label>
                    <input
                      id="entity-country-input"
                      data-testid="entity-country-input"
                      type="text"
                      maxLength={2}
                      className="mw-input"
                      value={entityCountry}
                      onChange={(e) => setEntityCountry(e.target.value.toUpperCase())}
                      disabled={submittingEntity || Boolean(ambiguousPost)}
                    />
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <input
                    id="entity-primary-checkbox"
                    data-testid="entity-primary-checkbox"
                    type="checkbox"
                    checked={entityPrimary}
                    onChange={(e) => setEntityPrimary(e.target.checked)}
                    disabled={submittingEntity || Boolean(ambiguousPost)}
                  />
                  <label htmlFor="entity-primary-checkbox" style={{ fontSize: "0.85rem" }}>
                    {t("portal.primaryEntityLabel")}
                  </label>
                </div>
                <button
                  type="submit"
                  className="mw-btn mw-btn-primary"
                  data-testid="create-entity-btn"
                  disabled={submittingEntity || Boolean(ambiguousPost)}
                >
                  {submittingEntity ? t("portal.creatingEntityBtn") : t("portal.createEntityBtn")}
                </button>
              </form>
            )}
          </div>
        </section>

        {/* SECTION 2: Business Units */}
        <section className="mw-card" data-testid="business-units-section" aria-labelledby="bu-heading">
          <div className="mw-card-header">
            <h2 id="bu-heading" className="mw-card-title">{t("portal.businessUnitsTitle")}</h2>
            <p className="mw-card-subtitle">{t("portal.businessUnitsSubtitle")}</p>
          </div>
          <div className="mw-card-body">
            {/* Entity selector for Business Units */}
            <div style={{ marginBottom: "1rem" }}>
              <label htmlFor="bu-entity-select" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                {t("portal.selectLegalEntityLabel")}
              </label>
              <select
                id="bu-entity-select"
                data-testid="bu-entity-select"
                className="mw-select"
                value={selectedBuEntityId}
                onChange={(e) => setSelectedBuEntityId(e.target.value)}
                disabled={legalEntities.length === 0 || submittingBu}
                style={{ width: "100%", maxWidth: "400px" }}
              >
                {legalEntities.length === 0 ? (
                  <option value="">{t("portal.selectEntityPrompt")}</option>
                ) : (
                  legalEntities.map((ent) => (
                    <option key={ent.id} value={ent.id}>
                      {ent.name} ({ent.country})
                    </option>
                  ))
                )}
              </select>
            </div>

            {unitsError && (
              <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24", marginBottom: "1rem" }}>
                {unitsError}
              </div>
            )}

            {unitsLoading ? (
              <div role="status" className="mw-loading-indicator">{t("portal.loadingUnits")}</div>
            ) : businessUnits.length === 0 ? (
              <p style={{ color: "#666", fontSize: "0.9rem" }}>{t("portal.noUnitsYet")}</p>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem", marginBottom: "1.5rem" }}>
                {businessUnits.map((bu) => (
                  <div
                    key={bu.id}
                    data-testid={`bu-card-${bu.id}`}
                    style={{
                      padding: "0.75rem",
                      borderRadius: "6px",
                      border: "1px solid var(--mw-border-color)",
                      background: "rgba(0, 0, 0, 0.02)",
                    }}
                  >
                    <strong>{bu.name}</strong>
                    {bu.code && (
                      <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", padding: "0.1rem 0.35rem", borderRadius: "4px", background: "rgba(0,0,0,0.06)" }}>
                        {bu.code}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Read-Only Role Notice or Create Business Unit Form */}
            {!canManage ? (
              <div role="status" className="mw-notice-banner" style={{ background: "rgba(0,0,0,0.03)", borderColor: "var(--mw-border-color)", marginTop: "1rem" }}>
                {t("portal.orgManageReadOnlyNotice")}
              </div>
            ) : (
              <form onSubmit={handleCreateBusinessUnit} style={{ marginTop: "1rem", borderTop: "1px solid var(--mw-border-color)", paddingTop: "1rem" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.75rem" }}>
                  {t("portal.addUnitHeading")}
                </h3>
                {buFormError && (
                  <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24", marginBottom: "0.75rem", fontSize: "0.85rem" }}>
                    {buFormError}
                  </div>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem", marginBottom: "0.75rem" }}>
                  <div>
                    <label htmlFor="bu-name-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.unitNameLabel")} *
                    </label>
                    <input
                      id="bu-name-input"
                      data-testid="bu-name-input"
                      type="text"
                      className="mw-input"
                      value={buName}
                      onChange={(e) => setBuName(e.target.value)}
                      placeholder="Security Operations"
                      disabled={submittingBu || legalEntities.length === 0 || Boolean(ambiguousPost)}
                    />
                  </div>
                  <div>
                    <label htmlFor="bu-code-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.unitCodeLabel")}
                    </label>
                    <input
                      id="bu-code-input"
                      data-testid="bu-code-input"
                      type="text"
                      className="mw-input"
                      value={buCode}
                      onChange={(e) => setBuCode(e.target.value)}
                      placeholder="SEC-OPS"
                      disabled={submittingBu || legalEntities.length === 0 || Boolean(ambiguousPost)}
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  className="mw-btn mw-btn-primary"
                  data-testid="create-bu-btn"
                  disabled={submittingBu || legalEntities.length === 0 || Boolean(ambiguousPost)}
                >
                  {submittingBu ? t("portal.creatingUnitBtn") : t("portal.createUnitBtn")}
                </button>
              </form>
            )}
          </div>
        </section>

        {/* SECTION 3: Locations */}
        <section className="mw-card" data-testid="locations-section" aria-labelledby="locations-heading">
          <div className="mw-card-header">
            <h2 id="locations-heading" className="mw-card-title">{t("portal.locationsTitle")}</h2>
            <p className="mw-card-subtitle">{t("portal.locationsSubtitle")}</p>
          </div>
          <div className="mw-card-body">
            {/* Entity selector for Locations */}
            <div style={{ marginBottom: "1rem" }}>
              <label htmlFor="loc-entity-select" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                {t("portal.selectLegalEntityLabel")}
              </label>
              <select
                id="loc-entity-select"
                data-testid="loc-entity-select"
                className="mw-select"
                value={selectedLocEntityId}
                onChange={(e) => setSelectedLocEntityId(e.target.value)}
                disabled={legalEntities.length === 0 || submittingLoc}
                style={{ width: "100%", maxWidth: "400px" }}
              >
                {legalEntities.length === 0 ? (
                  <option value="">{t("portal.selectEntityPrompt")}</option>
                ) : (
                  legalEntities.map((ent) => (
                    <option key={ent.id} value={ent.id}>
                      {ent.name} ({ent.country})
                    </option>
                  ))
                )}
              </select>
            </div>

            {locationsError && (
              <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24", marginBottom: "1rem" }}>
                {locationsError}
              </div>
            )}

            {locationsLoading ? (
              <div role="status" className="mw-loading-indicator">{t("portal.loadingLocations")}</div>
            ) : locations.length === 0 ? (
              <p style={{ color: "#666", fontSize: "0.9rem" }}>{t("portal.noLocationsYet")}</p>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem", marginBottom: "1.5rem" }}>
                {locations.map((loc) => (
                  <div
                    key={loc.id}
                    data-testid={`loc-card-${loc.id}`}
                    style={{
                      padding: "0.75rem",
                      borderRadius: "6px",
                      border: "1px solid var(--mw-border-color)",
                      background: "rgba(0, 0, 0, 0.02)",
                    }}
                  >
                    <strong>{loc.name}</strong>
                    <div style={{ fontSize: "0.8rem", color: "#666", marginTop: "0.25rem" }}>
                      {loc.city}, {loc.country} {loc.address ? `• ${loc.address}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Read-Only Role Notice or Create Location Form */}
            {!canManage ? (
              <div role="status" className="mw-notice-banner" style={{ background: "rgba(0,0,0,0.03)", borderColor: "var(--mw-border-color)", marginTop: "1rem" }}>
                {t("portal.orgManageReadOnlyNotice")}
              </div>
            ) : (
              <form onSubmit={handleCreateLocation} style={{ marginTop: "1rem", borderTop: "1px solid var(--mw-border-color)", paddingTop: "1rem" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.75rem" }}>
                  {t("portal.addLocationHeading")}
                </h3>
                {locFormError && (
                  <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24", marginBottom: "0.75rem", fontSize: "0.85rem" }}>
                    {locFormError}
                  </div>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem", marginBottom: "0.75rem" }}>
                  <div>
                    <label htmlFor="loc-name-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.locationNameLabel")} *
                    </label>
                    <input
                      id="loc-name-input"
                      data-testid="loc-name-input"
                      type="text"
                      className="mw-input"
                      value={locName}
                      onChange={(e) => setLocName(e.target.value)}
                      placeholder="Berlin DC 1"
                      disabled={submittingLoc || legalEntities.length === 0 || Boolean(ambiguousPost)}
                    />
                  </div>
                  <div>
                    <label htmlFor="loc-city-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.cityLabel")} *
                    </label>
                    <input
                      id="loc-city-input"
                      data-testid="loc-city-input"
                      type="text"
                      className="mw-input"
                      value={locCity}
                      onChange={(e) => setLocCity(e.target.value)}
                      placeholder="Berlin"
                      disabled={submittingLoc || legalEntities.length === 0 || Boolean(ambiguousPost)}
                    />
                  </div>
                  <div>
                    <label htmlFor="loc-country-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.countryLabel")}
                    </label>
                    <input
                      id="loc-country-input"
                      data-testid="loc-country-input"
                      type="text"
                      maxLength={2}
                      className="mw-input"
                      value={locCountry}
                      onChange={(e) => setLocCountry(e.target.value.toUpperCase())}
                      disabled={submittingLoc || legalEntities.length === 0 || Boolean(ambiguousPost)}
                    />
                  </div>
                  <div>
                    <label htmlFor="loc-address-input" style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      {t("portal.addressLabel")}
                    </label>
                    <input
                      id="loc-address-input"
                      data-testid="loc-address-input"
                      type="text"
                      className="mw-input"
                      value={locAddress}
                      onChange={(e) => setLocAddress(e.target.value)}
                      placeholder="Main Street 1"
                      disabled={submittingLoc || legalEntities.length === 0 || Boolean(ambiguousPost)}
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  className="mw-btn mw-btn-primary"
                  data-testid="create-loc-btn"
                  disabled={submittingLoc || legalEntities.length === 0 || Boolean(ambiguousPost)}
                >
                  {submittingLoc ? t("portal.creatingLocationBtn") : t("portal.createLocationBtn")}
                </button>
              </form>
            )}
          </div>
        </section>

        {/* SECTION 4: Members Directory (Independent Read-Only) */}
        <section className="mw-card" data-testid="memberships-section" aria-labelledby="members-heading">
          <div className="mw-card-header">
            <h2 id="members-heading" className="mw-card-title">{t("portal.membersTitle")}</h2>
            <p className="mw-card-subtitle">{t("portal.membersSubtitle")}</p>
          </div>
          <div className="mw-card-body">
            {membershipsStatus.state === "loading" && (
              <div role="status" className="mw-loading-indicator">Loading members...</div>
            )}
            {membershipsStatus.state === "denied" && (
              <div role="alert" data-testid="memberships-denied" className="mw-notice-banner" style={{ borderColor: "#ff9500", background: "rgba(255, 149, 0, 0.08)", color: "#b36b00" }}>
                <strong>Access Restricted (403): </strong>
                {membershipsStatus.errorMessage || t("portal.membersDenied")}
              </div>
            )}
            {membershipsStatus.state === "error" && (
              <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24" }}>
                {membershipsStatus.errorMessage}
              </div>
            )}
            {membershipsStatus.state === "loaded" && (
              (!membershipsStatus.data || membershipsStatus.data.length === 0) ? (
                <p style={{ color: "#666", fontSize: "0.9rem" }}>{t("portal.noMembersYet")}</p>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table data-testid="memberships-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--mw-border-color)", textAlign: "left" }}>
                        <th style={{ padding: "0.5rem" }}>Name</th>
                        <th style={{ padding: "0.5rem" }}>Email</th>
                        <th style={{ padding: "0.5rem" }}>Role</th>
                        <th style={{ padding: "0.5rem" }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {membershipsStatus.data.map((mem) => (
                        <tr key={mem.id} data-testid={`membership-row-${mem.id}`} style={{ borderBottom: "1px solid rgba(0,0,0,0.05)" }}>
                          <td style={{ padding: "0.5rem" }}><strong>{mem.display_name}</strong></td>
                          <td style={{ padding: "0.5rem", color: "#666" }}>({mem.email})</td>
                          <td style={{ padding: "0.5rem" }}>
                            <span style={{ padding: "0.15rem 0.4rem", borderRadius: "4px", background: "rgba(0,0,0,0.06)", fontWeight: 600, fontSize: "0.75rem" }}>
                              {mem.role}
                            </span>
                          </td>
                          <td style={{ padding: "0.5rem" }}>
                            <span style={{ color: mem.status === "ACTIVE" ? "#28a745" : "#666", fontWeight: 600 }}>
                              {mem.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}
          </div>
        </section>

        {/* SECTION 5: Plan Entitlements (Independent Read-Only) */}
        <section className="mw-card" data-testid="entitlements-section" aria-labelledby="entitlements-heading">
          <div className="mw-card-header">
            <h2 id="entitlements-heading" className="mw-card-title">{t("portal.entitlementsTitle")}</h2>
            <p className="mw-card-subtitle">{t("portal.entitlementsSubtitle")}</p>
          </div>
          <div className="mw-card-body">
            {entitlementsStatus.state === "loading" && (
              <div role="status" className="mw-loading-indicator">Loading plan entitlements...</div>
            )}
            {entitlementsStatus.state === "denied" && (
              <div role="alert" data-testid="entitlements-denied" className="mw-notice-banner" style={{ borderColor: "#ff9500", background: "rgba(255, 149, 0, 0.08)", color: "#b36b00" }}>
                <strong>Access Restricted (403): </strong>
                {entitlementsStatus.errorMessage || t("portal.entitlementsDenied")}
              </div>
            )}
            {entitlementsStatus.state === "error" && (
              <div role="alert" className="mw-notice-banner" style={{ borderColor: "#dc3545", color: "#721c24" }}>
                {entitlementsStatus.errorMessage}
              </div>
            )}
            {entitlementsStatus.state === "loaded" && entitlementsStatus.data && (
              <div data-testid="entitlements-card" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
                <div style={{ padding: "0.75rem", borderRadius: "6px", background: "rgba(0,0,0,0.02)", border: "1px solid var(--mw-border-color)" }}>
                  <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "#666", fontWeight: 700 }}>
                    {t("portal.planLabel")}
                  </div>
                  <div data-testid="entitlement-plan-code" style={{ fontSize: "1.1rem", fontWeight: 700, marginTop: "0.25rem", color: "var(--mw-primary)" }}>
                    {entitlementsStatus.data.plan_code}
                  </div>
                </div>
                <div style={{ padding: "0.75rem", borderRadius: "6px", background: "rgba(0,0,0,0.02)", border: "1px solid var(--mw-border-color)" }}>
                  <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "#666", fontWeight: 700 }}>
                    {t("portal.maxMembersLabel")}
                  </div>
                  <div data-testid="entitlement-max-members" style={{ fontSize: "1.1rem", fontWeight: 700, marginTop: "0.25rem" }}>
                    {entitlementsStatus.data.max_members}
                  </div>
                </div>
                <div style={{ padding: "0.75rem", borderRadius: "6px", background: "rgba(0,0,0,0.02)", border: "1px solid var(--mw-border-color)" }}>
                  <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "#666", fontWeight: 700 }}>
                    {t("portal.storageLimitLabel")}
                  </div>
                  <div data-testid="entitlement-storage-limit" style={{ fontSize: "1.1rem", fontWeight: 700, marginTop: "0.25rem" }}>
                    {Math.round(entitlementsStatus.data.max_storage_bytes / (1024 * 1024))} MB
                  </div>
                </div>
                <div style={{ gridColumn: "1 / -1", padding: "0.75rem", borderRadius: "6px", background: "rgba(0,0,0,0.02)", border: "1px solid var(--mw-border-color)" }}>
                  <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "#666", fontWeight: 700, marginBottom: "0.4rem" }}>
                    {t("portal.modulesLabel")}
                  </div>
                  <div data-testid="entitlement-modules" style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                    {entitlementsStatus.data.enabled_modules.map((mod) => (
                      <span key={mod} style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", borderRadius: "4px", background: "rgba(0,102,204,0.08)", color: "#0066cc", fontWeight: 600 }}>
                        {mod}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};
