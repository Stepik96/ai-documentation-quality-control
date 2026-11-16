import type { DocumentProfile } from "./checks";

export type CheckResult = {
  checkId: string;
  profile: DocumentProfile;
  rulesVersion: string;
  completeness: "complete" | "partial";
  findings: {
    location: string;
    ruleId: string;
    rule: string;
    problem: string;
    recommendation: string;
    category: string;
  }[];
  unchecked: string[];
};

type CheckStatus = {
  status: "queued" | "processing" | "completed" | "failed";
  error?: { message: string };
};

async function readCheck<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, cache: "no-store" });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.error?.message ?? "Не удалось получить результат проверки.");
  }
  return response.json();
}

export async function waitForResult(
  checkId: string,
  signal: AbortSignal,
  onProgress: (status: "queued" | "processing") => void,
): Promise<CheckResult> {
  const path = `/api/v1/checks/${encodeURIComponent(checkId)}`;
  while (!signal.aborted) {
    const check = await readCheck<CheckStatus>(path, signal);
    switch (check.status) {
      case "completed":
        return readCheck<CheckResult>(`${path}/result`, signal);
      case "failed":
        throw new Error(check.error?.message ?? "Не удалось проверить документ.");
      case "queued":
      case "processing":
        onProgress(check.status);
        break;
      default:
        throw new Error("Сервер вернул неизвестный статус проверки.");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw signal.reason;
}
