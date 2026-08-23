import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { agentApi, clustersApi } from "@/api";
import { reviewsToList } from "@/lib/clusterStats";
import type {
  ClusterResponse,
  PatternScheduleResponse,
  ReviewStatus,
  ReviewStore,
} from "@/types";

/*
 * ------------------------------------------------------------
 * Persistent client-side cache
 * ------------------------------------------------------------
 *
 * The Recurring Patterns page is unmounted when the user changes
 * tabs/routes.
 *
 * We deliberately keep the most recently loaded data at module
 * level so navigating away from /patterns does NOT immediately
 * trigger another clustering request when the user comes back.
 *
 * The backend remains the source of truth.
 * The cache is only a UI navigation cache.
 */

interface PatternsCache {
  clusters: ClusterResponse | null;
  reviews: ReviewStore | null;

  /*
   * Time when the client last successfully loaded the data.
   *
   * This lets us compare our cached data against the backend
   * scheduler's last_run_time.
   */
  cachedAt: number | null;

  /*
   * Last scheduler run that the client has already incorporated.
   */
  schedulerLastRun: number | null;
}

const cache: PatternsCache = {
  clusters: null,
  reviews: null,
  cachedAt: null,
  schedulerLastRun: null,
};

/*
 * ------------------------------------------------------------
 * Small helpers
 * ------------------------------------------------------------
 */

function parseServerTime(value?: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsed = Date.parse(value);

  return Number.isNaN(parsed) ? null : parsed;
}

function hasCachedData(): boolean {
  return (
    cache.clusters !== null &&
    cache.reviews !== null &&
    cache.cachedAt !== null
  );
}

/*
 * ------------------------------------------------------------
 * Hook
 * ------------------------------------------------------------
 */

