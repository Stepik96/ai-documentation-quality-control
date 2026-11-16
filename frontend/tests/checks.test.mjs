import test from "node:test";
import assert from "node:assert/strict";
import { uploadDocument, CheckSubmissionError } from "../src/api/checks.ts";

const file = new File(["synthetic document"], "Тестовый документ.docx", {
  type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
});
const jsonResponse = (body, status) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

test("POST sends exactly one real FormData file with browser-generated content type", async () => {
  const controller = new AbortController();
  let calls = 0;
  const accepted = await uploadDocument(
    file,
    controller.signal,
    async (url, options) => {
      calls += 1;
      assert.equal(url, "/api/v1/checks");
      assert.equal(options.method, "POST");
      assert.equal(options.signal, controller.signal);
      assert.equal(options.headers, undefined);
      assert.ok(options.body instanceof FormData);
      assert.deepEqual([...options.body.keys()], ["file"]);
      const sent = options.body.get("file");
      assert.ok(sent instanceof File);
      assert.equal(sent.name, file.name);
      assert.equal(sent.type, file.type);
      assert.equal(await sent.text(), "synthetic document");
      return jsonResponse({ checkId: "chk_001", status: "queued" }, 202);
    },
  );
  assert.deepEqual(accepted, { checkId: "chk_001", status: "queued" });
  assert.equal(
    calls,
    1,
    "one upload does not trigger status or result requests",
  );
});

for (const [status, code, message] of [
  [400, "FILE_REQUIRED", "Выберите документ."],
  [413, "FILE_TOO_LARGE", "Документ превышает допустимый размер."],
  [415, "UNSUPPORTED_FILE_FORMAT", "Для этого API выберите файл DOCX."],
  [422, "INVALID_DOCUMENT", "Документ повреждён или защищён."],
]) {
  test(`HTTP ${status} preserves the server's reason and structured code`, async () => {
    await assert.rejects(
      uploadDocument(file, undefined, async () =>
        jsonResponse({ error: { code, message } }, status),
      ),
      (error) => {
        assert.ok(error instanceof CheckSubmissionError);
        assert.equal(error.message, message);
        assert.equal(error.code, code);
        assert.equal(error.status, status);
        return true;
      },
    );
  });
}

for (const payload of [
  null,
  {},
  { checkId: "", status: "queued" },
  { checkId: "  ", status: "queued" },
  { checkId: "chk_1", status: "processing" },
  { checkId: 1, status: "queued" },
]) {
  test(`202 without a valid receipt is rejected: ${JSON.stringify(payload)}`, async () => {
    await assert.rejects(
      uploadDocument(file, undefined, async () => jsonResponse(payload, 202)),
      (error) =>
        error instanceof CheckSubmissionError &&
        error.code === "INVALID_RESPONSE" &&
        error.status === 202,
    );
  });
}

test("202 with an HTML response is not shown as accepted", async () => {
  await assert.rejects(
    uploadDocument(
      file,
      undefined,
      async () => new Response("<html>proxy</html>", { status: 202 }),
    ),
    (error) =>
      error instanceof CheckSubmissionError &&
      error.code === "INVALID_RESPONSE",
  );
});

test("200 with a plausible receipt is not accepted instead of contract 202", async () => {
  await assert.rejects(
    uploadDocument(file, undefined, async () =>
      jsonResponse({ checkId: "chk_001", status: "queued" }, 200),
    ),
    (error) =>
      error instanceof CheckSubmissionError &&
      error.code === "UNEXPECTED_STATUS" &&
      error.status === 200,
  );
});

test("HTML proxy failures have a readable unavailable-server fallback", async () => {
  await assert.rejects(
    uploadDocument(
      file,
      undefined,
      async () => new Response("Bad gateway", { status: 502 }),
    ),
    (error) => {
      assert.ok(error instanceof CheckSubmissionError);
      assert.match(error.message, /временно недоступен/);
      assert.equal(error.status, 502);
      return true;
    },
  );
});

test("missing server message uses the status-specific explanation", async () => {
  await assert.rejects(
    uploadDocument(file, undefined, async () =>
      jsonResponse({ error: { message: " " } }, 415),
    ),
    (error) =>
      error instanceof CheckSubmissionError &&
      /не поддерживает формат/.test(error.message),
  );
});

test("an empty Vite proxy 500 tells the user to check the API connection", async () => {
  await assert.rejects(
    uploadDocument(
      file,
      undefined,
      async () => new Response(null, { status: 500 }),
    ),
    (error) =>
      error instanceof CheckSubmissionError &&
      /сервер запущен/.test(error.message),
  );
});

test("network failure becomes a connection error and a later retry can succeed", async () => {
  await assert.rejects(
    uploadDocument(file, undefined, async () => {
      throw new TypeError("Failed to fetch");
    }),
    (error) =>
      error instanceof CheckSubmissionError &&
      error.code === "CONNECTION_ERROR" &&
      error.status === undefined,
  );
  assert.deepEqual(
    await uploadDocument(file, undefined, async () =>
      jsonResponse({ checkId: "retry_1", status: "queued" }, 202),
    ),
    { checkId: "retry_1", status: "queued" },
  );
});

test("abort stays distinguishable from a connection failure", async () => {
  const controller = new AbortController();
  const aborted = new DOMException("Aborted", "AbortError");
  controller.abort();
  await assert.rejects(
    uploadDocument(file, controller.signal, async () => {
      throw aborted;
    }),
    (error) => error === aborted,
  );
});
