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
            align: "left", rel_size: 1, font_pt: null, words, cells: [], items: [], image_ref: null, confidence: 0.9,
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
  vi.restoreAllMocks();
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
      const done = polls > 1;
      return { body: { id: "j1", source_file: doc.source_file, created_at: "", state: done ? "done" : "processing", progress: done ? 100 : 40, stage: done ? "finishing" : "reading", page: 1, pages: 1, error: null } };
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

/** Servidor que fica em `job` (etapa, página) sem terminar. */
function serverAt(job: { state: string; stage: string; page: number; pages: number; progress: number }) {
  handler = (url, init) => {
    if (url.endsWith("/jobs") && init?.method === "POST") {
      return { status: 201, body: { id: "j1", source_file: "contrato.pdf", created_at: "", state: "queued", progress: 0, stage: "queued", page: 0, pages: 0, error: null } };
    }
    if (url.endsWith("/jobs/j1")) return { body: { id: "j1", source_file: "contrato.pdf", created_at: "", error: null, ...job } };
    return undefined;
  };
}

/** IntersectionObserver falso: o teste diz se o cartão do topo está na tela. */
let setTopVisible: (visible: boolean) => void = () => undefined;
function stubObserver() {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: IntersectionObserverCallback) {
        setTopVisible = (visible) =>
          callback([{ isIntersecting: visible } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
      }
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return [];
      }
    },
  );
}

function reducedMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

async function poll() {
  await screen.findByRole("progressbar");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1600);
  });
}

describe("progresso", () => {
  it("mostra a etapa real com a página, uma ilustração e dicas que trocam", async () => {
    reducedMotion(false);
    serverAt({ state: "processing", stage: "reading", page: 2, pages: 5, progress: 30 });
    renderApp();
    await upload(pngFile());
    await poll();

    expect(screen.getByText("Lendo o texto da página 2 de 5")).toBeInTheDocument();
    expect(screen.getByTestId("reading-illustration")).toBeInTheDocument();
    const tip = screen.getByTestId("progress-tip");
    const first = tip.textContent;
    expect(first).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6100);
    });
    expect(screen.getByTestId("progress-tip").textContent).not.toBe(first);
  });

  it("na fila avisa que já vai começar, sem dica", async () => {
    reducedMotion(false);
    serverAt({ state: "queued", stage: "queued", page: 0, pages: 0, progress: 0 });
    renderApp();
    await upload(pngFile());
    await poll();

    expect(screen.getByText("Na fila, já vai começar…")).toBeInTheDocument();
    expect(screen.queryByTestId("progress-tip")).toBeNull();
  });

  it("documento de uma página não fala em 'página 1 de 1'", async () => {
    reducedMotion(false);
    serverAt({ state: "processing", stage: "preparing", page: 1, pages: 1, progress: 5 });
    renderApp();
    await upload(pngFile());
    await poll();

    expect(screen.getByText("Preparando a imagem")).toBeInTheDocument();
  });

  it("com 'reduzir movimento' a dica não troca sozinha", async () => {
    reducedMotion(true);
    serverAt({ state: "processing", stage: "reading", page: 1, pages: 3, progress: 20 });
    renderApp();
    await upload(pngFile());
    await poll();
    const first = screen.getByTestId("progress-tip").textContent;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(13000);
    });
    expect(screen.getByTestId("progress-tip").textContent).toBe(first);
  });

  it("mostra as quatro etapas com a atual destacada", async () => {
    reducedMotion(false);
    serverAt({ state: "processing", stage: "reading", page: 1, pages: 1, progress: 50 });
    renderApp();
    await upload(pngFile());
    await poll();

    const steps = within(screen.getByRole("list", { name: "Etapas" })).getAllByRole("listitem");
    expect(steps.map((li) => li.textContent)).toEqual(["Preparar", "Estrutura", "Leitura", "Montagem"]);
    expect(steps.map((li) => li.getAttribute("aria-current"))).toEqual([null, null, "step", null]);
  });

  it("em inglês", async () => {
    reducedMotion(false);
    serverAt({ state: "processing", stage: "layout", page: 3, pages: 4, progress: 60 });
    renderApp("en");
    await upload(pngFile());
    await poll();

    expect(screen.getByText("Finding headings, paragraphs, tables and images")).toBeInTheDocument();
  });
});

