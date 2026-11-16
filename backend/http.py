from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from backend.core.submit_check import (
    InvalidDocument,
    SubmitCheck,
    UnsupportedFileFormat,
)
from backend.domain.check import SubmittedDocument
from backend.infrastructure.check_repository import InMemoryCheckRepository
from backend.infrastructure.docx import DocxInspector

MAX_REQUEST_BYTES = 10 * 1024 * 1024


def error_response(status: int, code: str, message: str):
    return jsonify(error={"code": code, "message": message}), status


def create_app(submit_check: SubmitCheck | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    if submit_check is None:
        submit_check = SubmitCheck(DocxInspector(), InMemoryCheckRepository())

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
        if len(files) != 1 or len(request.files) != 1 or request.form:
            return error_response(400, "INVALID_REQUEST", "Загрузите один документ за раз.")
        (upload,) = files
        if not upload.filename:
            return error_response(400, "FILE_REQUIRED", "Выберите документ для загрузки.")

        try:
            check = submit_check.execute(SubmittedDocument(upload.filename, upload.read()))
        except UnsupportedFileFormat:
            return error_response(415, "UNSUPPORTED_FILE_FORMAT", "Выберите файл в формате DOCX.")
        except InvalidDocument:
            return error_response(422, "INVALID_DOCUMENT", "Выберите неповреждённый файл DOCX без защиты паролем.")

        return jsonify(checkId=check.id, status=check.status.value), 202

    return app
