"use client";

import { Camera, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { HowItWorks } from "@/components/home/HowItWorks";
import { Band } from "@/components/site/Band";
import { useI18n, type UploadError } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const ACCEPT = "image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif,application/pdf";
const FORMATS = ["JPG", "PNG", "WEBP", "HEIC", "PDF"];

interface Props {
  onFiles: (files: File[]) => void;
  error: UploadError | null;
}

/** Página inicial (spec site-interface): faixa com o título, cartão de envio (escolher,
 * arrastar ou colar; no celular, também "Tirar foto"), "Como funciona" e a chamada final. */
export function UploadDropzone({ onFiles, error }: Props) {
  const { t } = useI18n();
  const picker = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const files = [...(event.clipboardData?.files ?? [])];
      if (files.length > 0) {
        event.preventDefault();
        onFiles(files);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [onFiles]);

  const fromInput = (input: HTMLInputElement | null) => {
    const files = [...(input?.files ?? [])];
    if (input) input.value = "";
    if (files.length > 0) onFiles(files);
  };

  return (
    <div className="flex flex-col">
      <Band className="pb-24 sm:pb-[120px]">
        <section
          aria-labelledby="home-title"
          className="mx-auto flex max-w-[1140px] flex-col items-center gap-3.5 px-5 pt-7 text-center sm:gap-[18px] sm:px-6 sm:pt-14"
        >
          <span className="rounded-full bg-navy-soft px-3.5 py-1.5 text-xs font-medium text-on-navy-soft sm:text-[13px]">
            {t.badge}
          </span>
          <h1
            id="home-title"
            className="max-w-[760px] text-[34px] leading-[1.08] font-bold tracking-[-0.025em] sm:text-[54px]"
          >
            {t.title}
          </h1>
          <p className="max-w-[620px] text-base leading-normal text-on-navy-soft sm:text-[19px]">{t.subtitle}</p>
        </section>
      </Band>

      <div className="mx-auto -mt-[72px] flex w-full max-w-[1140px] flex-col gap-12 px-4 pb-16 sm:-mt-[88px] sm:gap-20 sm:px-6 sm:pb-20">
        <div className="mx-auto w-full max-w-[720px] rounded-[22px] bg-card p-5 shadow-[0_24px_60px_rgba(15,35,71,.18)] sm:rounded-3xl sm:p-3">
          <input
            ref={picker}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            data-testid="file-input"
            onChange={(e) => fromInput(e.currentTarget)}
          />
          <input
            ref={camera}
            type="file"
            accept="image/*"
            capture="environment"
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(e) => fromInput(e.currentTarget)}
          />

          {/* Celular: botões grandes; a área de arrastar não faz sentido no toque. */}
          <div className="flex flex-col gap-2.5 pointer-fine:hidden">
            <button
              type="button"
              onClick={() => camera.current?.click()}
              className="inline-flex h-14 cursor-pointer items-center justify-center gap-2.5 rounded-full bg-primary px-4 text-base font-semibold text-primary-foreground shadow-[0_8px_20px_rgba(37,99,217,.3)]"
            >
              <Camera className="size-5" aria-hidden="true" />
              {t.takePhoto}
            </button>
            <button
              type="button"
              onClick={() => picker.current?.click()}
              className="inline-flex h-14 cursor-pointer items-center justify-center gap-2.5 rounded-full bg-primary-soft px-4 text-base font-semibold text-navy"
            >
              <Upload className="size-5" aria-hidden="true" />
              {t.choose}
            </button>
            <p className="mt-1 text-center text-[13px] text-muted-foreground">{t.limits}</p>
          </div>

          <button
            type="button"
            onClick={() => picker.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              onFiles([...e.dataTransfer.files]);
            }}
            className={cn(
              "hidden w-full cursor-pointer flex-col items-center gap-3.5 rounded-[18px] border-2 border-dashed border-border px-6 py-10 text-center pointer-fine:flex",
              dragging && "border-primary bg-primary-soft",
            )}
          >
            <span className="flex size-[60px] items-center justify-center rounded-[18px] bg-primary-soft text-primary">
              <Upload className="size-7" aria-hidden="true" />
            </span>
            <span className="inline-flex h-[52px] items-center rounded-full bg-primary px-8 text-base font-semibold text-primary-foreground shadow-[0_8px_20px_rgba(37,99,217,.3)]">
              {t.choose}
            </span>
            <span className="text-sm text-muted-foreground">
              {t.orDrag}{" "}
              <kbd className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono text-xs">Ctrl+V</kbd>
            </span>
            <span className="flex flex-wrap justify-center gap-1.5" aria-label={t.limits}>
              {[...FORMATS, t.upTo, t.pagesUpTo].map((label) => (
                <span key={label} aria-hidden="true" className="rounded-full bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground">
                  {label}
                </span>
              ))}
            </span>
          </button>

          {error && (
            <p role="alert" className="mt-3 rounded-xl bg-destructive/10 px-3.5 py-2.5 text-center font-medium text-destructive">
              {t.errors[error]}
            </p>
          )}
        </div>

        <HowItWorks />

        <section
          aria-labelledby="cta-title"
          className="flex flex-col gap-3.5 rounded-[22px] bg-primary px-5 py-6 text-primary-foreground sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-5 sm:rounded-3xl sm:px-9 sm:py-8"
        >
          <div className="flex flex-col gap-1.5">
            <h2 id="cta-title" className="text-[22px] font-bold sm:text-[26px]">
              {t.ctaTitle}
            </h2>
            <p className="text-[15px] text-[#e3ecff] sm:text-base">{t.ctaText}</p>
          </div>
          <button
            type="button"
            onClick={() => picker.current?.click()}
            className="inline-flex h-[52px] cursor-pointer items-center justify-center rounded-full bg-white px-8 text-base font-bold text-navy hover:bg-on-navy"
          >
            {t.choose}
          </button>
        </section>
      </div>
    </div>
  );
}
