"use client";

import Link from "next/link";

import { LanguageToggle } from "@/components/site/LanguageToggle";
import { LogoMark } from "@/components/site/Logo";
import { useI18n } from "@/lib/i18n";

/** Barra superior: logotipo (volta ao envio) e seletor PT | EN. Nada mais. */
export function SiteHeader({ onHome }: { onHome?: () => void }) {
  const { t } = useI18n();
  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex h-16 max-w-[1120px] items-center justify-between gap-4 px-4 sm:px-6">
        <Link
          href="/"
          aria-label={t.home}
          onClick={(event) => {
            if (!onHome) return;
            event.preventDefault();
            onHome();
          }}
          className="flex min-h-11 items-center gap-2.5 rounded-md text-base font-semibold text-foreground no-underline"
        >
          <LogoMark />
          image-to-text
        </Link>
        <LanguageToggle />
      </div>
    </header>
  );
}
