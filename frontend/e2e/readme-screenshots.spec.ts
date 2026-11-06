import path from "node:path";
import { devices, expect, type Page, test } from "@playwright/test";
import { analyze, card, pickExample } from "./helpers";

const OUT = path.resolve(import.meta.dirname, "../../docs/screenshots");

test.skip(!process.env.README_SCREENSHOTS, "set README_SCREENSHOTS=1 to refresh the README images");

async function showF01(page: Page) {
  await page.goto("/");
  await pickExample(page, "F01");
  await analyze(page).click();
  await expect(card(page, "Fix")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(card(page, "Fix").locator(".shiki")).toBeVisible();
}

test("desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await showF01(page);
  await page.screenshot({ path: path.join(OUT, "desktop.png") });
});

test.describe("phone", () => {
  test.use({ viewport: devices["Pixel 7"].viewport, isMobile: true, hasTouch: true });

  test("phone", async ({ page }) => {
    await showF01(page);
    await page.screenshot({ path: path.join(OUT, "phone.png"), fullPage: true });
  });
});
