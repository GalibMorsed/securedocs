import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StatusPage } from "./StatusPage";
import { ThemeProvider } from "../theme/ThemeProvider";

const readiness = (ok: boolean) => ({
  status: ok ? "ok" : "degraded",
  app: "SecureDocs",
  version: "0.1.0",
  environment: "development",
  services: [
    { name: "PostgreSQL", ok: true, detail: "PostgreSQL 17.2", latency_ms: 2.1 },
    { name: "Redis", ok, detail: ok ? "Redis 7.4" : "ConnectionError: refused", latency_ms: 1.0 },
  ],
});

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("StatusPage", () => {
  it("shows connected services", async () => {
    mockFetch(200, readiness(true));
    render(<ThemeProvider><StatusPage /></ThemeProvider>);
    await waitFor(() =>
      expect(screen.getByText("All services are connected")).toBeInTheDocument(),
    );
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
  });

  it("shows a failing dependency from a 503 response", async () => {
    mockFetch(503, readiness(false));
    render(<ThemeProvider><StatusPage /></ThemeProvider>);
    await waitFor(() =>
      expect(screen.getByText("Some services are unreachable")).toBeInTheDocument(),
    );
    expect(screen.getByText("Unreachable")).toBeInTheDocument();
  });

  it("shows an error when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));
    render(<ThemeProvider><StatusPage /></ThemeProvider>);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Cannot reach the API/));
  });
});
