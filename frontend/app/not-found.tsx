"use client";

import Link from "next/link";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-24 text-center">
        <h1 className="text-3xl font-semibold">{t.notFound}</h1>
        <Link href="/" className="inline-flex min-h-11 items-center font-medium text-primary underline-offset-4 hover:underline">
          {t.backHome}
        </Link>
      </main>
      <SiteFooter />
    </div>
  );
}
