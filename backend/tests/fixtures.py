from io import BytesIO
from pathlib import Path
from sys import argv
from zipfile import ZIP_DEFLATED, ZipFile

MANIFEST = """\
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELATIONSHIPS = """\
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="word/document.xml"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>
</Relationships>"""

DOCUMENT = """\
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>Synthetic test document</w:t></w:r></w:p></w:body>
</w:document>"""


def sample_docx(manifest: str = MANIFEST) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", manifest)
        package.writestr("_rels/.rels", RELATIONSHIPS)
        package.writestr("word/document.xml", DOCUMENT)
    return output.getvalue()


if __name__ == "__main__":
    target = Path(argv[1])
    target.mkdir(parents=True, exist_ok=True)
    (target / "example.docx").write_bytes(sample_docx())
    (target / "example.txt").write_text("Synthetic test file\n", encoding="utf-8")
