import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { StatCard } from "@/components/StatCard";
import {
  ErrorState,
  Loading,
} from "@/components/States";

import { BarChart } from "@/components/charts/BarChart";
import { ClusterScatter } from "@/components/charts/ClusterScatter";
import { DonutChart } from "@/components/charts/DonutChart";

import { AgentReviewPanel } from "@/features/patterns/components/AgentReviewPanel";
import { AlgorithmComparisonPanel } from "@/features/patterns/components/AlgorithmComparison";
import { ReviewTable } from "@/features/patterns/components/ReviewTable";

import { usePatterns } from "@/features/patterns/usePatterns";

import {
  computeStats,
  countByType,
  sizeDistribution,
} from "@/lib/clusterStats";

const PAGE_SIZE = 10;

/*
 * ------------------------------------------------------------
 * Countdown formatting
 * ------------------------------------------------------------
 */

function formatCountdown(
  milliseconds: number,
): string {
  if (milliseconds <= 0) {
    return "00:00";
  }

  const totalSeconds =
    Math.floor(milliseconds / 1000);

  const hours =
    Math.floor(totalSeconds / 3600);

  const minutes =
    Math.floor(
      (totalSeconds % 3600) / 60,
    );

  const seconds =
    totalSeconds % 60;

  if (hours > 0) {
    return `${hours
      .toString()
      .padStart(2, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${seconds
      .toString()
      .padStart(2, "0")}`;
  }

  return `${minutes
    .toString()
    .padStart(2, "0")}:${seconds
    .toString()
    .padStart(2, "0")}`;
}

/*
 * ------------------------------------------------------------
 * Page
 * ------------------------------------------------------------
 */

