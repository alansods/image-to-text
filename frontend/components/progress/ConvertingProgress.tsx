"use client";

import { useEffect, useState } from "react";

import { ReadingIllustration } from "@/components/progress/ReadingIllustration";
import { Band } from "@/components/site/Band";
import { useI18n } from "@/lib/i18n";
import type { JobStage } from "@/lib/types/job";
import { cn } from "@/lib/utils";

/** Etapa real da conversão, informada pelo servidor (spec job-processing). */
export interface Step {
  stage: JobStage;
  page: number;
  pages: number;
}

interface Props {
  fileName: string;
  progress: number;
  step: Step;
  onCancel: () => void;
}

const TIP_MS = 6000;
const STAGES = ["preparing", "layout", "reading", "finishing"] as const;

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

/** Ilustração, "Lendo seu documento…", a etapa real, dicas durante a leitura, barra,
 * nome · percentual e "Cancelar". */
export function ConvertingProgress({ fileName, progress, step, onCancel }: Props) {
  const { t } = useI18n();
  const [tip, setTip] = useState(0);
  const reading = step.stage === "reading";

  // Dicas trocam sozinhas só enquanto o texto é lido, e nunca com "reduzir movimento".
  useEffect(() => {
    if (!reading || prefersReducedMotion()) return;
    const timer = setInterval(() => setTip((i) => (i + 1) % t.tips.length), TIP_MS);
    return () => clearInterval(timer);
  }, [reading, t.tips.length]);

  const current = STAGES.indexOf(step.stage as (typeof STAGES)[number]);
  return (
    <div className="flex flex-col">
      <Band className="pb-[110px] sm:pb-[140px]">
        <div className="mx-auto flex max-w-[640px] flex-col gap-2 px-5 pt-6 text-center sm:px-6 sm:pt-10">
          <h1 className="text-[26px] font-bold tracking-[-0.02em] sm:text-[34px]">{t.reading}</h1>
          <p className="text-[15px] text-on-navy-soft sm:text-base">{t.readingSub}</p>
        </div>
      </Band>
      <div className="mx-auto -mt-[84px] w-full max-w-[640px] px-4 pb-16 sm:-mt-[108px] sm:px-6">
        <div className="flex flex-col items-center gap-4 rounded-[22px] bg-card px-5 pt-7 pb-5 text-center shadow-[0_24px_60px_rgba(15,35,71,.18)] sm:gap-[18px] sm:rounded-3xl sm:px-8 sm:pt-9 sm:pb-7">
          <ReadingIllustration />
          <div className="flex flex-col gap-1.5">
            <div role="status" aria-live="polite" className="text-[17px] font-semibold sm:text-lg">
              {t.stage(step.stage, step.page, step.pages)}
            </div>
            {/* Fora da região anunciada: a troca das dicas não interrompe o leitor de tela. */}
            <p
              data-testid={reading ? "progress-tip" : undefined}
              className="m-0 min-h-[2.75em] max-w-[420px] text-sm text-muted-foreground"
            >
              {reading ? t.tips[tip] : ""}
            </p>
          </div>
          <div className="flex w-full flex-col gap-2.5">
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              aria-label={t.progress}
              className="h-2.5 w-full overflow-hidden rounded-full bg-background"
            >
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-between gap-3 text-[13px] text-muted-foreground">
              <span className="truncate">{fileName}</span>
              <span className="font-mono">{progress}%</span>
            </div>
          </div>
          <ol aria-label={t.stepsLabel} className="flex w-full flex-wrap justify-center gap-2 border-t border-border pt-3">
            {STAGES.map((stage, index) => (
              <li
                key={stage}
                aria-current={index === current ? "step" : undefined}
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs font-semibold",
                  index < current && "bg-primary-soft text-[#1f55c4]",
                  index === current && "bg-primary text-primary-foreground",
                  (current < 0 || index > current) && "bg-background text-muted-foreground",
                )}
              >
                {t.stepNames[stage]}
              </li>
            ))}
          </ol>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-11 cursor-pointer items-center rounded-full px-[22px] text-[15px] font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            {t.cancel}
          </button>
        </div>
      </div>
    </div>
  );
}
