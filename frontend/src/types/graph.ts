/** Interaction graph types (B4). Every node/edge carries a source ID. */

import type { MetaInfo } from "./dashboard";

export type GraphNodeType = "agent" | "tool" | "model" | "invocation" | "external_resource";
export type GraphEdgeType = "message" | "invocation" | "result";

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  risk: string;
  timestamp?: string | null;
  source_id: string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: GraphEdgeType;
  message_id?: string | null;
  risk: string;
  timestamp?: string | null;
  source_id: string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface CandidatePath {
  id: string;
  label: string;
  node_ids: string[];
  edge_ids: string[];
  evidence_refs: string[];
  risk: string;
}

export interface GraphResponse {
  meta: MetaInfo;
  graph: {
    scenario_id?: string | null;
    nodes: GraphNode[];
    edges: GraphEdge[];
    candidate_paths: CandidatePath[];
    not_provable?: string[];
    /** B13 upstream C1 self-reported availability (absent in demo fixtures) */
    upstream_available?: boolean;
    upstream_data_status?: string | null;
  };
}
