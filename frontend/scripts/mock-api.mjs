import { createServer } from "node:http";
import { randomUUID } from "node:crypto";
import { setTimeout as delay } from "node:timers/promises";

function positiveInteger(value, fallback, allowZero = false) {
  const parsed = Number(value);
  return value !== undefined &&
    Number.isSafeInteger(parsed) &&
    (allowZero ? parsed >= 0 : parsed > 0)
    ? parsed
    : fallback;
}

const port = positiveInteger(process.env.MOCK_PORT, 8000);
const delayMs = positiveInteger(process.env.MOCK_DELAY_MS, 500, true);
const maxBodyBytes = positiveInteger(
  process.env.MOCK_MAX_BODY_BYTES,
  10 * 1024 * 1024,
);

function respond(response, status, body) {
  if (response.destroyed) return;
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(body));
}

function error(response, status, code, message) {
  respond(response, status, { error: { code, message } });
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    if (url.pathname === "/health" && request.method === "GET") {
      respond(response, 200, { status: "ok", mock: true });
      return;
    }
    if (url.pathname !== "/api/v1/checks") {
      request.resume();
      error(response, 404, "NOT_FOUND", "Маршрут заглушки не найден.");
      return;
    }
    if (request.method !== "POST") {
      request.resume();
      error(
        response,
        405,
        "METHOD_NOT_ALLOWED",
        "Для загрузки требуется POST.",
      );
      return;
    }

    // Bound only this development stub's memory usage; not a product file limit.
    let bytes = 0;
    let oversized = false;
    const chunks = [];
    for await (const chunk of request) {
      bytes += chunk.length;
      if (bytes > maxBodyBytes) {
        oversized = true;
        chunks.length = 0;
      } else if (!oversized) {
        chunks.push(chunk);
      }
    }

    await delay(delayMs);
    if (oversized) {
      error(
        response,
        413,
        "FILE_TOO_LARGE",
        "Размер запроса превышает лимит локальной заглушки.",
      );
      return;
    }

    const contentType = request.headers["content-type"] || "";
    if (!contentType.toLowerCase().startsWith("multipart/form-data")) {
      error(
        response,
        400,
        "FILE_REQUIRED",
        "Передайте документ в поле file через FormData.",
      );
      return;
    }

    let form;
    try {
      const body = new Request("http://127.0.0.1/api/v1/checks", {
        method: "POST",
        headers: { "Content-Type": contentType },
        body: Buffer.concat(chunks),
      });
      form = await body.formData();
    } catch {
      error(
        response,
        400,
        "INVALID_REQUEST",
        "Не удалось прочитать multipart/form-data.",
      );
      return;
    }

    const files = form.getAll("file");
    const file = files[0];
    if (!file || typeof file === "string") {
      error(response, 400, "FILE_REQUIRED", "Выберите документ для загрузки.");
      return;
    }
    if (files.length !== 1) {
      error(
        response,
        400,
        "INVALID_REQUEST",
        "Загрузите один документ за раз.",
      );
      return;
    }
    if (!file.name.toLowerCase().endsWith(".docx")) {
      error(
        response,
        415,
        "UNSUPPORTED_FILE_FORMAT",
        "Для локальной заглушки выберите файл DOCX.",
      );
      return;
    }

    // Filename-only simulation: no parsing, disk writes, analysis or status jobs.
    respond(response, 202, {
      checkId: `chk_${randomUUID()}`,
      status: "queued",
    });
  } catch {
    error(
      response,
      500,
      "MOCK_API_ERROR",
      "Локальная заглушка не смогла обработать запрос.",
    );
  }
});

server.on("error", (cause) => {
  console.error(
    `Не удалось запустить заглушку: ${cause.code || cause.message}`,
  );
  process.exitCode = 1;
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Mock API: http://127.0.0.1:${port}`);
  console.log(
    `POST /api/v1/checks · delay ${delayMs} ms · request limit ${maxBodyBytes} bytes`,
  );
  console.log(
    "Заглушка проверяет только расширение. Файлы не сохраняются и не анализируются.",
  );
});
