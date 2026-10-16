"use client";

import { useI18n } from "@/lib/i18n";

interface Props {
  fileName: string;
  progress: number;
  onCancel: () => void;
}

/** "Lendo seu documento…", barra, nome · percentual e "Cancelar". */
export function ConvertingProgress({ fileName, progress, onCancel }: Props) {
  const { t } = useI18n();
  return (
    <div
      role="status"
      aria-live="polite"
      className="mx-auto flex w-full max-w-[760px] flex-col items-center justify-center gap-[18px] px-6 pt-32 pb-16 text-center sm:pt-40"
    >
      <div className="text-[22px] font-semibold">{t.reading}</div>
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
