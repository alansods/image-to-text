"use client";

import { Download, Eye, SquareCheckBig, Upload } from "lucide-react";

import { useI18n } from "@/lib/i18n";

const ICONS = [Upload, Eye, SquareCheckBig, Download];

/** "Como funciona": os quatro passos numa linha do tempo (no celular, de cima para baixo). */
export function HowItWorks() {
  const { t } = useI18n();
  return (
    <section aria-labelledby="how-title" className="flex flex-col gap-7 sm:gap-9">
      <div className="flex flex-col items-center gap-2 text-center">
        <span className="text-[13px] font-semibold tracking-[0.1em] text-primary uppercase">
          {t.howEyebrow}
        </span>
        <h2 id="how-title" className="text-[26px] leading-tight font-bold tracking-[-0.02em] sm:text-[34px]">
          {t.howTitle}
        </h2>
      </div>
      <ol className="grid gap-0 sm:grid-cols-2 sm:gap-6 lg:grid-cols-4">
        {t.steps.map((step, index) => {
          const Icon = ICONS[index];
          const last = index === t.steps.length - 1;
          return (
            <li key={step.title} className="flex gap-4 sm:flex-col sm:items-center sm:gap-3.5 sm:text-center">
              <div className="flex flex-col items-center sm:relative sm:w-full">
                {/* linha que liga os passos: vertical no celular, horizontal nas telas largas */}
                <span aria-hidden="true" className="absolute top-1/2 right-0 left-0 hidden h-0.5 bg-border lg:block" />
                <span
                  aria-hidden="true"
                  className="relative flex size-[52px] shrink-0 items-center justify-center rounded-full border-2 border-primary bg-card text-primary shadow-[0_6px_16px_rgba(15,35,71,.08)] sm:size-16"
                >
                  <Icon className="size-[22px] sm:size-[26px]" strokeWidth={1.9} />
                </span>
                {!last && <span aria-hidden="true" className="min-h-6 w-0.5 flex-1 bg-border sm:hidden" />}
              </div>
              <div className="flex flex-col gap-1.5 pt-1 pb-7 sm:items-center sm:pb-0">
                <span className="text-xs font-bold tracking-[0.1em] text-primary uppercase">{t.step(index + 1)}</span>
                <h3 className="text-lg font-semibold sm:text-[19px]">{step.title}</h3>
                <p className="max-w-[260px] text-[15px] leading-relaxed text-muted-foreground">{step.text}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