export function RecurringPatternsPage() {
  const {
    clusters,
    reviews,
    reviewList,
    decide,
    agentCheck,
    agentResume,
    refreshAll,
    schedule,
  } = usePatterns();

  const [
    visibleCount,
    setVisibleCount,
  ] = useState(PAGE_SIZE);

  /*
   * Current time used only for the visual countdown.
   *
   * This does NOT trigger clustering.
   */
  const [now, setNow] = useState(
    () => Date.now(),
  );

  /*
   * Update the countdown every second.
   */
  useEffect(() => {
    const interval =
      window.setInterval(() => {
        setNow(Date.now());
      }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  const stats =
    computeStats(reviewList);

  const clusterList =
    clusters.data?.clusters ?? [];

  const visibleReviews =
    reviewList.slice(
      0,
      visibleCount,
    );

  const hasMore =
    visibleCount <
    reviewList.length;

  /*
   * Calculate the actual time remaining until the backend's
   * next scheduled recurring-pattern check.
   */
  const nextRunMilliseconds =
    useMemo(() => {
      if (!schedule?.next_run_time) {
        return null;
      }

      const nextRun =
        Date.parse(
          schedule.next_run_time,
        );

      if (Number.isNaN(nextRun)) {
        return null;
      }

      return Math.max(
        0,
        nextRun - now,
      );
    }, [
      schedule?.next_run_time,
      now,
    ]);

  const countdownText =
    nextRunMilliseconds === null
      ? "--:--"
      : formatCountdown(
          nextRunMilliseconds,
        );

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Recurring Patterns</h1>

          <p>
            Semantic grouping of similar support
            tickets, gated by human review.
          </p>
        </div>

        <div className="row">
          <Badge>
            ⟳ Auto-checked hourly
          </Badge>

          <span
            className="small mono dim"
            title="Time remaining until the next automatic recurring-pattern check"
          >
            Next check in {countdownText}
          </span>

          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() =>
              void refreshAll()
            }
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid--3">
        <StatCard
          label="Total patterns"
          value={stats.totalPatterns}
          icon="⁂"
        />

        <StatCard
          label="Pending review"
          value={stats.pendingReview}
          accent
          icon="⌛"
        />

        <StatCard
          label="Total approved"
          value={stats.totalApproved}
          icon="✓"
        />
      </div>

      {/* --------------------------------------------------
       * 3D Cluster Visualization
       * ------------------------------------------------ */}
      <Card
        title="Cluster Visualization"
        subtitle="Interactive 3D constellation of semantically related tickets, grouped by detected pattern type."
        action={
          clusters.data?.best_algorithm ? (
            <Badge
              tone="primary"
              upper
            >
              Best:{" "}
              {
                clusters.data
                  .best_algorithm
              }
            </Badge>
          ) : null
        }
      >
        {clusters.loading ? (
          <Loading label="Clustering tickets…" />
        ) : null}

        {!clusters.loading &&
        clusters.error ? (
          <ErrorState
            message={
              clusters.error
            }
            onRetry={() =>
              void clusters.refetch()
            }
          />
        ) : null}

        {!clusters.loading &&
        !clusters.error &&
        clusters.data?.error ? (
          <ErrorState
            message={
              clusters.data.error
            }
          />
        ) : null}

        {!clusters.loading &&
        !clusters.error &&
        !clusters.data?.error &&
        clusterList.length > 0 ? (
          <ClusterScatter
            clusters={
              clusterList
            }
          />
        ) : null}
      </Card>

      {/* --------------------------------------------------
       * Pattern statistics
       * ------------------------------------------------ */}
      <div className="grid grid--2">
        <Card title="Patterns by Type">
          {clusterList.length ? (
            <DonutChart
              data={countByType(
                clusterList,
              )}
            />
          ) : (
            <p className="small dim">
              No clusters yet.
            </p>
          )}
        </Card>

        <Card title="Cluster Size Distribution">
          {clusterList.length ? (
            <>
              <BarChart
                data={sizeDistribution(
                  clusterList,
                )}
              />

              <p
                className="small dim"
                style={{
                  textAlign: "center",
                }}
              >
                Total:{" "}
                {
                  clusterList.filter(
                    (c) =>
                      c.cluster_id !==
                      -1,
                  ).length
                }{" "}
                clusters
              </p>
            </>
          ) : (
            <p className="small dim">
              No clusters yet.
            </p>
          )}
        </Card>
      </div>

      {/* --------------------------------------------------
       * Algorithm comparison
       * ------------------------------------------------ */}
      <Card
        title="Algorithm Comparison"
        subtitle="Chosen empirically by silhouette score."
        flush
      >
        {clusters.data ? (
          <AlgorithmComparisonPanel
            comparison={
              clusters.data
                .comparison
            }
            best={
              clusters.data
                .best_algorithm
            }
          />
        ) : (
          <div className="card__body">
            <p className="small dim">
              Waiting for clustering
              results…
            </p>
          </div>
        )}
      </Card>

      {/* --------------------------------------------------
       * Agentic pattern check
       * ------------------------------------------------ */}
      <Card title="Agentic Pattern Check">
        <AgentReviewPanel
          check={agentCheck}
          resume={
            agentResume
          }
        />
      </Card>

      {/* --------------------------------------------------
       * Human review
       * ------------------------------------------------ */}
      <Card
        title="Clusters Awaiting Review"
        subtitle={
          reviewList.length > 0
            ? `Showing ${visibleReviews.length} of ${reviewList.length}`
            : undefined
        }
        flush
      >
        {reviews.loading ? (
          <Loading />
        ) : null}

        {!reviews.loading &&
        reviews.error ? (
          <ErrorState
            message={
              reviews.error
            }
            onRetry={() =>
              void reviews.refetch()
            }
          />
        ) : null}

        {!reviews.loading &&
        !reviews.error ? (
          <>
            <ReviewTable
              reviews={
                visibleReviews
              }
              busy={
                decide.loading
              }
              onDecide={(
                signature,
                status,
              ) =>
                void decide.run(
                  signature,
                  status,
                )
              }
            />

            {hasMore ? (
              <div
                className="row"
                style={{
                  justifyContent:
                    "center",
                  padding:
                    "16px 0",
                }}
              >
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  onClick={() =>
                    setVisibleCount(
                      (count) =>
                        count +
                        PAGE_SIZE,
                    )
                  }
                >
                  Load more
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </Card>
    </div>
  );
}