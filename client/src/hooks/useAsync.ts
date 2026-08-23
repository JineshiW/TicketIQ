import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Manual-trigger async action (forms, buttons).
 *
 * Tracks whether the component is currently mounted so an async
 * response cannot update state after unmounting.
 *
 * IMPORTANT:
 * mounted.current is explicitly reset to true inside the effect.
 * This is required for React StrictMode development behaviour.
 */
export function useAsyncAction<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
) {
  const [state, setState] = useState<AsyncState<TResult>>({
    data: null,
    loading: false,
    error: null,
  });

  const mounted = useRef(true);

  useEffect(() => {
    // React StrictMode may run the effect cleanup/setup cycle
    // during development. Always restore the mounted state.
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(
    async (...args: TArgs) => {
      setState((s) => ({
        ...s,
        loading: true,
        error: null,
      }));

      try {
        const data = await fn(...args);

        if (mounted.current) {
          setState({
            data,
            loading: false,
            error: null,
          });
        }

        return data;
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Unexpected error";

        if (mounted.current) {
          setState({
            data: null,
            loading: false,
            error: message,
          });
        }

        return null;
      }
    },
    [fn],
  );

  const reset = useCallback(() => {
    setState({
      data: null,
      loading: false,
      error: null,
    });
  }, []);

  return {
    ...state,
    run,
    reset,
  };
}

/**
 * Fetch-on-mount resource with refetch.
 */
export function useAsyncResource<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
) {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({
      ...s,
      loading: true,
      error: null,
    }));

    try {
      const data = await fn();

      setState({
        data,
        loading: false,
        error: null,
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unexpected error";

      setState({
        data: null,
        loading: false,
        error: message,
      });
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    ...state,
    refetch: load,
    setData: (d: T) =>
      setState({
        data: d,
        loading: false,
        error: null,
      }),
  };
}