import { useCallback, useEffect, useState } from "react";
import { errorMessage, request } from "./api";

interface Snapshot<T> {
  path: string;
  key: string;
  data: T | null;
  error: string | null;
}

export interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function useResource<T>(path: string | null): Resource<T> {
  const [version, setVersion] = useState(0);
  const [snapshot, setSnapshot] = useState<Snapshot<T> | null>(null);
  const key = `${path ?? ""}:${String(version)}`;
  const reload = useCallback(() => {
    setVersion((previous) => previous + 1);
  }, []);

  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    void request<T>(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setSnapshot({ path, key, data, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setSnapshot((previous) => ({
            path,
            key,
            data: previous?.path === path ? previous.data : null,
            error: errorMessage(error),
          }));
        }
      });
    return () => {
      controller.abort();
    };
  }, [path, key]);

  return {
    data: path !== null && snapshot?.path === path ? snapshot.data : null,
    error: snapshot?.key === key ? snapshot.error : null,
    loading: path !== null && snapshot?.key !== key,
    reload,
  };
}
