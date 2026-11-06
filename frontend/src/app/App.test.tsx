import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { App } from "./App";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("shows backend ok when /healthz answers", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"status":"ok"}', { status: 200 })));
  renderApp();
  expect(await screen.findByText("Backend: ok")).toBeInTheDocument();
});

test("shows unreachable when the request fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
  renderApp();
  expect(await screen.findByText("Backend: unreachable")).toBeInTheDocument();
});
