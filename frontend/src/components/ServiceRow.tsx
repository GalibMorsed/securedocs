import type { ServiceStatus } from "../types/health";

export function ServiceRow({ service }: { service: ServiceStatus }) {
  return (
    <li className="flex items-center gap-4 py-4">
      <span
        aria-hidden="true"
        className={`h-2.5 w-2.5 shrink-0 rounded-full ${service.ok ? "bg-ok" : "bg-fail"}`}
      />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{service.name}</p>
        <p className="truncate text-sm text-muted">{service.detail}</p>
      </div>
      <div className="text-right text-sm">
        <p className={service.ok ? "text-ok" : "text-fail"}>
          {service.ok ? "Connected" : "Unreachable"}
        </p>
        {service.latency_ms !== null && (
          <p className="text-muted">{service.latency_ms} ms</p>
        )}
      </div>
    </li>
  );
}
