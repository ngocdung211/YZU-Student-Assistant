"""Convert PDF pages to Markdown with Docling, as in the HaUI pipeline."""

from pathlib import Path

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.document_converter import DocumentConverter

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 100


def extract_pdf(path: Path) -> list[tuple[int, str]]:
    """Return actual one-based PDF page numbers and their Markdown content."""
    converter = DocumentConverter(allowed_formats=[InputFormat.PDF])
    result = converter.convert(path, max_num_pages=MAX_PDF_PAGES,
                               max_file_size=MAX_PDF_BYTES)
    if result.status != ConversionStatus.SUCCESS:
        raise ValueError("PDF conversion was incomplete.")
    # Export each physical page so citation metadata never defaults to page zero.
    pages = [(number, result.document.export_to_markdown(page_no=number))
             for number in sorted(result.document.pages)]
    if not pages or not any(text.strip() for _, text in pages):
        raise ValueError("The PDF contains no extractable text.")
    return pages
