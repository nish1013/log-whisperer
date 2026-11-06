import { expect, test } from "@playwright/test";

test("home page reaches the backend through the dev proxy", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "log-whisperer" })).toBeVisible();
  await expect(page.getByTestId("backend-status")).toHaveText("Backend: ok");
});
