"use client";

import Link from "next/link";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="flex min-h-screen flex-col bg-navy">
      <SiteHeader />
      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 pt-12 pb-24 text-center text-on-navy">
        <span aria-hidden="true" className="font-mono text-7xl font-medium text-[#7fa6f5] sm:text-8xl">
          404
        </span>
        <h1 className="text-3xl font-bold tracking-[-0.02em] sm:text-4xl">{t.notFound}</h1>
        <p className="max-w-[460px] text-on-navy-soft sm:text-[17px]">{t.notFoundText}</p>
        <Link
          href="/"
          className="mt-2 inline-flex min-h-[52px] items-center rounded-full bg-white px-8 font-bold text-navy no-underline hover:bg-on-navy"
        >
          {t.backHome}
        </Link>
      </main>
      <SiteFooter />
    </div>
  );
}