export function usePatterns() {
  /*
   * Initialise React state from the persistent module cache.
   *
   * If the user has already visited this page during the current
   * browser session, the previous data is immediately displayed.
   */
  const [clustersData, setClustersData] =
    useState<ClusterResponse | null>(
      cache.clusters,
    );

  const [reviewsData, setReviewsData] =
    useState<ReviewStore | null>(
      cache.reviews,
    );

  const [clustersLoading, setClustersLoading] =
    useState(!hasCachedData());

  const [reviewsLoading, setReviewsLoading] =
    useState(!hasCachedData());

  const [clustersError, setClustersError] =
    useState<string | null>(null);

  const [reviewsError, setReviewsError] =
    useState<string | null>(null);

  /*
   * Hourly scheduler information.
   */
  const [schedule, setSchedule] =
    useState<PatternScheduleResponse | null>(
      null,
    );

  /*
   * Prevent state updates after this particular component
   * instance has been unmounted.
   */
  const mountedRef = useRef(false);

  /*
   * Prevent multiple automatic refreshes from being started
   * simultaneously.
   */
  const refreshingRef = useRef(false);

  const [deciding, setDeciding] = useState(false);

  /*
   * ----------------------------------------------------------
   * Load actual pattern data
   * ----------------------------------------------------------
   */

  const loadPatterns = useCallback(
    async (
      force = false,
    ): Promise<boolean> => {
      if (refreshingRef.current) {
        return false;
      }

      /*
       * If we already have cached data and this is not a forced
       * refresh, do NOT run clustering again.
       */
      if (!force && hasCachedData()) {
        if (mountedRef.current) {
          setClustersData(cache.clusters);
          setReviewsData(cache.reviews);
          setClustersLoading(false);
          setReviewsLoading(false);
        }

        return true;
      }

      refreshingRef.current = true;

      if (mountedRef.current) {
        setClustersLoading(true);
        setReviewsLoading(true);

        setClustersError(null);
        setReviewsError(null);
      }

      try {
        /*
         * Load both resources together.
         *
         * /clusters performs clustering/reconciliation.
         * /clusters/reviews returns the persistent review store.
         */
        const [clustersResult, reviewsResult] =
          await Promise.all([
            clustersApi.getClusters(),
            clustersApi.getReviews(),
          ]);

        const now = Date.now();

        /*
         * Update the persistent client cache.
         */
        cache.clusters = clustersResult;
        cache.reviews = reviewsResult;
        cache.cachedAt = now;

        /*
         * If we already know the scheduler's last run,
         * remember that this cached data includes it.
         */
        const schedulerLastRun =
          parseServerTime(
            schedule?.last_run_time,
          );

        if (schedulerLastRun !== null) {
          cache.schedulerLastRun =
            schedulerLastRun;
        }

        if (mountedRef.current) {
          setClustersData(clustersResult);
          setReviewsData(reviewsResult);

          setClustersLoading(false);
          setReviewsLoading(false);

          setClustersError(null);
          setReviewsError(null);
        }

        return true;
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Unexpected error";

        if (mountedRef.current) {
          setClustersLoading(false);
          setReviewsLoading(false);

          setClustersError(message);
          setReviewsError(message);
        }

        return false;
      } finally {
        refreshingRef.current = false;
      }
    },
    [schedule?.last_run_time],
  );

  /*
   * ----------------------------------------------------------
   * Load scheduler information
   * ----------------------------------------------------------
   */

  const loadSchedule = useCallback(
    async (): Promise<PatternScheduleResponse | null> => {
      try {
        const result =
          await clustersApi.getSchedule();

        if (mountedRef.current) {
          setSchedule(result);
        }

        return result;
      } catch (error) {
        /*
         * Scheduler metadata is informational.
         *
         * Do not destroy the already-working pattern UI if
         * this endpoint temporarily fails.
         */
        console.warn(
          "Could not load pattern scheduler status.",
          error,
        );

        return null;
      }
    },
    [],
  );

  /*
   * ----------------------------------------------------------
   * Initial mount
   * ----------------------------------------------------------
   */

  useEffect(() => {
    mountedRef.current = true;

    let cancelled = false;

    const initialise = async () => {
      /*
       * First obtain the scheduler state.
       *
       * This request is cheap. It does NOT trigger clustering.
       */
      const currentSchedule =
        await loadSchedule();

      if (cancelled || !mountedRef.current) {
        return;
      }

      /*
       * If there is no cached data, this is the first visit.
       *
       * We must load the patterns.
       */
      if (!hasCachedData()) {
        await loadPatterns(true);
        return;
      }

      /*
       * We already have data from a previous visit.
       *
       * Check whether the backend scheduler has actually run
       * since our cached data was created.
       */
      const backendLastRun =
        parseServerTime(
          currentSchedule?.last_run_time,
        );

      const cachedAt =
        cache.cachedAt;

      const schedulerChanged =
        backendLastRun !== null &&
        cachedAt !== null &&
        backendLastRun > cachedAt;

      if (schedulerChanged) {
        /*
         * The hourly job has genuinely produced newer
         * recurring-pattern data.
         *
         * Now — and only now — fetch the new clusters.
         */
        await loadPatterns(true);
      } else {
        /*
         * Nothing changed on the backend.
         *
         * Restore the cached state without triggering
         * clustering.
         */
        setClustersData(cache.clusters);
        setReviewsData(cache.reviews);

        setClustersLoading(false);
        setReviewsLoading(false);
      }
    };

    void initialise();

    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
  }, [loadPatterns, loadSchedule]);

  /*
   * ----------------------------------------------------------
   * Poll scheduler metadata
   * ----------------------------------------------------------
   *
   * This DOES NOT run clustering.
   *
   * It only checks whether the hourly backend job has completed.
   *
   * This allows the UI to notice an hourly update while the user
   * is sitting on the Recurring Patterns page.
   */

  useEffect(() => {
    if (!mountedRef.current) {
      return;
    }

    const interval = window.setInterval(
      async () => {
        if (!mountedRef.current) {
          return;
        }

        const currentSchedule =
          await loadSchedule();

        if (!currentSchedule) {
          return;
        }

        const backendLastRun =
          parseServerTime(
            currentSchedule.last_run_time,
          );

        const cachedAt =
          cache.cachedAt;

        if (
          backendLastRun !== null &&
          cachedAt !== null &&
          backendLastRun > cachedAt
        ) {
          /*
           * The scheduled backend job has run since the
           * currently displayed data was loaded.
           */
          await loadPatterns(true);
        }
      },
      10000,
    );

    return () => {
      window.clearInterval(interval);
    };
  }, [loadPatterns, loadSchedule]);

  /*
   * ----------------------------------------------------------
   * Manual refresh
   * ----------------------------------------------------------
   *
   * The Refresh button is intentionally allowed to trigger
   * clustering. This is an explicit user action.
   */

  const refreshAll = useCallback(async () => {
    const refreshed =
      await loadPatterns(true);

    /*
     * Get the new next-run time after the refresh.
     */
    await loadSchedule();

    return refreshed;
  }, [loadPatterns, loadSchedule]);

  /*
   * ----------------------------------------------------------
   * Human review decision
   * ----------------------------------------------------------
   */

  const decide = useCallback(
    async (
      signature: string,
      status: ReviewStatus,
    ) => {
      if (deciding) {
        return null;
      }

      setDeciding(true);

      try {
        const result =
          await clustersApi.decideReview(
            signature,
            status,
          );

        const updatedReviews =
          await clustersApi.getReviews();

        cache.reviews = updatedReviews;

        if (mountedRef.current) {
          setReviewsData(updatedReviews);
        }

        return result;
      } finally {
        if (mountedRef.current) {
          setDeciding(false);
        }
      }
    },
    [deciding],
  );

  /*
   * ----------------------------------------------------------
   * Agentic pattern check
   * ----------------------------------------------------------
   */

  const agentCheck = useCallback(
    async () => {
      const result =
        await agentApi.checkPatterns();

      /*
       * Agent processing may update the review store.
       *
       * Fetch only the review store here.
       * Do not unnecessarily rerun clustering.
       */
      const updatedReviews =
        await clustersApi.getReviews();

      cache.reviews = updatedReviews;

      if (mountedRef.current) {
        setReviewsData(updatedReviews);
      }

      return result;
    },
    [],
  );

  /*
   * ----------------------------------------------------------
   * Agent resume
   * ----------------------------------------------------------
   */

  const agentResume = useCallback(
    async (
      threadId: string,
      decision: string,
    ) => {
      const result =
        await agentApi.resumePatternCheck(
          threadId,
          decision,
        );

      const updatedReviews =
        await clustersApi.getReviews();

      cache.reviews = updatedReviews;

      if (mountedRef.current) {
        setReviewsData(updatedReviews);
      }

      return result;
    },
    [],
  );

  /*
   * ----------------------------------------------------------
   * Convert API state to the shape expected by the page
   * ----------------------------------------------------------
   */

  const reviewList =
    reviewsToList(reviewsData);

  return {
    clusters: {
      data: clustersData,
      loading: clustersLoading,
      error: clustersError,
      refetch: () => loadPatterns(true),
    },

    reviews: {
      data: reviewsData,
      loading: reviewsLoading,
      error: reviewsError,
      refetch: async () => {
        /*
         * Review-only refresh.
         *
         * This is useful after a decision.
         */
        try {
          setReviewsLoading(true);
          setReviewsError(null);

          const result =
            await clustersApi.getReviews();

          cache.reviews = result;

          if (mountedRef.current) {
            setReviewsData(result);
            setReviewsLoading(false);
          }

          return result;
        } catch (error) {
          const message =
            error instanceof Error
              ? error.message
              : "Unexpected error";

          if (mountedRef.current) {
            setReviewsLoading(false);
            setReviewsError(message);
          }

          return null;
        }
      },
    },

    reviewList,

    decide: {
      loading: deciding,
      error: null,
      run: decide,
    },

    agentCheck: {
      data: null,
      loading: false,
      error: null,
      run: agentCheck,
    },

    agentResume: {
      data: null,
      loading: false,
      error: null,
      run: agentResume,
    },

    refreshAll,

    schedule,
  };
}