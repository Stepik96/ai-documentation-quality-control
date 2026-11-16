import argparse
from pathlib import Path

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

STYLE_LABELS = {"Heading 1": "Заголовок 1", "Normal": "Обычный"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Print DOCX paragraphs and check for a level-one heading.")
    parser.add_argument("document", type=Path, help="path to a DOCX file")
    args = parser.parse_args()

    try:
        document = Document(args.document)
    except (OSError, PackageNotFoundError) as exc:
        parser.exit(1, f"Could not open DOCX: {exc}\n")

    has_heading = False
    for paragraph in document.paragraphs:
        if not paragraph.text.strip():
            continue
        style = paragraph.style
        label = STYLE_LABELS.get(style.name, style.name) if style.builtin else style.name
        print(f"[{label}] {paragraph.text}")
        if style.builtin and style.name == "Heading 1":
            has_heading = True

    if not has_heading:
        print("Не найден заголовок первого уровня")


if __name__ == "__main__":
    main()
