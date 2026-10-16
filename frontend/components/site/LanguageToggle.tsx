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
    <div role="group" aria-label={t.langName} className="flex gap-0.5 rounded-lg bg-muted p-[3px]">
      {OPTIONS.map((option) => (
        <button
          key={option.lang}
          type="button"
          lang={option.htmlLang}
          aria-pressed={lang === option.lang}
          onClick={() => setLang(option.lang)}
          className={cn(
            "h-11 min-w-11 cursor-pointer rounded-md px-2.5 text-[13px] font-semibold text-muted-foreground sm:h-9",
            lang === option.lang && "bg-card text-foreground shadow-[0_1px_2px_rgba(20,18,14,.12)]",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
