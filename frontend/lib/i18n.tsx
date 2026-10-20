"use client";

// Textos da interface em português e inglês (spec site-interface). Nada de texto fixo nos
// componentes; o idioma não é guardado no navegador.
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import type { JobStage } from "@/lib/types/job";

export type Lang = "pt" | "en";

function listPages(pages: number[], and: string): string {
  if (pages.length === 1) return String(pages[0]);
  return `${pages.slice(0, -1).join(", ")} ${and} ${pages[pages.length - 1]}`;
}

const pt = {
  langName: "Idioma",
  home: "image-to-text — início",
  title: "Transforme imagens em texto",
  subtitle:
    "Envie uma foto, print ou PDF escaneado. Em instantes você tem o texto pronto para copiar ou baixar em Word ou PDF.",
  choose: "Escolher arquivo",
  takePhoto: "Tirar foto",
  orDrag: "ou arraste aqui, ou cole com",
  limits: "JPG, PNG, WEBP, HEIC ou PDF · até 20 MB · até 20 páginas",
  upTo: "até 20 MB",
  pagesUpTo: "até 20 páginas",
  reading: "Lendo seu documento…",
  stage: (stage: JobStage, page: number, pages: number): string => {
    const many = pages > 1;
    switch (stage) {
      case "queued":
        return "Na fila, já vai começar…";
      case "preparing":
        return many ? `Preparando a página ${page} de ${pages}` : "Preparando a imagem";
      case "layout":
        return "Encontrando títulos, parágrafos, tabelas e imagens";
      case "reading":
        return many ? `Lendo o texto da página ${page} de ${pages}` : "Lendo o texto";
      case "finishing":
        return "Montando o documento";
    }
  },
  tips: [
    "Cada palavra é lida duas vezes, por dois leitores diferentes, para conferir.",
    "As palavras com dúvida vão aparecer marcadas para você conferir.",
    "Títulos, negrito, tabelas e imagens ficam no mesmo lugar do original.",
    "Nada fica guardado: seu arquivo é apagado em até 1 hora.",
    "No fim, você pode copiar o texto ou baixar em Word e PDF.",
  ],
  progress: "Progresso",
  cancel: "Cancelar",
  another: "Converter outro",
  gate: (n: number) =>
    n === 1 ? "Confira 1 palavra antes de baixar" : `Confira ${n} palavras antes de baixar`,
  gateSub: "Elas estão marcadas no texto. Escolha a forma certa de cada uma.",
  checkNext: "Conferir próxima",
  allChecked: "Tudo conferido",
  copy: "Copiar texto",
  copied: "Copiado",
  downloadWord: "Baixar Word",
  downloadPdf: "Baixar PDF",
  exportFailed: "Não foi possível gerar o arquivo. Tente de novo.",
  pageLabel: (n: number, total: number) => `Página ${n} de ${total}`,
  pageAria: (n: number) => `Página ${n}`,
  inImage: "Na imagem:",
  whichRight: "Qual está certo?",
  typeIt: "Ou digite a correta",
  useTyped: "Usar o que digitei",
  close: "Fechar",
  noWord: "(nenhuma palavra)",
  corrected: (w: string) => `Palavra corrigida: ${w} — alterar`,
  removedWord: "Palavra removida — alterar",
  doubtLabel: (w: string) => `Palavra em dúvida: ${w}`,
  cropAlt: "Trecho da imagem original com a palavra destacada",
  figureAlt: "Imagem do original",
  quality: (pages: number[], total: number) =>
    total === 1
      ? "A imagem tem baixa qualidade. Confira o texto e a formatação (negrito, itálico) com atenção."
      : pages.length === 1
        ? `A página ${pages[0]} tem baixa qualidade. Confira o texto e a formatação (negrito, itálico) com atenção.`
        : `As páginas ${listPages(pages, "e")} têm baixa qualidade. Confira o texto e a formatação (negrito, itálico) com atenção.`,
  saveFailed: "Não foi possível salvar. Verifique sua conexão.",
  notFound: "Página não encontrada",
  backHome: "Voltar ao início",
  notFoundText: "Esse endereço não existe. O site tem uma página só: a de enviar o arquivo.",
  badge: "Grátis · sem cadastro · nada fica guardado",
  howEyebrow: "Como funciona",
  howTitle: "Da imagem ao documento em quatro passos",
  step: (n: number) => `Passo ${n}`,
  steps: [
    {
      title: "Envie o arquivo",
      text: "Foto, print ou PDF escaneado. Arraste, cole ou, no celular, tire a foto na hora.",
    },
    {
      title: "A leitura começa sozinha",
      text: "Cada palavra é lida duas vezes. Títulos, negrito, tabelas e imagens ficam no lugar.",
    },
    {
      title: "Confira as dúvidas",
      text: "Palavras incertas ficam marcadas em amarelo. Escolha a certa ou digite; dá para trocar depois.",
    },
    {
      title: "Baixe ou copie",
      text: "PDF ou Word com a mesma paginação do original, ou só o texto.",
    },
  ],
  ctaTitle: "Pronto para começar?",
  ctaText: "Sem cadastro e sem custo. Seu arquivo é apagado em até 1 hora.",
  readingSub: "Pode deixar esta página aberta. O resultado aparece aqui quando terminar.",
  stepNames: { preparing: "Preparar", layout: "Estrutura", reading: "Leitura", finishing: "Montagem" },
  stepsLabel: "Etapas",
  almostReady: "Quase pronto",
  barLabel: "Andamento da conferência",
  barLeft: (n: number) => (n === 1 ? "Falta 1 palavra para conferir" : `Faltam ${n} palavras para conferir`),
  barDone: "Seu documento está pronto.",
  errors: {
    unsupported_format: "Esse arquivo não é uma imagem nem PDF. Tente JPG, PNG, HEIC ou PDF.",
    file_too_large: "O arquivo passa do limite de 20 MB.",
    too_many_pages: "O PDF passa do limite de 20 páginas.",
    pdf_password: "PDF protegido por senha não é suportado",
    multiple_files: "Envie um arquivo por vez.",
    too_many_active_jobs: "Aguarde a conclusão de uma conversão em andamento.",
    network: "Não foi possível enviar. Verifique sua conexão.",
    unreadable: "Não foi possível ler esse arquivo.",
  },
};

