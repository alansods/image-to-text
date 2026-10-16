"use client";

import { useSyncExternalStore } from "react";

import { LogoMark } from "@/components/site/Logo";

const noSubscription = () => () => {};

/** Rodapé: logotipo e "© ano image-to-text". Nada mais. O ano é lido no navegador: o Next
 * não deixa a página pré-renderizada depender do relógio do servidor. */
export function SiteFooter() {
  const year = useSyncExternalStore(
    noSubscription,
    () => new Date().getFullYear(),
    () => null,
  );
  return (
    <footer className="border-t border-border bg-card">
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-x-8 gap-y-3 px-4 py-7 sm:px-6">
        <span className="flex items-center gap-2 font-semibold">
          <LogoMark size={22} />
          image-to-text
        </span>
        <span className="text-[13px] text-muted-foreground">
          ©{year ? ` ${year}` : ""} image-to-text
        </span>
      </div>
    </footer>
  );
}
