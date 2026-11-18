export async function request<T>(
  path: string,
  options: RequestInit,
): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed (HTTP ${String(response.status)}).`;
    if (response.headers.get("content-type")?.includes("application/json")) {
      const body: unknown = await response.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof body.detail === "string"
      ) {
        message = body.detail;
      }
    }
    throw new Error(message);
  }
  // FastAPI validates these responses against the shared API contracts.
  return (await response.json()) as T;
}

export function claimPath(claimId: string): string {
  return `/api/claims/${encodeURIComponent(claimId)}`;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The request could not be completed.";
}
