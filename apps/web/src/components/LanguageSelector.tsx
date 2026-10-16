import { Globe2 } from "lucide-react";
import { useTranslation } from "../i18n/I18nContext";
import type { SupportedLocale } from "../i18n/types";

/** Native selection provides complete keyboard and assistive-technology support. */
export function LanguageSelector({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale, availableLocales, t } = useTranslation();
  return <label className="language-selector-container"><Globe2 size={15}/><select aria-label={t("language.selectorLabel")} value={locale} onChange={event => setLocale(event.target.value as SupportedLocale)}>{availableLocales.map(info => <option key={info.code} value={info.code}>{compact ? info.code.toUpperCase() : info.nativeLabel}</option>)}</select></label>;
}
