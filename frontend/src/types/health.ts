export interface ServiceStatus {
  name: string;
  ok: boolean;
  detail: string;
  latency_ms: number | null;
}

export interface Readiness {
  status: "ok" | "degraded";
  app: string;
  version: string;
  environment: string;
  services: ServiceStatus[];
}
