import type { ServiceHealth } from "@/features/dashboard/types";

export type Runtime = string;

export interface ServiceMetadata {
  runtime: Runtime;
  team: string;
  tier: number;
  region: string;
  nodePool: string;
  node: string;
  replicas: string;
}

export interface ActivityLogEntry {
  id: string;
  message: string;
  timestamp: string;
}

/** The table row shape: live telemetry joined with registry metadata. */
export type ServiceRow = ServiceHealth & ServiceMetadata;
