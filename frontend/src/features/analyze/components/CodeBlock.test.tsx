import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { CodeBlock } from "./CodeBlock";

test("python is highlighted with Shiki", async () => {
  render(<CodeBlock code={"def f():\n    return 1"} language="python" />);
  const block = await screen.findByTestId("code-highlighted", {}, { timeout: 5000 });
  expect(block.querySelector("pre.shiki")).not.toBeNull();
  expect(block).toHaveTextContent("def f():");
});

test("unknown language renders plain text", async () => {
  render(<CodeBlock code="SELECT 1" language="not-a-language" />);
  expect(screen.getByTestId("code-plain")).toHaveTextContent("SELECT 1");
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(screen.queryByTestId("code-highlighted")).not.toBeInTheDocument();
});

test("null language renders plain text", () => {
  render(<CodeBlock code="x = 1" language={null} />);
  expect(screen.getByTestId("code-plain")).toHaveTextContent("x = 1");
});

test.each(["python", null])("script tags are escaped (%s)", async (language) => {
  const code = '<script>window.__pwned = true</script><img src=x onerror="window.__pwned=true">';
  const { container } = render(<CodeBlock code={code} language={language} />);
  if (language) await screen.findByTestId("code-highlighted", {}, { timeout: 5000 });
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("img")).toBeNull();
  expect(container).toHaveTextContent("<script>window.__pwned = true</script>");
});

test("copy puts the snippet on the clipboard", async () => {
  const user = userEvent.setup();
  const writeText = vi.spyOn(navigator.clipboard, "writeText");
  render(<CodeBlock code="print('hi')" language={null} />);
  await user.click(screen.getByRole("button", { name: "Copy code" }));
  expect(writeText).toHaveBeenCalledWith("print('hi')");
  await waitFor(() => expect(screen.getByText("Copied")).toBeInTheDocument());
});
