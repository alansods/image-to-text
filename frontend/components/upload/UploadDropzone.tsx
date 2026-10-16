"use client";

import { Camera, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n, type UploadError } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const ACCEPT = "image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif,application/pdf";

interface Props {
  onFiles: (files: File[]) => void;
  error: UploadError | null;
}

/** Envio: escolher, arrastar ou colar um arquivo; no celular, também "Tirar foto". */
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
    <section className="mx-auto flex w-full max-w-[760px] flex-col gap-7 px-4 pt-12 sm:px-6 sm:pt-[72px]">
      <div className="flex flex-col gap-3 text-center">
        <h1 className="text-[30px] leading-[1.12] font-semibold tracking-[-0.02em] sm:text-[46px]">
          {t.title}
        </h1>
        <p className="mx-auto max-w-[560px] text-base text-muted-foreground sm:text-lg">
          {t.subtitle}
        </p>
      </div>

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
          className="inline-flex h-14 cursor-pointer items-center justify-center gap-2.5 rounded-[10px] bg-primary px-4 text-base font-medium text-primary-foreground"
        >
          <Camera className="size-5" aria-hidden="true" />
          {t.takePhoto}
        </button>
        <button
          type="button"
          onClick={() => picker.current?.click()}
          className="inline-flex h-14 cursor-pointer items-center justify-center gap-2.5 rounded-[10px] border border-border bg-card px-4 text-base font-medium"
        >
          <Upload className="size-5" aria-hidden="true" />
          {t.choose}
        </button>
        <p className="mt-0.5 text-center text-[13px] text-muted-foreground">{t.limits}</p>
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
          "hidden cursor-pointer flex-col items-center gap-4 rounded-2xl border-2 border-dashed border-border-strong bg-card px-6 py-14 text-center pointer-fine:flex",
          dragging && "border-primary bg-primary-soft",
        )}
      >
        <span className="flex size-16 items-center justify-center rounded-full bg-primary-soft text-primary">
          <Upload className="size-7" aria-hidden="true" />
        </span>
        <span className="inline-flex h-12 items-center rounded-lg bg-primary px-7 text-base font-medium text-primary-foreground">
          {t.choose}
        </span>
        <span className="text-sm text-muted-foreground">
          {t.orDrag} <span className="font-mono text-[13px]">Ctrl+V</span>
        </span>
        <span className="text-[13px] text-muted-foreground">{t.limits}</span>
      </button>

      {error && (
        <p
          role="alert"
          className="-mt-3 rounded-lg bg-destructive/10 px-3.5 py-2.5 text-center font-medium text-destructive"
        >
          {t.errors[error]}
        </p>
      )}
    </section>
  );
}
