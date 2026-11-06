import { devices, expect, test } from "@playwright/test";
import { fixtureText } from "./fixtureText";
import { analyze, card, pickExample, textarea, watchConsole } from "./helpers";

test.use({ ...devices["Pixel 7"] });

const MIN_TAP = 44;

test("phone: the full flow fits the screen and works by touch", async ({ page }, testInfo) => {
  const errors = watchConsole(page);
  await page.goto("/");
  const fontSize = await textarea(page).evaluate((el) => getComputedStyle(el).fontSize);
  expect(parseFloat(fontSize), "textarea font size, below 16px zooms on focus").toBeGreaterThanOrEqual(16);

  await pickExample(page, "F01");
  await expect(textarea(page)).toHaveValue(fixtureText("F01_py3.12"));
  await analyze(page).tap();
  await expect(card(page, "Fix")).toBeVisible();
  await page.waitForLoadState("networkidle");

  for (const name of ["Analyze", "Copy code"]) {
    const box = await page.getByRole("button", { name }).boundingBox();
    expect(box?.height ?? 0, `${name} tap height`).toBeGreaterThanOrEqual(MIN_TAP);
  }
  const select = await page.getByRole("combobox", { name: "Load an example" }).boundingBox();
  expect(select?.height ?? 0, "example picker tap height").toBeGreaterThanOrEqual(MIN_TAP);

  const copy = await page.getByRole("button", { name: "Copy code" }).boundingBox();
  const code = await card(page, "Fix").locator("pre").first().boundingBox();
  expect(copy && code, "copy button and code").toBeTruthy();
  if (copy && code) {
    const overlaps = copy.y < code.y + code.height && code.y < copy.y + copy.height;
    expect(overlaps, "copy button overlaps the code").toBe(false);
  }

  const width = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth,
    view: window.innerWidth,
  }));
  expect(width.page).toBeLessThanOrEqual(width.view);
  await page.screenshot({ path: testInfo.outputPath("analyze-phone.png"), fullPage: true });
  expect(errors).toEqual([]);
});
