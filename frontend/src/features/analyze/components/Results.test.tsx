import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { analysis } from "../testData";
import { Results } from "./Results";

const card = (name: string) => screen.getByRole("region", { name });

test("cards render in order with the culprit location", () => {
  render(<Results result={analysis()} />);
  const titles = screen.getAllByRole("heading").map((h) => h.textContent);
  expect(titles).toEqual(["Summary", "Culprit", "Fix", "Explanation"]);
  expect(within(card("Culprit")).getByText("/srv/app/services/user.py:2 in get_profile")).toBeInTheDocument();
  expect(within(card("Fix")).getAllByRole("listitem")).toHaveLength(2);
});

test.each([
  ["high", "bg-green-100"],
  ["medium", "bg-amber-100"],
  ["low", "bg-slate-200"],
] as const)("%s confidence badge colour", (confidence, className) => {
  const base = analysis();
  render(<Results result={{ ...base, diagnosis: { ...base.diagnosis, confidence } }} />);
  expect(screen.getByText(`${confidence} confidence`)).toHaveClass(className);
});

test("null culprit shows a fallback line", () => {
  const base = analysis();
  render(<Results result={{ ...base, diagnosis: { ...base.diagnosis, culprit: null } }} />);
  expect(within(card("Culprit")).getByText("No specific line identified")).toBeInTheDocument();
});

test("notices show redactions and truncation", () => {
  render(<Results result={analysis({ redaction_count: 5, truncated: true })} />);
  expect(screen.getByText("Masked 5 secrets before analysis")).toBeInTheDocument();
  expect(screen.getByText("Log was truncated to the relevant parts")).toBeInTheDocument();
});

test("one redaction uses the singular", () => {
  render(<Results result={analysis({ redaction_count: 1 })} />);
  expect(screen.getByText("Masked 1 secret before analysis")).toBeInTheDocument();
});

test("no notices when nothing was masked or cut", () => {
  render(<Results result={analysis()} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("collapsibles open on click", async () => {
  render(<Results result={analysis()} />);
  expect(screen.queryByText("The caller dropped the key.")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Other possible causes" }));
  expect(screen.getByText("The caller dropped the key.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "What to check next" }));
  expect(screen.getByText("Check the request payload.")).toBeInTheDocument();
});

test("empty lists and missing snippet render nothing", () => {
  const base = analysis();
  const diagnosis = {
    ...base.diagnosis,
    alternative_causes: [],
    follow_up_checks: [],
    fix: { steps: ["x"], code_snippet: null, language: null },
  };
  render(<Results result={{ ...base, diagnosis }} />);
  expect(screen.queryByRole("button", { name: "Other possible causes" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Copy code" })).not.toBeInTheDocument();
});
