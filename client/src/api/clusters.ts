import { request } from "./client";

import type {
  ClusterResponse,
  PatternScheduleResponse,
  ReviewStatus,
  ReviewStore,
} from "@/types";

/**
 * GET /clusters
 *
 * Explicitly loads/recomputes the recurring-pattern view.
 */
export function getClusters() {
  return request<ClusterResponse>("/clusters");
}

/**
 * GET /clusters/reviews
 *
 * Returns the persistent recurring-pattern review store.
 */
export function getReviews() {
  return request<ReviewStore>("/clusters/reviews");
}

/**
 * GET /clusters/schedule
 *
 * Returns information about the backend's hourly recurring-pattern
 * scheduler.
 *
 * This endpoint is metadata-only and does NOT trigger clustering.
 */
export function getSchedule() {
  return request<PatternScheduleResponse>(
    "/clusters/schedule",
  );
}

/**
 * POST /clusters/reviews/{signature}/decide?decision=...
 *
 * `decision` is a query parameter on the server.
 */
export function decideReview(
  signature: string,
  decision: ReviewStatus,
) {
  return request<{
    signature: string;
    status: ReviewStatus;
  }>(
    "/clusters/reviews/decide",
    {
      method: "POST",
      query: { signature, decision },
    },
  );
}