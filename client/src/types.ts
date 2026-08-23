/** Shared API contract types — mirrors the FastAPI/Pydantic models exactly. */

export interface Ticket {
  id: string;
  title: string;
  description: string;
  resolution?: string;
  source_repo?: string;
}

export interface SimilarTicketResult {
  title: string;
  resolution: string;
  similarity_score: number;
}

export interface SimilarTicketsResponse {
  similar_tickets: SimilarTicketResult[];
  ai_summary: string;
  normalized_text: string;
  quality: string;
}

export interface BatchSimilarResult {
  ticket_id: string;
  ticket_title: string;
  result: SimilarTicketsResponse;
}

export interface BatchSimilarResponse {
  results: BatchSimilarResult[];
}

export interface AddTicketResponse {
  message?: string;
  added?: number;
  skipped?: number;
  [key: string]: unknown;
}

export interface ClusterTicket {
  id: string;
  title: string;
  resolution: string;
  source_repo?: string;
  x: number;
  y: number;
}

export interface Cluster {
  cluster_id: number;
  cluster_key: string;
  repository: string;
  local_cluster_id?: number;
  signature?: string;
  summary: string;
  type: string;
  status: ReviewStatus | string;
  size: number;
  first_seen?: string;
  last_seen?: string;
  tickets: ClusterTicket[];
}

export interface AlgorithmComparison {
  [algorithm: string]: { silhouette: number; n_clusters: number };
}

export interface ClusterResponse {
  clusters: Cluster[];
  comparison: AlgorithmComparison;
  best_algorithm: string | null;
  error?: string;
}

export interface PatternScheduleResponse {
  running: boolean;
  interval_hours: number;
  next_run_time: string | null;
  last_run_time: string | null;
}

export type ReviewStatus = "pending" | "approved" | "rejected";

export interface ReviewRecord {
  signature: string;
  repository: string;
  summary: string;
  type: string;
  status: ReviewStatus;
  size: number;
  ticket_ids: string[];
  first_seen: string;
  last_seen: string;
  decided_at?: string;
}

/** GET /clusters/reviews returns a dict keyed by signature. */
export type ReviewStore = Record<string, ReviewRecord>;

export interface PatternCheckResponse {
  thread_id: string | null;
  findings?: string;
  question?: string;
  message?: string;
}

export interface ResumeResponse {
  thread_id: string;
  final_result: string;
}
