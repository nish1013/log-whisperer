import type { Page } from "@playwright/test";

export const textarea = (page: Page) => page.getByRole("textbox", { name: "Traceback or log" });
export const analyze = (page: Page) => page.getByRole("button", { name: "Analyze" });
export const card = (page: Page, name: string) => page.getByRole("region", { name });

export function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

export async function pickExample(page: Page, id: string) {
  await page.getByRole("combobox", { name: "Load an example" }).click();
  await page.getByRole("option", { name: new RegExp(`^${id}`) }).click();
}

