import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConverterApp } from "@/components/app/ConverterApp";
import { I18nProvider, type Lang } from "@/lib/i18n";
import type { Document, Word } from "@/lib/types/document";

function word(id: string, text: string, status: Word["status"] = "accepted", alts: string[] = []): Word {
  return {
    id, text, bbox: { x: 100, y: 100, w: 120, h: 46 }, confidence: 0.9, bold: false, italic: false,
    alternatives: alts.map((t, i) => ({ text: t, confidence: 0.9 - i * 0.1, source: "paddle" as const })),
    status, resolved_by: null,
  };
}

function documentWith(words: Word[], quality: Document["pages"][0]["quality_issues"] = []): Document {
  return {
    id: "j1",
    source_file: "contrato.pdf",
    counts: { accepted: 0, resolved: 0, uncertain: 0, edited: 0 },
    pages: [
      {
        index: 0, width: 2480, height: 3508, page_size: { w_pt: 595, h_pt: 842 }, columns: 1,
        image_ref: "pages/0.png", blank: false, quality_issues: quality,
        counts: { accepted: 0, resolved: 0, uncertain: 0, edited: 0 },
        blocks: [
          {
            id: "b0", type: "paragraph", bbox: { x: 100, y: 100, w: 2000, h: 60 }, order: 0, column: 0,
            align: "left", rel_size: 1, words, cells: [], items: [], image_ref: null, confidence: 0.9,
          },
        ],
      },
    ],
  };
}

const DOUBTS = documentWith([
  word("w0", "assinado"),
  word("w1", "SlLVA", "uncertain", ["SlLVA", "SILVA"]),
  word("w2", "acerv0", "uncertain", ["acerv0", "acervo"]),
]);

type Handler = (url: string, init?: RequestInit) => { status?: number; body?: unknown } | undefined;

let handler: Handler;
const calls: { url: string; init?: RequestInit }[] = [];

beforeEach(() => {
  calls.length = 0;
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const reply = handler(url, init) ?? { status: 404, body: { error: "not_found" } };
      const status = reply.status ?? 200;
      return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
        status,
        headers: { "content-type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function renderApp(lang: Lang = "pt") {
  return render(
    <I18nProvider initial={lang}>
      <ConverterApp />
    </I18nProvider>,
  );
}

function pngFile(name = "foto.png") {
  return new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0, 0, 0, 0, 0, 0, 0, 0])], name, {
    type: "image/png",
  });
}

async function upload(file: File | File[]) {
  const input = screen.getByTestId("file-input") as HTMLInputElement;
  await act(async () => {
    fireEvent.change(input, { target: { files: Array.isArray(file) ? file : [file] } });
  });
}

/** Servidor que conclui a conversão na 2ª consulta e devolve `doc`. */
function serverFinishing(doc: Document) {
  let polls = 0;
  handler = (url, init) => {
    if (url.endsWith("/jobs") && init?.method === "POST") {
      return { status: 201, body: { id: "j1", source_file: doc.source_file, created_at: "", state: "queued", progress: 0, error: null } };
    }
    if (url.endsWith("/jobs/j1")) {
      polls += 1;
      return { body: { id: "j1", source_file: doc.source_file, created_at: "", state: polls > 1 ? "done" : "processing", progress: polls > 1 ? 100 : 40, error: null } };
    }
    if (url.endsWith("/jobs/j1/result") && init?.method === "PATCH") return { body: doc };
    if (url.endsWith("/jobs/j1/result")) return { body: doc };
    return undefined;
  };
}

async function untilResult() {
  await screen.findByText("Lendo seu documento…");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3200);
  });
  await screen.findByRole("article", { name: "Página 1" });
}

describe("moldura e idioma", () => {
  it("troca para inglês na hora, sem recarregar", async () => {
    handler = () => undefined;
    renderApp();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Transforme imagens em texto");

    await userEvent.click(screen.getByRole("button", { name: "EN" }));

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Turn images into text");
    expect(screen.getAllByText("Choose file").length).toBeGreaterThan(0);
  });

  it("rodapé só com logotipo e o ano", () => {
    handler = () => undefined;
    renderApp();
    expect(screen.getByRole("contentinfo")).toHaveTextContent(`© ${new Date().getFullYear()} image-to-text`);
  });
});

