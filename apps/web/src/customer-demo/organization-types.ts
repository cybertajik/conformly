/**
 * Type definitions for Organization Workspace V2, Memberships, and Entitlements.
 * Maps strictly to existing backend API schemas.
 */

export interface LegalEntity {
  id: string;
  tenant_id: string;
  name: string;
  registration_number: string | null;
  country: string;
  is_primary: boolean;
  created_at?: string;
}

export interface LegalEntityCreateInput {
  name: string;
  registration_number?: string | null;
  country?: string;
  is_primary?: boolean;
}

export interface BusinessUnit {
  id: string;
  tenant_id: string;
  legal_entity_id: string;
  name: string;
  code: string | null;
  created_at?: string;
}

export interface BusinessUnitCreateInput {
  legal_entity_id: string;
  name: string;
  code?: string | null;
}

export interface Location {
  id: string;
  tenant_id: string;
  legal_entity_id: string;
  name: string;
  country: string;
  city: string;
  address: string | null;
  created_at?: string;
}

export interface LocationCreateInput {
  legal_entity_id: string;
  name: string;
  country?: string;
  city: string;
  address?: string | null;
}

export interface Membership {
  id: string;
  tenant_id?: string;
  user_id: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  created_at?: string;
}

export interface TenantEntitlement {
  id: string;
  tenant_id: string;
  plan_code: string;
  enabled_modules: string[];
  max_members: number;
  max_storage_bytes: number;
  allowed_framework_slugs: string[];
  effective_from: string;
  effective_until: string | null;
}

export type SectionFetchState = "idle" | "loading" | "loaded" | "denied" | "unavailable" | "error";

export interface SectionStatus<T> {
  state: SectionFetchState;
  data: T | null;
  errorMessage?: string;
}
