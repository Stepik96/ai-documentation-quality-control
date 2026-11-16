import re

from docx.oxml.ns import qn
from docx.table import Table
from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph

from backend.domain.style_rules import (
    SYSTEM_OBJECTS,
    TABLE_FONT_HALF_POINTS,
    object_bold_finding,
    table_font_finding,
    table_reference_finding,
)

TABLE_CAPTION = re.compile(r"^\s*таблица\s+(\d+(?:[.\-]\d+)*)(?!\w)", re.IGNORECASE)
TABLE_REFERENCE = re.compile(r"\bтаблиц(?:а|е|у|ы|ей)\s+(\d+(?:[.\-]\d+)*)(?!\w)", re.IGNORECASE)
OBJECT_PATTERN = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(name) for name in SYSTEM_OBJECTS) + r")(?!\w)",
    re.IGNORECASE,
)


def style_chain(style):
    seen = set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        yield style
        style = style.base_style


def text_runs(paragraph):
    for item in paragraph.iter_inner_content():
        if isinstance(item, Hyperlink):
            yield from item.runs
        else:
            yield item


def default_font_size(document):
    elements = document.styles.element.xpath("./w:docDefaults/w:rPrDefault/w:rPr/w:sz")
    return int(elements[0].get(qn("w:val"))) if elements else None


def font_size(run, paragraph, default, table_has_sizes):
    if run.font.size is not None:
        return run.font.size.emu // 6350
    if table_has_sizes:
        return None
    for style in (*style_chain(run.style), *style_chain(paragraph.style)):
        if style.font.size is not None:
            return style.font.size.emu // 6350
    return default


def check_table_font(document, tables):
    default = default_font_size(document)
    findings = []
    unchecked = []
    for table_number, table in enumerate(tables, 1):
        table_location = f"Таблица {table_number} по порядку"
        table_has_sizes = any(style.element.xpath(".//w:sz") for style in style_chain(table.style))
        visited = set()
        for row_number, row in enumerate(table.rows, 1):
            for column, cell in enumerate(row.cells, row.grid_cols_before + 1):
                if cell._tc in visited:
                    continue
                visited.add(cell._tc)
                location = f"{table_location}, строка {row_number}, ячейка {column}"
                if cell.tables:
                    unchecked.append(f"R02: вложенная таблица в позиции «{location}».")
                sizes = {
                    font_size(run, paragraph, default, table_has_sizes)
                    for paragraph in cell.paragraphs
                    for run in text_runs(paragraph)
                    if run.text.strip()
                }
                if None in sizes:
                    unchecked.append(f"R02: не удалось определить размер части текста в позиции «{location}».")
                    sizes.remove(None)
                for size in sorted(sizes - {TABLE_FONT_HALF_POINTS}):
                    findings.append(table_font_finding(location, size))
    return findings, unchecked


def check_table_references(blocks):
    paragraphs = [
        block for block in blocks
        if isinstance(block, Paragraph) and not block.style.style_id.startswith("TOC")
    ]
    references = {
        match[1]
        for paragraph in paragraphs
        if not TABLE_CAPTION.match(paragraph.text)
        for match in TABLE_REFERENCE.finditer(paragraph.text)
    }
    has_word_references = any(
        re.search(r"\b(?:REF|PAGEREF)\b", instruction, re.IGNORECASE)
        for paragraph in paragraphs
        for instruction in paragraph._p.xpath(".//w:instrText/text() | .//w:fldSimple/@w:instr")
    )
    findings = []
    unchecked = []
    used_captions = set()
    table_number = 0
    for index, table in enumerate(blocks):
        if not isinstance(table, Table):
            continue
        table_number += 1
        location = f"Таблица {table_number} по порядку"
        for neighbor in (index - 1, index + 1):
            if 0 <= neighbor < len(blocks) and neighbor not in used_captions:
                paragraph = blocks[neighbor]
                if isinstance(paragraph, Paragraph) and (caption := TABLE_CAPTION.match(paragraph.text)):
                    used_captions.add(neighbor)
                    break
        else:
            unchecked.append(f"R03: у таблицы {table_number} не найдена соседняя подпись с номером.")
            continue
        if caption[1] in references:
            continue
        if has_word_references:
            unchecked.append(f"R03: для таблицы {caption[1]} требуется проверить поля ссылок Word.")
        else:
            findings.append(table_reference_finding(location, caption[1]))
    return findings, unchecked


def is_bold(run, paragraph, default):
    direct = run.font.bold
    if direct is not None:
        return direct
    bold = default
    for style in (*style_chain(paragraph.style), *style_chain(run.style)):
        if style.font.bold:
            bold = not bold
    return bold


def check_object_bold(document):
    default = document.styles.element.xpath("./w:docDefaults/w:rPrDefault/w:rPr/w:b")
    bold_default = bool(default) and default[0].get(qn("w:val")) not in {"0", "false", "off"}
    findings = []
    for number, paragraph in enumerate(document.paragraphs, 1):
        text = []
        formatting = []
        for run in text_runs(paragraph):
            text.append(run.text)
            formatting.extend([is_bold(run, paragraph, bold_default)] * len(run.text))
        for match in OBJECT_PATTERN.finditer("".join(text)):
            if not all(formatting[match.start():match.end()]):
                findings.append(object_bold_finding(f"Абзац {number}", match[0]))
    return findings
