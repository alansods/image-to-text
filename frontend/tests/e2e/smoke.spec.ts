import { expect, test } from "@playwright/test";

test("a página inicial abre em português", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
  await expect(page.getByRole("heading", { level: 1, name: "image-to-text" })).toBeVisible();
});
