export type DocumentProfile = "heading-demo" | "tech-spec" | "user-guide";

export type AcceptedCheck = {
  checkId: string;
  status: "queued";
};

export class CheckSubmissionError extends Error {
  readonly code: string;
  readonly status?: number;

  constructor(message: string, code: string, status?: number) {
    super(message);
    this.name = "CheckSubmissionError";
    this.code = code;
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isAbort(error: unknown, signal?: AbortSignal): boolean {
  return (
    signal?.aborted === true ||
    (error instanceof Error && error.name === "AbortError")
  );
}

function fallbackMessage(status: number): string {
  switch (status) {
    case 400:
      return "Сервер не получил документ. Выберите файл и отправьте его ещё раз.";
    case 401:
      return "Сервер требует активную сессию. Обратитесь к команде проекта.";
    case 413:
      return "Размер файла превышает ограничение сервера. Выберите другой документ.";
    case 415:
      return "Сервер не поддерживает формат файла. Выберите другой документ.";
    case 422:
      return "Сервер не смог принять документ: файл повреждён или защищён. Выберите другой файл.";
    case 500:
      return "Не удалось получить ответ от API. Проверьте, что сервер запущен, и попробуйте отправить документ ещё раз.";
    case 502:
    case 503:
    case 504:
      return "Сервер проверки временно недоступен. Попробуйте отправить документ ещё раз.";
    default:
      return `Не удалось отправить документ (HTTP ${status}). Попробуйте ещё раз.`;
  }
}

/** Send one file. Browser supplies the multipart boundary; no polling is started. */
export async function uploadDocument(
  file: File,
  signal?: AbortSignal,
  request: typeof fetch = fetch,
  profile: DocumentProfile = "heading-demo",
): Promise<AcceptedCheck> {
  const form = new FormData();
  form.append("file", file);
  if (profile !== "heading-demo") form.append("profile", profile);

  let response: Response;
  try {
    response = await request("/api/v1/checks", {
      method: "POST",
      body: form,
      signal,
    });
  } catch (error) {
    if (isAbort(error, signal)) throw error;
    throw new CheckSubmissionError(
      "Не удалось соединиться с сервером. Проверьте, что API запущен, и попробуйте ещё раз.",
      "CONNECTION_ERROR",
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (error) {
    if (isAbort(error, signal)) throw error;
    // A reverse proxy may return HTML or an empty body instead of contract JSON.
    payload = null;
  }

  if (response.status === 202) {
    if (
      isRecord(payload) &&
      typeof payload.checkId === "string" &&
      payload.checkId.trim().length > 0 &&
      payload.status === "queued"
    ) {
      return { checkId: payload.checkId, status: "queued" };
    }
    throw new CheckSubmissionError(
      "Сервер не подтвердил приём документа: получен некорректный ответ. Попробуйте ещё раз.",
      "INVALID_RESPONSE",
      response.status,
    );
  }

  const serverError =
    isRecord(payload) && isRecord(payload.error) ? payload.error : null;
  const message =
    typeof serverError?.message === "string" && serverError.message.trim()
      ? serverError.message
      : fallbackMessage(response.status);
  const code =
    typeof serverError?.code === "string" && serverError.code.trim()
      ? serverError.code
      : response.ok
        ? "UNEXPECTED_STATUS"
        : "UPLOAD_REJECTED";

  throw new CheckSubmissionError(message, code, response.status);
}
