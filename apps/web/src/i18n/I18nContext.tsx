import React, { createContext, useContext, useEffect, useState } from "react";
import { de } from "./locales/de";
import { en } from "./locales/en";
import { es } from "./locales/es";
import { fr } from "./locales/fr";
import { nl } from "./locales/nl";
import {
  SUPPORTED_LOCALES,
  type LocaleInfo,
  type SupportedLocale,
  type TranslationDictionary,
} from "./types";

const LOCAL_STORAGE_KEY = "conformly.locale";

const dictionaries: Record<SupportedLocale, TranslationDictionary> = {
  en,
  de,
  fr,
  nl,
  es,
};

interface I18nContextValue {
  locale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  availableLocales: LocaleInfo[];
}

const I18nContext = createContext<I18nContextValue | null>(null);

function getNestedValue(obj: Record<string, unknown>, path: string): string | null {
  const parts = path.split(".");
  let current: unknown = obj;
  for (const part of parts) {
    if (current && typeof current === "object" && part in current) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return null;
    }
  }
  return typeof current === "string" ? current : null;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<SupportedLocale>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY) as SupportedLocale | null;
      if (saved && saved in dictionaries) {
        return saved;
      }
      if (typeof navigator !== "undefined" && navigator.language) {
        const browserLang = navigator.language.slice(0, 2).toLowerCase() as SupportedLocale;
        if (browserLang in dictionaries) {
          return browserLang;
        }
      }
    } catch {
      // Ignore localStorage errors in restricted environments
    }
    return "en";
  });

  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, locale);
    } catch {
      // Ignore localStorage write errors
    }
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const setLocale = (newLocale: SupportedLocale) => {
    if (newLocale in dictionaries) {
      setLocaleState(newLocale);
    }
  };

  const t = (key: string, params?: Record<string, string | number>): string => {
    const currentDict = dictionaries[locale] as unknown as Record<string, unknown>;
    const fallbackDict = dictionaries.en as unknown as Record<string, unknown>;

    let text = getNestedValue(currentDict, key);
    if (!text) {
      text = getNestedValue(fallbackDict, key);
    }
    if (!text) {
      return key;
    }

    if (params) {
      return text.replace(/\{(\w+)\}/g, (match, paramKey) => {
        return paramKey in params ? String(params[paramKey]) : match;
      });
    }
    return text;
  };

  const availableLocales = Object.values(SUPPORTED_LOCALES);

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, availableLocales }}>
      {children}
    </I18nContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTranslation() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useTranslation must be used within an I18nProvider");
  }
  return context;
}
