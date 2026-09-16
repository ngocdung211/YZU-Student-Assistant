"""Adapt HaUI Markdown splitting while retaining all physical source pages."""

from dataclasses import dataclass
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    """A passage with its first page, full page provenance, and heading context."""

    text: str
    page_number: int
    heading_path: str
    chunk_index: int
    page_numbers: list[int]


def chunk_pages(pages: list[tuple[int, str]], chunk_size: int = 2500, min_chunk_size: int = 700,
                chunk_overlap: int = 500) -> list[Chunk]:
    """Split sections across pages, mapping each passage back to source spans."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=len,
        add_start_index=True, keep_separator="end", is_separator_regex=True,
        separators=[r"\n\n", r"(?<=[.!?]) +", r"\n", " ", ""],
    )
    headings: list[tuple[int, str]] = []
    chunks: list[Chunk] = []
    content = ""
    spans: list[tuple[int, int, int]] = []

    def flush() -> None:
        nonlocal content

        heading_path = " > ".join(title for _, title in headings)

        prev_chunk_text = ""

        for document in splitter.create_documents([content]):

            start = document.metadata["start_index"]
            end = start + len(document.page_content)

            source_pages = sorted({
                page for left, right, page in spans
                if left < end and right > start
            })

            current_chunk = Chunk(
                document.page_content,
                source_pages[0],
                heading_path,
                len(chunks),
                source_pages,
            )

            if (
                current_chunk.text.strip()
                and len(current_chunk.text) < min_chunk_size
            ):
                # Accumulate consecutive small chunks
                if prev_chunk_text:
                    prev_chunk_text += "\n" + current_chunk.text
                else:
                    prev_chunk_text = current_chunk.text

                continue

            # Merge accumulated small chunk(s) with current chunk
            if prev_chunk_text:
                current_chunk.text = (
                    prev_chunk_text + "\n" + current_chunk.text
                )
                prev_chunk_text = ""

            chunks.append(current_chunk)

        # Edge case: final chunk(s) are smaller than min_chunk_size
        if prev_chunk_text:
            if chunks:
                chunks[-1].text += "\n" + prev_chunk_text
            else:
                # Entire section itself is < min_chunk_size
                chunks.append(
                    Chunk(
                        prev_chunk_text,
                        spans[0][2],
                        heading_path,
                        len(chunks),
                        sorted({page for _, _, page in spans}),
                    )
                )

        content = ""
        spans.clear()

    for page_number, markdown in pages:
        for line_index, line in enumerate(markdown.strip().splitlines()):
            heading = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if heading:
                flush()
                level, title = len(heading[1]), heading[2].strip()
                headings = [(depth, name) for depth, name in headings if depth < level]
                headings.append((level, title))
            separator = "\n" if content else ""
            if content and line_index == 0:
                # Join plain-text continuations; retain new list/table/paragraph boundaries.
                continuation = (re.search(r"[\w,]$", content)
                                and re.match(r"^[a-z]", line))
                separator = " " if continuation else "\n\n"
            start = len(content) + len(separator)
            content += separator + line
            if line.strip():
                spans.append((start, len(content), page_number))
        # A physical page break is provenance, not an unconditional chunk boundary.
    flush()
    return chunks
