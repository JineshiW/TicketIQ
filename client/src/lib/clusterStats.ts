import type { Cluster, ReviewRecord, ReviewStore } from "@/types";

export interface PatternStats {
  totalPatterns: number;
  pendingReview: number;
  totalApproved: number;
  totalRejected: number;
}

export function computeStats(reviews: ReviewRecord[]): PatternStats {
  return {
    totalPatterns: reviews.length,
    pendingReview: reviews.filter((r) => r.status === "pending").length,
    totalApproved: reviews.filter((r) => r.status === "approved").length,
    totalRejected: reviews.filter((r) => r.status === "rejected").length,
  };
}

export function reviewsToList(store: ReviewStore | null): ReviewRecord[] {
  if (!store) return [];
  return Object.values(store).sort((a, b) => b.size - a.size);
}

/** Counts of tickets per cluster type, for the donut chart. */
export function countByType(clusters: Cluster[]): { label: string; value: number }[] {
  const counts = new Map<string, number>();
  clusters
    .filter((c) => c.cluster_id !== -1)
    .forEach((c) => counts.set(c.type, (counts.get(c.type) ?? 0) + c.size));
  return [...counts.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

const BUCKETS: { label: string; test: (n: number) => boolean }[] = [
  { label: "<5", test: (n) => n < 5 },
  { label: "5-10", test: (n) => n >= 5 && n <= 10 },
  { label: "11-20", test: (n) => n >= 11 && n <= 20 },
  { label: "21-50", test: (n) => n >= 21 && n <= 50 },
  { label: "50+", test: (n) => n > 50 },
];

/** Cluster size distribution histogram. */
export function sizeDistribution(clusters: Cluster[]): { label: string; value: number }[] {
  const real = clusters.filter((c) => c.cluster_id !== -1);
  return BUCKETS.map((b) => ({
    label: b.label,
    value: real.filter((c) => b.test(c.size)).length,
  }));
}
