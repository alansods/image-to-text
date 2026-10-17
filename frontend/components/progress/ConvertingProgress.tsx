"use client";

import { useEffect, useState } from "react";

import { ReadingIllustration } from "@/components/progress/ReadingIllustration";
import { useI18n } from "@/lib/i18n";
import type { JobStage } from "@/lib/types/job";

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

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col items-center justify-center gap-[18px] px-6 pt-20 pb-16 text-center sm:pt-28">
      <ReadingIllustration />
      <div role="status" aria-live="polite" className="flex flex-col items-center gap-1.5">
        <div className="text-[22px] font-semibold">{t.reading}</div>
        <div className="text-[15px] text-foreground/80">
          {t.stage(step.stage, step.page, step.pages)}
        </div>
      </div>
      {/* Fora da região anunciada: a troca das dicas não interrompe o leitor de tela. */}
      <p
        data-testid={reading ? "progress-tip" : undefined}
        className="m-0 min-h-[2.75em] max-w-[420px] text-sm text-muted-foreground"
      >
        {reading ? t.tips[tip] : ""}
      </p>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        aria-label={t.progress}
        className="h-2 w-full max-w-[420px] overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="text-sm text-muted-foreground">
        {fileName} · <span className="font-mono">{progress}%</span>
      </div>
      <button
        type="button"
        onClick={onCancel}
        className="mt-2 inline-flex h-11 cursor-pointer items-center rounded-lg px-[18px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        {t.cancel}
      </button>
    </div>
  );
}
