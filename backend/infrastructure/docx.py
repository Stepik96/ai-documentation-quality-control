from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile
from zlib import error as ZlibError

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

CONTENT_TYPES = "[Content_Types].xml"
CONTENT_TYPES_LIMIT = 256 * 1024
TYPES_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
MAIN_DOCUMENT = "word/document.xml"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


class DocxInspector:
    def is_valid(self, content: bytes) -> bool:
        try:
            with ZipFile(BytesIO(content)) as package:
                package.getinfo("_rels/.rels")
                package.getinfo(MAIN_DOCUMENT)
                if any(part.flag_bits & 1 for part in package.infolist()):
                    return False

                # Check the bounded manifest without extracting or parsing document text.
                manifest_part = package.getinfo(CONTENT_TYPES)
                if manifest_part.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
                    return False
                with package.open(manifest_part) as manifest:
                    xml = manifest.read(CONTENT_TYPES_LIMIT + 1)
                if len(xml) > CONTENT_TYPES_LIMIT:
                    return False
                types = fromstring(xml, forbid_dtd=True)

        except (
            BadZipFile,
            DefusedXmlException,
            LookupError,
            NotImplementedError,
            OSError,
            ParseError,
            RuntimeError,
            ValueError,
            ZlibError,
        ):
            return False

        return types.tag == f"{TYPES_NS}Types" and any(
            item.get("PartName") == f"/{MAIN_DOCUMENT}"
            and item.get("ContentType") == DOCX_CONTENT_TYPE
            for item in types.findall(f"{TYPES_NS}Override")
        )
