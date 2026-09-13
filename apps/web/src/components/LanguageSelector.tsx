import { useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import type { SupportedLocale } from "../i18n/types";

export function LanguageSelector({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale, availableLocales, t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentInfo = availableLocales.find((l) => l.code === locale) ?? availableLocales[0];

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleSelect = (code: SupportedLocale) => {
    setLocale(code);
    setIsOpen(false);
  };

  return (
    <div
      ref={containerRef}
      className="language-selector-container"
      style={{ position: "relative", display: "inline-block" }}
    >
      <button
        type="button"
        className="language-selector-btn"
        aria-label={t("language.selectorLabel")}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
          padding: compact ? "0.3rem 0.6rem" : "0.4rem 0.8rem",
          fontSize: "0.8125rem",
          fontWeight: 500,
          background: "var(--bg-elevated)",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-md)",
          color: "var(--text-primary)",
          cursor: "pointer",
          transition: "var(--transition-fast)",
        }}
      >
        <span aria-hidden="true">{currentInfo.flag}</span>
        <span>{compact ? currentInfo.code.toUpperCase() : currentInfo.nativeLabel}</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: isOpen ? "rotate(180deg)" : "none",
            transition: "transform 0.2s ease",
            opacity: 0.7,
          }}
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {isOpen && (
        <ul
          role="listbox"
          aria-label={t("language.selectorLabel")}
          className="language-dropdown-menu"
          style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: 0,
            zIndex: 1000,
            minWidth: "140px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            padding: "0.35rem",
            margin: 0,
            listStyle: "none",
          }}
        >
          {availableLocales.map((loc) => {
            const isSelected = loc.code === locale;
            return (
              <li
                key={loc.code}
                role="option"
                aria-selected={isSelected}
                onClick={() => handleSelect(loc.code)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0.4rem 0.65rem",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "0.8125rem",
                  cursor: "pointer",
                  color: isSelected ? "var(--accent)" : "var(--text-primary)",
                  background: isSelected ? "var(--accent-subtle)" : "transparent",
                  fontWeight: isSelected ? 600 : 400,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span aria-hidden="true">{loc.flag}</span>
                  <span>{loc.nativeLabel}</span>
                </div>
                {isSelected && (
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
