const BASE_URL: string = import.meta.env.VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = window.sessionStorage.getItem("securedocs.accessToken");
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the API. Is the backend running on port 8000?");
  }

  const body = await res.json().catch(() => undefined);
  if (!res.ok) {
    throw new ApiError(
      res.status,
      getErrorMessage(body, `Request failed with status ${res.status}`),
      body,
    );
  }
  return body as T;
}

function getErrorMessage(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return fallback;
  }
  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String(item.msg)
          : "Invalid input",
      )
      .join(" ");
  }
  return fallback;
}
