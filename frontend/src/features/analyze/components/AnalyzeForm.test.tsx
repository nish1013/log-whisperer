import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";
import { EXAMPLES } from "../examples";
import { AnalyzeForm } from "./AnalyzeForm";

function Harness({ onSubmit = vi.fn(), pending = false, initial = "" }) {
  const [value, setValue] = useState(initial);
  return <AnalyzeForm value={value} pending={pending} onChange={setValue} onSubmit={onSubmit} />;
}

const textarea = () => screen.getByRole("textbox", { name: "Traceback or log" });
const button = () => screen.getByRole("button", { name: "Analyze" });

test("button is disabled for empty and whitespace input", async () => {
  render(<Harness />);
  expect(button()).toBeDisabled();
  await userEvent.type(textarea(), "   ");
  expect(button()).toBeDisabled();
  await userEvent.type(textarea(), "x");
  expect(button()).toBeEnabled();
});

test("counter counts UTF-8 bytes and turns red over the limit", () => {
  const { rerender } = render(<Harness initial={"é".repeat(512)} />);
  expect(screen.getByTestId("byte-counter")).toHaveTextContent("1.0 KB / 200 KB");
  expect(screen.getByTestId("byte-counter")).toHaveAttribute("data-over", "false");
  rerender(<Harness key="over" initial={"a".repeat(204_801)} />);
  expect(screen.getByTestId("byte-counter")).toHaveAttribute("data-over", "true");
  expect(screen.getByTestId("byte-counter")).toHaveClass("text-red-600");
  expect(button()).toBeDisabled();
});

test("exactly the limit is still allowed", () => {
  render(<Harness initial={"a".repeat(204_800)} />);
  expect(screen.getByTestId("byte-counter")).toHaveAttribute("data-over", "false");
  expect(button()).toBeEnabled();
});

test("ctrl and cmd enter submit", async () => {
  const onSubmit = vi.fn();
  render(<Harness onSubmit={onSubmit} initial="boom" />);
  textarea().focus();
  await userEvent.keyboard("{Control>}{Enter}{/Control}");
  await userEvent.keyboard("{Meta>}{Enter}{/Meta}");
  await userEvent.keyboard("{Enter}");
  expect(onSubmit).toHaveBeenCalledTimes(2);
});

test("shortcut does nothing while disabled", async () => {
  const onSubmit = vi.fn();
  render(<Harness onSubmit={onSubmit} initial="boom" pending />);
  textarea().focus();
  await userEvent.keyboard("{Control>}{Enter}{/Control}");
  expect(onSubmit).not.toHaveBeenCalled();
  expect(screen.getByTestId("spinner")).toBeInTheDocument();
  expect(button()).toBeDisabled();
});

test("picking the same example again after an edit reloads it", async () => {
  render(<Harness />);
  const f01 = EXAMPLES.find((e) => e.id === "F01");
  if (!f01) throw new Error("F01 example missing");
  await userEvent.click(screen.getByRole("combobox", { name: "Load an example" }));
  await userEvent.click(await screen.findByRole("option", { name: /^F01/ }));
  expect(textarea()).toHaveValue(f01.text);
  await userEvent.type(textarea(), "edited");
  await userEvent.click(screen.getByRole("combobox", { name: "Load an example" }));
  await userEvent.click(await screen.findByRole("option", { name: /^F01/ }));
  expect(textarea()).toHaveValue(f01.text);
});

test("textarea does not wrap lines", () => {
  render(<Harness />);
  expect(textarea()).toHaveAttribute("wrap", "off");
  expect(textarea()).toHaveAttribute("rows", "14");
});
