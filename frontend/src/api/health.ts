import type { Readiness } from "../types/health";
import { ApiError, apiRequest } from "./client";

/**
 * The backend answers 503 with a full body when a dependency is down.
 * That body is still useful to show, so it is returned instead of thrown.
 */
export async function fetchReadiness(): Promise<Readiness> {
  try {
    return await apiRequest<Readiness>("/health/services");
  } catch (err) {
    if (err instanceof ApiError && err.status === 503 && err.body) {
      return err.body as Readiness;
    }
    throw err;
  }
}