export type Dictionary = typeof pt;
export type UploadError = keyof Dictionary["errors"];

const en: Dictionary = {
  langName: "Language",
  home: "image-to-text — home",
  title: "Turn images into text",
  subtitle:
    "Upload a photo, screenshot or scanned PDF. In moments you have the text ready to copy or download as Word or PDF.",
  choose: "Choose file",
  takePhoto: "Take photo",
  orDrag: "or drag it here, or paste with",
  limits: "JPG, PNG, WEBP, HEIC or PDF · up to 20 MB · up to 20 pages",
  upTo: "up to 20 MB",
  pagesUpTo: "up to 20 pages",
  reading: "Reading your document…",
  stage: (stage: JobStage, page: number, pages: number): string => {
    const many = pages > 1;
    switch (stage) {
      case "queued":
        return "In line, starting soon…";
      case "preparing":
        return many ? `Preparing page ${page} of ${pages}` : "Preparing the image";
      case "layout":
        return "Finding headings, paragraphs, tables and images";
      case "reading":
        return many ? `Reading the text of page ${page} of ${pages}` : "Reading the text";
      case "finishing":
        return "Putting the document together";
    }
  },
  tips: [
    "Every word is read twice, by two different readers, to double-check it.",
    "Words we are unsure about will be marked for you to check.",
    "Headings, bold text, tables and images stay where they were in the original.",
    "Nothing is kept: your file is deleted within 1 hour.",
    "At the end you can copy the text or download it as Word and PDF.",
  ],
  progress: "Progress",
  cancel: "Cancel",
  another: "Convert another",
  gate: (n: number) =>
    n === 1 ? "Check 1 word before downloading" : `Check ${n} words before downloading`,
  gateSub: "They are marked in the text. Pick the right form of each one.",
  checkNext: "Check next",
  allChecked: "All checked",
  copy: "Copy text",
  copied: "Copied",
  downloadWord: "Download Word",
  downloadPdf: "Download PDF",
  exportFailed: "Could not generate the file. Try again.",
  pageLabel: (n: number, total: number) => `Page ${n} of ${total}`,
  pageAria: (n: number) => `Page ${n}`,
  inImage: "In the image:",
  whichRight: "Which one is right?",
  typeIt: "Or type the right one",
  useTyped: "Use what I typed",
  close: "Close",
  noWord: "(no word)",
  corrected: (w: string) => `Corrected word: ${w} — change`,
  removedWord: "Word removed — change",
  doubtLabel: (w: string) => `Uncertain word: ${w}`,
  cropAlt: "Excerpt of the original image with the word highlighted",
  figureAlt: "Image from the original",
  quality: (pages: number[], total: number) =>
    total === 1
      ? "The image has low quality. Check the text and formatting (bold, italic) carefully."
      : pages.length === 1
        ? `Page ${pages[0]} has low quality. Check the text and formatting (bold, italic) carefully.`
        : `Pages ${listPages(pages, "and")} have low quality. Check the text and formatting (bold, italic) carefully.`,
  saveFailed: "Could not save. Check your connection.",
  notFound: "Page not found",
  backHome: "Back to home",
  notFoundText: "This address does not exist. The site has a single page: the one to upload your file.",
  badge: "Free · no sign-up · nothing is kept",
  howEyebrow: "How it works",
  howTitle: "From image to document in four steps",
  step: (n: number) => `Step ${n}`,
  steps: [
    {
      title: "Upload the file",
      text: "Photo, screenshot or scanned PDF. Drag it, paste it or, on a phone, take the photo right away.",
    },
    {
      title: "Reading starts on its own",
      text: "Every word is read twice. Headings, bold text, tables and images stay in place.",
    },
    {
      title: "Check the doubts",
      text: "Uncertain words are marked in yellow. Pick the right one or type it; you can change it later.",
    },
    {
      title: "Download or copy",
      text: "PDF or Word with the same pages as the original, or just the text.",
    },
  ],
  ctaTitle: "Ready to start?",
  ctaText: "No sign-up and no cost. Your file is deleted within 1 hour.",
  readingSub: "You can keep this page open. The result shows up here when it is done.",
  stepNames: { preparing: "Prepare", layout: "Structure", reading: "Reading", finishing: "Assembly" },
  stepsLabel: "Steps",
  almostReady: "Almost done",
  barLabel: "Review progress",
  barLeft: (n: number) => (n === 1 ? "1 word left to check" : `${n} words left to check`),
  barDone: "Your document is ready.",
  errors: {
    unsupported_format: "This file is not an image or PDF. Try JPG, PNG, HEIC or PDF.",
    file_too_large: "The file is over the 20 MB limit.",
    too_many_pages: "The PDF is over the 20-page limit.",
    pdf_password: "Password-protected PDFs are not supported",
    multiple_files: "Send one file at a time.",
    too_many_active_jobs: "Wait for a conversion in progress to finish.",
    network: "Could not upload. Check your connection.",
    unreadable: "Could not read this file.",
  },
};

export const dictionaries: Record<Lang, Dictionary> = { pt, en };

/** Inglês quando o idioma preferido do navegador é inglês; português em qualquer outro caso. */
export function detectLang(languages: readonly string[]): Lang {
  return languages[0]?.toLowerCase().startsWith("en") ? "en" : "pt";
}

interface I18n {
  lang: Lang;
  t: Dictionary;
  setLang: (lang: Lang) => void;
}

const I18nContext = createContext<I18n>({ lang: "pt", t: pt, setLang: () => {} });

const noSubscription = () => () => {};

function browserLang(): Lang {
  return detectLang(navigator.languages?.length ? navigator.languages : [navigator.language]);
}

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  // Idioma do navegador lido no cliente; no servidor (e na hidratação) começa em português.
  const detected = useSyncExternalStore(noSubscription, browserLang, () => "pt" as Lang);
  const [chosen, setLang] = useState<Lang | null>(initial ?? null);
  const lang = chosen ?? detected;

  useEffect(() => {
    document.documentElement.lang = lang === "en" ? "en" : "pt-BR";
  }, [lang]);

  const value = useMemo(() => ({ lang, t: dictionaries[lang], setLang }), [lang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  return useContext(I18nContext);
}