describe("página inicial", () => {
  it("ensina a usar: quatro passos e a chamada final", () => {
    handler = () => undefined;
    renderApp();

    const how = screen.getByRole("region", { name: "Da imagem ao documento em quatro passos" });
    expect(within(how).getAllByRole("listitem").map((li) => within(li).getByRole("heading").textContent)).toEqual([
      "Envie o arquivo",
      "A leitura começa sozinha",
      "Confira as dúvidas",
      "Baixe ou copie",
    ]);
    expect(screen.getByRole("heading", { name: "Pronto para começar?" })).toBeInTheDocument();
    expect(screen.getByText("Grátis · sem cadastro · nada fica guardado")).toBeInTheDocument();
  });

  it("mostra os limites de tamanho e de páginas antes do envio", () => {
    handler = () => undefined;
    renderApp();

    expect(screen.getAllByText(/até 20 páginas/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/até 20 MB/).length).toBeGreaterThan(0);
  });

  it("o botão da chamada final abre a mesma escolha de arquivo", async () => {
    handler = () => undefined;
    renderApp();
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const click = vi.spyOn(input, "click");

    const cta = screen.getByRole("region", { name: "Pronto para começar?" });
    await userEvent.click(within(cta).getByRole("button", { name: "Escolher arquivo" }));

    expect(click).toHaveBeenCalled();
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

  it("escolher resolve, grava, fica na palavra corrigida (verde) e só avança com 'Conferir próxima'", async () => {
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
    expect(screen.queryByRole("dialog")).toBeNull();
    const fixed = screen.getByText("SILVA");
    expect(fixed.className).toContain("bg-success");
    expect(document.activeElement).toBe(fixed);

    await userEvent.click(screen.getByRole("button", { name: "Conferir próxima" }));
    const next = await screen.findByRole("dialog", { name: "Qual está certo?" });
    expect(within(next).getByRole("button", { name: "acervo" })).toBeInTheDocument();
  });

  it("o quadro só oferece texto: sem 'Manter como no original'", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();

    await userEvent.click(screen.getByRole("button", { name: "Palavra em dúvida: SlLVA" }));
    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).queryByRole("button", { name: /original/i })).toBeNull();
    expect(within(dialog).getAllByRole("button").map((b) => b.getAttribute("aria-label") ?? b.textContent)).toEqual([
      "Fechar", "SlLVA", "SILVA", "Usar o que digitei",
    ]);
  });

  it("palavra corrigida continua clicável e a nova escolha substitui a anterior", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();

    await userEvent.click(screen.getByRole("button", { name: "Palavra em dúvida: SlLVA" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "SlLVA" }));
    expect(screen.getByText("Confira 1 palavra antes de baixar")).toBeInTheDocument();

    const fixed = screen.getByRole("button", { name: "Palavra corrigida: SlLVA — alterar" });
    expect(document.activeElement).toBe(fixed);
    await userEvent.click(fixed);
    const dialog = await screen.findByRole("dialog");
    const current = within(dialog).getByRole("button", { name: "SlLVA" });
    expect(current).toHaveAttribute("aria-pressed", "true");
    expect(within(dialog).getByRole("button", { name: "SILVA" })).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(within(dialog).getByRole("button", { name: "SILVA" }));

    expect(screen.getByRole("button", { name: "Palavra corrigida: SILVA — alterar" }).className).toContain("bg-success");
    expect(screen.getByText("Confira 1 palavra antes de baixar")).toBeInTheDocument();
    const patches = calls.filter((c) => c.init?.method === "PATCH");
    expect(JSON.parse(String(patches.at(-1)?.init?.body))).toEqual({ words: [{ id: "w1", text: "SILVA" }] });
  });

  it("palavra removida vira uma marca clicável, fora do texto copiado", async () => {
    serverFinishing(documentWith([word("w0", "assinado"), word("w1", "|", "uncertain", ["|", ""])]));
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderApp();
    await upload(pngFile());
    await untilResult();

    await userEvent.click(screen.getByRole("button", { name: "Palavra em dúvida: |" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "(nenhuma palavra)" }));

    const mark = screen.getByRole("button", { name: "Palavra removida — alterar" });
    await userEvent.click(screen.getByRole("button", { name: "Copiar texto" }));
    expect(writeText).toHaveBeenCalledWith("assinado");

    await userEvent.click(mark);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "(nenhuma palavra)" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(within(dialog).getByRole("button", { name: "|" }));
    expect(screen.getByRole("button", { name: "Palavra corrigida: | — alterar" })).toBeInTheDocument();
  });

  it("clicar numa palavra visível abre o quadro sem a página rolar", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    const focus = vi.spyOn(HTMLElement.prototype, "focus");

    await userEvent.click(screen.getByRole("button", { name: "Palavra em dúvida: SlLVA" }));
    await screen.findByRole("dialog");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    expect(scroll).not.toHaveBeenCalled();
    // Focar o quadro antes de ele estar no lugar faria a página pular para o topo.
    const dialog = screen.getByRole("dialog");
    const inDialog = focus.mock.calls.filter((_, i) => dialog.contains(focus.mock.contexts[i] as Node));
    expect(inDialog.length).toBeGreaterThan(0);
    expect(inDialog.every(([options]) => options?.preventScroll === true)).toBe(true);
  });

  it("'Conferir próxima' rola até a palavra quando ela está fora da tela", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue(
      { top: 5000, bottom: 5040, left: 0, right: 100, width: 100, height: 40, x: 0, y: 5000, toJSON: () => ({}) },
    );

    await userEvent.click(screen.getByRole("button", { name: "Conferir próxima" }));
    await screen.findByRole("dialog");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    expect(scroll).toHaveBeenCalled();
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
  it("tudo conferido: PDF e Word em destaque primeiro, depois copiar e converter outro", async () => {
    serverFinishing(documentWith([word("w0", "assinado")]));
    renderApp();
    await upload(pngFile());
    await untilResult();

    const actions = within(screen.getAllByRole("status").find((s) => within(s).queryByText("Baixar PDF"))!).getAllByRole("button");
    expect(actions.map((b) => b.textContent)).toEqual(["Baixar PDF", "Baixar Word", "Copiar texto", "Converter outro"]);
    expect(actions[0].className).toContain("bg-primary ");
    expect(actions[2].className).not.toContain("bg-primary ");
  });

  it("com dúvidas, 'Converter outro' não aparece", async () => {
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();

    expect(screen.queryByRole("button", { name: "Converter outro" })).toBeNull();
    expect(screen.getByText("Quase pronto")).toBeInTheDocument();
  });

  it("com o topo na tela, não há barra fixa", async () => {
    stubObserver();
    serverFinishing(DOUBTS);
    renderApp();
    await upload(pngFile());
    await untilResult();
    act(() => setTopVisible(true));

    expect(screen.queryByRole("region", { name: "Andamento da conferência" })).toBeNull();
  });

  it("barra fixa: quantas faltam e, ao resolver a última, 'Tudo conferido' com os downloads", async () => {
    stubObserver();
    serverFinishing(documentWith([word("w0", "assinado"), word("w1", "SlLVA", "uncertain", ["SlLVA", "SILVA"])]));
    renderApp();
    await upload(pngFile());
    await untilResult();
    act(() => setTopVisible(false));

    let bar = screen.getByRole("region", { name: "Andamento da conferência" });
    expect(bar).toHaveTextContent("Falta 1 palavra para conferir");
    await userEvent.click(within(bar).getByRole("button", { name: "Conferir próxima" }));

    const dialog = await screen.findByRole("dialog");
    expect(screen.queryByRole("region", { name: "Andamento da conferência" })).toBeNull();
    await userEvent.click(within(dialog).getByRole("button", { name: "SILVA" }));

    bar = screen.getByRole("region", { name: "Andamento da conferência" });
    expect(bar).toHaveTextContent("Tudo conferido");
    expect(bar).toHaveTextContent("Seu documento está pronto.");
    expect(within(bar).getAllByRole("button").map((b) => b.textContent)).toEqual(["Baixar PDF", "Baixar Word"]);
  });

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
