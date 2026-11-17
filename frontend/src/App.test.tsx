import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const user = {
  id: "c63ebd6a-4a3d-4cb6-9eef-60c588d267a5",
  email: "alex@example.com",
  full_name: "Alex Morgan",
  is_active: true,
  created_at: "2026-11-15T00:00:00Z",
};

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/");
});

describe("application routes and authentication", () => {
  it("redirects the root route to login when signed out", async () => {
    window.history.replaceState({}, "", "/");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });

  it("protects documents and returns there after a successful login", async () => {
    window.history.replaceState({}, "", "/documents");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "valid-token", token_type: "bearer", user }),
      )
      .mockResolvedValueOnce(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: user.email } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Documents" })).toBeInTheDocument();
    expect(window.sessionStorage.getItem("securedocs.accessToken")).toBe("valid-token");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("registers an account and opens the protected dashboard", async () => {
    window.history.replaceState({}, "", "/register");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ access_token: "new-token", token_type: "bearer", user }, 201),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByRole("heading", { name: "Create your workspace" });
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: user.full_name } });
    fireEvent.change(screen.getByLabelText("Organization"), { target: { value: "Example Team" } });
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: user.email } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery staple" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: /Welcome, Alex Morgan/ })).toBeInTheDocument();
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(request.body))).toEqual({
      email: user.email,
      password: "correct horse battery staple",
      full_name: user.full_name,
      organization_name: "Example Team",
    });
    await waitFor(() => expect(window.sessionStorage.getItem("securedocs.accessToken")).toBe("new-token"));
  });

  it("restores a session and sends the stored bearer token to the API", async () => {
    window.history.replaceState({}, "", "/dashboard");
    window.sessionStorage.setItem("securedocs.accessToken", "restored-token");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(user));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("heading", { name: /Welcome, Alex Morgan/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/me",
      expect.anything(),
    );
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(request.headers).get("Authorization")).toBe("Bearer restored-token");
  });
});
