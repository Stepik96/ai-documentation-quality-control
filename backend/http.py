from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from backend.core.process_check import ProcessCheck
from backend.core.submit_check import (
    InvalidDocument,
    SubmitCheck,
    UnsupportedFileFormat,
)
from backend.domain.check import CheckStatus, DocumentProfile, SubmittedDocument
from backend.infrastructure.check_repository import InMemoryCheckRepository
from backend.infrastructure.docx import DocxInspector
from backend.infrastructure.docx_analyzer import DocxAnalyzer

MAX_REQUEST_BYTES = 10 * 1024 * 1024
CHECK_FAILED_MESSAGE = "Не удалось проверить документ. Попробуйте ещё раз."


def error_response(status: int, code: str, message: str):
    return jsonify(error={"code": code, "message": message}), status


def create_app(submit_check: SubmitCheck | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    process = None
    if submit_check is None:
        store = InMemoryCheckRepository()
        submit_check = SubmitCheck(DocxInspector(), store)
        process = ProcessCheck(store, DocxAnalyzer())
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="docx-check")

        @app.get("/api/v1/checks/<check_id>")
        def status(check_id):
            check = store.get(check_id)
            if check is None:
                return error_response(404, "CHECK_NOT_FOUND", "Проверка не найдена.")
            payload = {"checkId": check.id, "status": check.status.value}
            if check.status == CheckStatus.FAILED:
                payload["error"] = {"code": "CHECK_FAILED", "message": CHECK_FAILED_MESSAGE}
            return jsonify(payload)

        @app.get("/api/v1/checks/<check_id>/result")
        def report(check_id):
            check = store.get(check_id)
            if check is None:
                return error_response(404, "CHECK_NOT_FOUND", "Проверка не найдена.")
            if check.status == CheckStatus.FAILED:
                return error_response(409, "CHECK_FAILED", CHECK_FAILED_MESSAGE)
            result = check.result
            if result is None:
                return error_response(409, "CHECK_NOT_READY", "Проверка ещё не завершилась.")
            findings = [
                {
                    "location": finding.location,
                    "ruleId": finding.rule_id,
                    "rule": finding.rule,
                    "problem": finding.problem,
                    "recommendation": finding.recommendation,
                    "category": finding.category,
                }
                for finding in result.findings
            ]
            return jsonify(
                checkId=check.id,
                profile=check.document.profile.value,
                rulesVersion=result.rules_version,
                completeness="partial" if result.unchecked else "complete",
                summary={"findingCount": len(findings)},
                findings=findings,
                unchecked=list(result.unchecked),
            )

    @app.errorhandler(BadRequest)
    def bad_request(_error):
        return error_response(400, "INVALID_REQUEST", "Не удалось прочитать запрос загрузки.")

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return error_response(413, "FILE_TOO_LARGE", "Размер запроса превышает 10 МиБ.")

    @app.post("/api/v1/checks")
    def submit():
        files = request.files.getlist("file") if request.mimetype == "multipart/form-data" else []
        if not files:
            return error_response(400, "FILE_REQUIRED", "Выберите документ для загрузки.")
        if len(files) != 1 or len(request.files) != 1:
            return error_response(400, "INVALID_REQUEST", "Загрузите один документ за раз.")
        if set(request.form) - {"profile"} or len(request.form.getlist("profile")) > 1:
            return error_response(400, "INVALID_REQUEST", "Передайте только один профиль проверки.")
        (upload,) = files
        if not upload.filename:
            return error_response(400, "FILE_REQUIRED", "Выберите документ для загрузки.")

        try:
            profile = DocumentProfile(request.form.get("profile", DocumentProfile.HEADING_DEMO))
        except ValueError:
            return error_response(400, "INVALID_PROFILE", "Выберите поддерживаемый тип документа.")

        try:
            check = submit_check.execute(SubmittedDocument(upload.filename, upload.read(), profile))
        except UnsupportedFileFormat:
            return error_response(415, "UNSUPPORTED_FILE_FORMAT", "Выберите файл в формате DOCX.")
        except InvalidDocument:
            return error_response(422, "INVALID_DOCUMENT", "Выберите неповреждённый файл DOCX без защиты паролем.")

        if process is not None:
            executor.submit(process.execute, check)
        return jsonify(checkId=check.id, status=check.status.value), 202

    return app
