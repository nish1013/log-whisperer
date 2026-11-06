import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import { renderWithQuery } from "@/test/render";
import { analysis } from "../testData";
import { AnalyzePage } from "./AnalyzePage";

afterEach(() => vi.unstubAllGlobals());

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function sentBody(fetch: ReturnType<typeof vi.fn>, call: number): unknown {
  const init = fetch.mock.calls[call]?.[1] as RequestInit | undefined;
  return JSON.parse(String(init?.body));
}

async function submit(text: string) {
  await userEvent.type(screen.getByRole("textbox", { name: "Traceback or log" }), text);
  await userEvent.click(screen.getByRole("button", { name: "Analyze" }));
}

test("success shows the results and posts the input", async () => {
  const fetch = vi.fn().mockResolvedValue(json(200, analysis()));
  vi.stubGlobal("fetch", fetch);
  renderWithQuery(<AnalyzePage />);
  expect(screen.getByText(/appear here/)).toBeInTheDocument();
  await submit("boom");
  expect(await screen.findByTestId("results")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/analyze", expect.objectContaining({ method: "POST" }));
  expect(sentBody(fetch, 0)).toEqual({ input: "boom" });
});

test("pending state shows the skeleton", async () => {
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => undefined)));
  renderWithQuery(<AnalyzePage />);
  await submit("boom");
  expect(screen.getByTestId("results-skeleton")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analyze" })).toBeDisabled();
});

test("server error message shows inline, keeps the text, and retry resends", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(json(502, { error: "Analysis failed" }))
    .mockResolvedValueOnce(json(200, analysis()));
  vi.stubGlobal("fetch", fetch);
  renderWithQuery(<AnalyzePage />);
  await submit("first");
  expect(await screen.findByRole("alert")).toHaveTextContent("Analysis failed");
  expect(screen.getByRole("textbox", { name: "Traceback or log" })).toHaveValue("first");
  await userEvent.type(screen.getByRole("textbox", { name: "Traceback or log" }), " more");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByTestId("results")).toBeInTheDocument();
  expect(sentBody(fetch, 1)).toEqual({ input: "first" });
});

test("network failure says the server is unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  renderWithQuery(<AnalyzePage />);
  await submit("boom");
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server.");
});

test("error body without error field shows the status", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>", { status: 504 })));
  renderWithQuery(<AnalyzePage />);
  await submit("boom");
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Request failed (504)"));
});
