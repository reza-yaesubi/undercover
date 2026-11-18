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

export function useResource<T>(path: string | null, poll = false): Resource<T> {
  const [version, setVersion] = useState(0);
  const [snapshot, setSnapshot] = useState<Snapshot<T> | null>(null);
  const key = `${path ?? ""}:${String(version)}`;
  const reload = useCallback(() => {
    setVersion((previous) => previous + 1);
  }, []);

  useEffect(() => {
    if (path === null) return;
    const requestPath = path;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const data = await request<T>(requestPath, {
          signal: controller.signal,
        });
        if (!controller.signal.aborted)
          setSnapshot({ path: requestPath, key, data, error: null });
      } catch (error: unknown) {
        if (!controller.signal.aborted) {
          setSnapshot((previous) => ({
            path: requestPath,
            key,
            data: previous?.path === requestPath ? previous.data : null,
            error: errorMessage(error),
          }));
        }
      } finally {
        if (poll && !controller.signal.aborted) {
          timer = setTimeout(() => {
            void load();
          }, 1000);
        }
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, key, poll]);

  return {
    data: path !== null && snapshot?.path === path ? snapshot.data : null,
    error: snapshot?.key === key ? snapshot.error : null,
    loading: path !== null && snapshot?.key !== key,
    reload,
  };
}
