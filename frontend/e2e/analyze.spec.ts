import { expect, test } from "@playwright/test";
import { fixtureText } from "./fixtureText";
import { analyze, card, pickExample, textarea, watchConsole } from "./helpers";

test("E2 pasted F04 analyzes on Ctrl+Enter", async ({ page }) => {
  await page.goto("/");
  await textarea(page).fill(fixtureText("F04_py3.12"));
  await textarea(page).press("Control+Enter");
  await expect(card(page, "Summary")).toContainText("ConnectionError");
  await expect(card(page, "Culprit")).toContainText("app/clients/http.py:16 in fetch_status");
});

test("E3 pasted secrets are masked before analysis", async ({ page }) => {
  await page.goto("/");
  await textarea(page).fill(fixtureText("F11_secrets"));
  await analyze(page).click();
  await expect(page.getByText("Masked 5 secrets before analysis")).toBeVisible();
});

test("E4 a 502 shows an inline error, keeps the text, and retry succeeds", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/analyze", async (route) => {
    calls += 1;
    if (calls === 1) {
      await route.fulfill({ status: 502, json: { error: "Analysis failed" } });
      return;
    }
    await route.continue();
  });
  await page.goto("/");
  const text = fixtureText("F01_py3.12");
  await textarea(page).fill(text);
  await analyze(page).click();
  await expect(page.getByRole("alert")).toContainText("Analysis failed");
  await expect(textarea(page)).toHaveValue(text);
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(card(page, "Culprit")).toContainText("app/services/user.py");
  expect(calls).toBe(2);
});

test("E5 empty and oversized input disable the button", async ({ page }) => {
  await page.goto("/");
  await expect(analyze(page)).toBeDisabled();
  await textarea(page).fill("a".repeat(204_801));
  await expect(analyze(page)).toBeDisabled();
  const counter = page.getByTestId("byte-counter");
  await expect(counter).toHaveAttribute("data-over", "true");
  await expect(counter).toHaveCSS("color", "oklch(0.577 0.245 27.325)");
  await textarea(page).fill("a".repeat(204_800));
  await expect(analyze(page)).toBeEnabled();
});

test.describe("layout", () => {
  for (const width of [1440, 375]) {
    test(`F01 result at ${width}px`, async ({ page }, testInfo) => {
      const errors = watchConsole(page);
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      expect(errors).toEqual([]);
      await pickExample(page, "F01");
      await analyze(page).click();
      await expect(card(page, "Fix")).toBeVisible();
      await page.waitForLoadState("networkidle");
      const scroll = await page.evaluate(() => ({
        page: document.documentElement.scrollWidth,
        view: window.innerWidth,
      }));
      expect(scroll.page).toBeLessThanOrEqual(scroll.view);
      if (width === 1440) {
        for (const name of ["Culprit", "Fix"]) {
          const box = await card(page, name).boundingBox();
          expect(box, name).not.toBeNull();
          expect((box?.y ?? 0) + (box?.height ?? 0), `${name} bottom`).toBeLessThanOrEqual(900);
        }
      }
      await page.screenshot({
        path: testInfo.outputPath(`analyze-${width}.png`),
        fullPage: true,
      });
      expect(errors).toEqual([]);
    });
  }
});
