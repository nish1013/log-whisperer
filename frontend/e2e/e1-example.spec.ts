import { expect, test } from "@playwright/test";
import { fixtureText } from "./fixtureText";
import { analyze, card, pickExample, textarea, watchConsole } from "./helpers";

test.use({ video: "on" });

test("E1 example F01 shows culprit and fix, and copies the snippet", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const errors = watchConsole(page);
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route("**/api/analyze", async (route) => {
    await held;
    await route.continue();
  });
  await page.goto("/");
  await pickExample(page, "F01");
  await expect(textarea(page)).toHaveValue(fixtureText("F01_py3.12"));
  await analyze(page).click();
  await expect(page.getByTestId("spinner")).toBeVisible();
  await expect(analyze(page)).toBeDisabled();
  release();
  await expect(card(page, "Summary")).toBeVisible();
  await expect(card(page, "Culprit")).toContainText("app/services/user.py");
  await expect(card(page, "Fix")).toBeVisible();
  await expect(page.getByTestId("spinner")).toHaveCount(0);
  await page.getByRole("button", { name: "Copy code" }).click();
  const clipboard = await page.evaluate(() => navigator.clipboard.readText());
  expect(clipboard).toBe('return {"name": user["name"], "email": user["email"]}');
  expect(errors).toEqual([]);
});