describe("envio", () => {
  it("dois arquivos de uma vez são recusados sem enviar nada", async () => {
    handler = () => undefined;
    renderApp();

    await upload([pngFile("a.png"), pngFile("b.png")]);

    expect(screen.getByRole("alert")).toHaveTextContent("Envie um arquivo por vez.");
    expect(calls).toHaveLength(0);
  });

  it("formato recusado pelo servidor mostra a mensagem da spec", async () => {
    handler = () => ({ status: 400, body: { error: "unsupported_format" } });
    renderApp();

    await upload(pngFile("anim.gif"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Esse arquivo não é uma imagem nem PDF. Tente JPG, PNG, HEIC ou PDF.",
    );
  });

  it("queda de conexão volta ao envio com a mensagem de envio", async () => {
    handler = () => undefined;
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    renderApp();

    await upload(pngFile());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível enviar. Verifique sua conexão.",
    );
  });

  it("arquivo válido vai direto ao progresso e depois ao resultado", async () => {
    serverFinishing(DOUBTS);
    renderApp();

    await upload(pngFile());

    expect(await screen.findByText("Lendo seu documento…")).toBeInTheDocument();
    await untilResult();
    expect(screen.getByText("contrato.pdf")).toBeInTheDocument();
  });

  it("cancelar apaga a conversão e volta ao envio", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());

    await userEvent.click(await screen.findByRole("button", { name: "Cancelar" }));

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Transforme imagens em texto");
    expect(calls.some((c) => c.url.endsWith("/jobs/j1") && c.init?.method === "DELETE")).toBe(true);
  });

  it("conversão que falhou volta ao envio com 'Não foi possível ler esse arquivo.'", async () => {
    handler = (url, init) => {
      if (init?.method === "POST") return { status: 201, body: { id: "j1", source_file: "x.png", created_at: "", state: "queued", progress: 0, error: null } };
      return { body: { id: "j1", source_file: "x.png", created_at: "", state: "failed", progress: 0, error: "unreadable" } };
    };
    renderApp();
    await upload(pngFile());
    await screen.findByText("Lendo seu documento…");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível ler esse arquivo.");
  });
});

describe("conferência", () => {
  it("dúvidas pendentes escondem cópia e download", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();

    expect(screen.getByText("Confira 2 palavras antes de baixar")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Copiar texto/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Baixar Word/ })).toBeNull();
    const doubt = screen.getByRole("button", { name: "Palavra em dúvida: SlLVA" });
    expect(doubt.className).toContain("decoration-wavy");
  });

  it("escolher resolve, grava no servidor, diminui o contador e abre a próxima", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();

    await userEvent.click(screen.getByRole("button", { name: "Conferir próxima" }));
    const dialog = await screen.findByRole("dialog", { name: "Qual está certo?" });
    const option = within(dialog).getByRole("button", { name: "SILVA" });
    expect(within(option).getByText("I").className).toContain("bg-doubt");

    await userEvent.click(option);

    expect(screen.getByText("Confira 1 palavra antes de baixar")).toBeInTheDocument();
    const patch = calls.find((c) => c.init?.method === "PATCH");
    expect(JSON.parse(String(patch?.init?.body))).toEqual({ words: [{ id: "w1", text: "SILVA" }] });
    expect(screen.getByText("SILVA")).toBeInTheDocument();
    const next = await screen.findByRole("dialog", { name: "Qual está certo?" });
    expect(within(next).getByRole("button", { name: "acervo" })).toBeInTheDocument();
  });

  it("Esc fecha sem resolver", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();

    await userEvent.click(screen.getByRole("button", { name: "Palavra em dúvida: SlLVA" }));
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText("Confira 2 palavras antes de baixar")).toBeInTheDocument();
  });

  it("texto digitado resolve a palavra e, sem dúvidas, libera copiar e baixar", async () => {
    serverFinishing(documentWith([word("w1", "SlLVA", "uncertain", ["SlLVA", "SlLVA2"])]));
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderApp();
    await upload(pngFile());
    await untilResult();

    await userEvent.click(screen.getByRole("button", { name: "Conferir próxima" }));
    await userEvent.type(await screen.findByRole("textbox", { name: "Ou digite a correta" }), "SILVEIRA");
    await userEvent.click(screen.getByRole("button", { name: "Usar o que digitei" }));

    expect(await screen.findByText("Tudo conferido")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copiar texto" }));
    expect(writeText).toHaveBeenCalledWith("SILVEIRA");
    expect(screen.getByRole("button", { name: "Copiado" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Baixar Word" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Baixar PDF" })).toBeInTheDocument();
  });
});

describe("aviso de qualidade", () => {
  it("aparece em imagem ruim e não bloqueia o download", async () => {
    serverFinishing(documentWith([word("w0", "texto")], ["resolution"]));
    renderApp();
    await upload(pngFile());
    await untilResult();

    expect(screen.getByText(/A imagem tem baixa qualidade/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Baixar PDF" })).toBeInTheDocument();
  });

  it("não aparece em imagem nítida", async () => {
    serverFinishing(documentWith([word("w0", "texto")]));
    renderApp();
    await upload(pngFile());
    await untilResult();

    expect(screen.queryByText(/baixa qualidade/)).toBeNull();
  });
});
