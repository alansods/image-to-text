import { expect, test } from "@playwright/test";

test("a página inicial abre em português quando o navegador está em português", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
  await expect(page.getByRole("heading", { level: 1, name: "Transforme imagens em texto" })).toBeVisible();
});

test("endereço inexistente mostra 'Página não encontrada' e volta ao início", async ({ page }) => {
  await page.goto("/qualquer-coisa");

  await expect(page.getByRole("heading", { name: "Página não encontrada" })).toBeVisible();
  await page.getByRole("link", { name: "Voltar ao início" }).click();
  await expect(page).toHaveURL("/");
});

test("o seletor PT | EN troca a interface na hora", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "EN", exact: true }).click();

  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Turn images into text");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("sem rolagem horizontal e alvos de toque de 44 px no celular", async ({ page, isMobile }) => {
  test.skip(!isMobile, "só no celular");
  await page.goto("/");

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  for (const name of ["Tirar foto", "Escolher arquivo", "PT", "EN"]) {
    const box = await page.getByRole("button", { name, exact: true }).first().boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
  }
});
