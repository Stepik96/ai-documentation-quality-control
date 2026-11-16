from backend.domain.check import Finding


def is_level_one_heading(text: str, style_name: str, built_in: bool) -> bool:
    return bool(text.strip()) and built_in and style_name == "Heading 1"


MISSING_HEADING = Finding(
    location="Основной текст документа",
    rule_id="DOCX-HEADING-01",
    rule="В документе должен быть хотя бы один заголовок в стиле «Заголовок 1».",
    problem="Не найден заголовок первого уровня",
    recommendation="Примените стиль «Заголовок 1» к подходящему заголовку.",
)
