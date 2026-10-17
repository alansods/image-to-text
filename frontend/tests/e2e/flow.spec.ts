// Fluxo completo contra o backend de verdade (docker compose up): enviar → progresso →
// conferir as dúvidas → baixar Word e PDF (spec site-interface, review-editor, document-export).
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const FIXTURE = join(__dirname, "..", "..", "..", "backend", "tests", "fixtures", "precision", "contrato_foto", "input.jpg");

test.describe.configure({ mode: "serial", timeout: 300_000 });

test.beforeAll(async ({ request }) => {
  const health = await request.get(`${API}/health`).catch(() => null);
  test.skip(!health?.ok(), "backend fora do ar: rode `docker compose up`");
});

function contrato(): string {
  const file = join(mkdtempSync(join(tmpdir(), "itt-")), "contrato.jpg");
  copyFileSync(FIXTURE, file);
  return file;
}

const gate = (page: Page) => page.getByText(/^Confira \d+ palavras? antes de baixar$/);

/** Espera a escolha ser gravada: o contador muda (ou some, com "Tudo conferido"). */
async function choiceSaved(page: Page, before: string) {
  await expect(page.getByText(before, { exact: true })).toBeHidden();
}

async function resolveAllDoubts(page: Page) {
  while (await gate(page).isVisible()) {
    const before = (await gate(page).textContent()) ?? "";
    await page.getByRole("button", { name: "Conferir próxima" }).click();
    const dialog = page.getByRole("dialog", { name: "Qual está certo?" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("img")).toBeVisible();
    await dialog.locator("button[data-option]").first().click();
    await choiceSaved(page, before);
  }
}

test("enviar, conferir e baixar Word e PDF com o nome do arquivo", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(contrato());

  await expect(page.getByText("Lendo seu documento…")).toBeVisible();
  await expect(page.getByRole("article", { name: "Página 1" })).toBeVisible({ timeout: 240_000 });
  await expect(page.getByText("PÁGINA 1 DE 1", { exact: false })).toBeVisible();
  await expect(page.getByText(/CONTRATO DE PRESTAÇÃO/)).toBeVisible();

  await resolveAllDoubts(page);
  await expect(page.getByText("Tudo conferido")).toBeVisible();

  // Trocar a escolha: a palavra corrigida reabre o quadro, com a escolha atual marcada. A foto
  // de teste pode sair sem dúvidas; aí não há o que trocar (coberto nos testes de unidade).
  const fixed = page.getByRole("button", { name: /— alterar$/ }).first();
  if ((await fixed.count()) > 0) {
    await fixed.click();
    const dialog = page.getByRole("dialog", { name: "Qual está certo?" });
    await expect(dialog.locator("button[aria-pressed='true']")).toHaveCount(1);
    await dialog.locator("button[aria-pressed='false']").first().click();
    await expect(dialog).toBeHidden();
    await expect(page.getByText("Tudo conferido")).toBeVisible();
  }

  const word = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar Word" }).click();
  expect((await word).suggestedFilename()).toBe("contrato.docx");

  const pdf = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar PDF" }).click();
  expect((await pdf).suggestedFilename()).toBe("contrato.pdf");

  await page.getByRole("button", { name: "Converter outro" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Transforme imagens em texto");
});

test("tudo só com o teclado", async ({ page, isMobile }) => {
  test.skip(isMobile, "teclado: desktop");
  await page.goto("/");

  const chooser = page.waitForEvent("filechooser");
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => document.activeElement?.textContent ?? "");
    if (focused.includes("Escolher arquivo")) break;
  }
  await page.keyboard.press("Enter");
  await (await chooser).setFiles(contrato());
  await expect(page.getByRole("article", { name: "Página 1" })).toBeVisible({ timeout: 240_000 });

  while (await gate(page).isVisible()) {
    const before = (await gate(page).textContent()) ?? "";
    await page.getByRole("button", { name: "Conferir próxima" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Enter"); // a primeira opção já recebe o foco
    await choiceSaved(page, before);
  }
  await expect(page.getByText("Tudo conferido")).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar PDF" }).focus();
  await page.keyboard.press("Enter");
  expect((await download).suggestedFilename()).toBe("contrato.pdf");
});
