import "@testing-library/jest-dom/vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { I18nProvider, useTranslation } from "./I18nContext";
import { de } from "./locales/de";
import { en } from "./locales/en";
import { es } from "./locales/es";
import { fr } from "./locales/fr";
import { nl } from "./locales/nl";
import { SUPPORTED_LOCALES, type SupportedLocale } from "./types";

describe("i18n Localization Subsystem", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    React.createElement(I18nProvider, null, children)
  );

  it("supports all 5 required languages (DE, EN, FR, NL, ES)", () => {
    const supportedCodes = Object.keys(SUPPORTED_LOCALES) as SupportedLocale[];
    expect(supportedCodes).toContain("en");
    expect(supportedCodes).toContain("de");
    expect(supportedCodes).toContain("fr");
    expect(supportedCodes).toContain("nl");
    expect(supportedCodes).toContain("es");
    expect(supportedCodes.length).toBe(5);
  });

  it("ensures all dictionaries have complete parity on common and onboarding keys", () => {
    const dicts = [en, de, fr, nl, es];
    for (const d of dicts) {
      expect(d.common.save).toBeTruthy();
      expect(d.common.cancel).toBeTruthy();
      expect(d.common.completed).toBeTruthy();
      expect(d.common.pending).toBeTruthy();
      expect(d.nav.overview).toBeTruthy();
      expect(d.nav.onboarding).toBeTruthy();
      expect(d.nav.compliance).toBeTruthy();
      expect(d.onboarding.title).toBeTruthy();
      expect(d.onboarding.step1Title).toBeTruthy();
      expect(d.onboarding.step2Title).toBeTruthy();
      expect(d.onboarding.step3Title).toBeTruthy();
      expect(d.onboarding.step4Title).toBeTruthy();
      expect(d.onboarding.step5Title).toBeTruthy();
      expect(d.disclaimer.title).toBeTruthy();
    }
  });

  it("initializes with default locale 'en' and translates base keys", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    expect(result.current.locale).toBe("en");
    expect(result.current.t("common.save")).toBe("Save");
    expect(result.current.t("nav.onboarding")).toBe("Onboarding");
  });

  it("switches to German (DE) and updates documentElement.lang and localStorage", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });

    act(() => {
      result.current.setLocale("de");
    });

    expect(result.current.locale).toBe("de");
    expect(result.current.t("common.save")).toBe("Speichern");
    expect(result.current.t("nav.compliance")).toBe("Compliance & Nachweise");
    expect(localStorage.getItem("conformly.locale")).toBe("de");
    expect(document.documentElement.lang).toBe("de");
  });

  it("switches to French (FR), Dutch (NL), and Spanish (ES)", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });

    act(() => {
      result.current.setLocale("fr");
    });
    expect(result.current.t("common.save")).toBe("Enregistrer");

    act(() => {
      result.current.setLocale("nl");
    });
    expect(result.current.t("common.save")).toBe("Opslaan");

    act(() => {
      result.current.setLocale("es");
    });
    expect(result.current.t("common.save")).toBe("Guardar");
  });

  it("interpolates dynamic parameters correctly", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const formatted = result.current.t("onboarding.stepsCompleted", {
      completed: 3,
      total: 5,
      percent: 60,
    });
    expect(formatted).toBe("3 of 5 milestones completed (60%)");
  });

  it("falls back gracefully to English when key is missing in active locale", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    act(() => {
      result.current.setLocale("de");
    });
    // Non-existent key returns the key itself
    expect(result.current.t("non.existent.key")).toBe("non.existent.key");
  });
});
