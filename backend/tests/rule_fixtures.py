from io import BytesIO
from pathlib import Path
from sys import argv

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt


def tech_spec(*, size: int, referenced: bool) -> bytes:
    document = Document()
    style = document.styles.add_style("Table sample text", WD_STYLE_TYPE.PARAGRAPH)
    style.font.size = Pt(size)
    if referenced:
        document.add_paragraph("Параметры приведены в таблице 4.")
    document.add_paragraph("Таблица 4. Параметры")
    table = document.add_table(rows=1, cols=1)
    paragraph = table.cell(0, 0).paragraphs[0]
    paragraph.style = style
    paragraph.add_run("Параметр")
    result = BytesIO()
    document.save(result)
    return result.getvalue()


def user_guide(*, fully_bold: bool) -> bytes:
    document = Document()
    paragraph = document.add_paragraph("Откройте подсистему ")
    paragraph.add_run("Планирование деятельности ").bold = True
    paragraph.add_run("предприятия").bold = fully_bold
    paragraph.add_run(".")
    result = BytesIO()
    document.save(result)
    return result.getvalue()


if __name__ == "__main__":
    target = Path(argv[1])
    target.mkdir(parents=True, exist_ok=True)
    (target / "tech-spec-ok.docx").write_bytes(tech_spec(size=10, referenced=True))
    (target / "tech-spec-findings.docx").write_bytes(tech_spec(size=12, referenced=False))
    (target / "user-guide-ok.docx").write_bytes(user_guide(fully_bold=True))
    (target / "user-guide-findings.docx").write_bytes(user_guide(fully_bold=False))
