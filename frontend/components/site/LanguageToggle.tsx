"use client";

import { cn } from "@/lib/utils";
import { useI18n, type Lang } from "@/lib/i18n";

const OPTIONS: { lang: Lang; label: string; htmlLang: string }[] = [
  { lang: "pt", label: "PT", htmlLang: "pt-BR" },
  { lang: "en", label: "EN", htmlLang: "en" },
];

export function LanguageToggle() {
  const { lang, setLang, t } = useI18n();
  return (
    <div role="group" aria-label={t.langName} className="flex gap-0.5 rounded-full bg-navy-soft p-[3px]">
      {OPTIONS.map((option) => (
        <button
          key={option.lang}
          type="button"
          lang={option.htmlLang}
          aria-pressed={lang === option.lang}
          onClick={() => setLang(option.lang)}
          className={cn(
            "h-11 min-w-12 cursor-pointer rounded-full px-3.5 text-[13px] font-semibold text-on-navy-soft hover:text-on-navy sm:h-9",
            lang === option.lang && "bg-on-navy text-navy hover:text-navy",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
