"""Layout-Aware PDF Document Parser.

Extracts text, section headings, and structured tables from financial PDF documents.
Primary engine: PyMuPDF (fitz) with layout table extraction.
Fallback engine: pypdf for raw text recovery.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

PARSER_VERSION = "pymupdf-2.0+layout"


@dataclass
class ParsedTable:
    """Structured financial table extracted from a document page."""
    table_id: str
    page_number: int
    title: Optional[str]
    headers: List[str]
    rows: List[List[str]]
    raw_text: str
    footnotes: List[str] = field(default_factory=list)


@dataclass
class ParsedPage:
    """Extracted text and tables for a single document page."""
    page_number: int
    text: str
    tables: List[ParsedTable] = field(default_factory=list)
    is_blank: bool = False
    warnings: List[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Complete parsed document payload with page and table metadata."""
    document_id: str
    pages: List[ParsedPage] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    full_text: str = ""
    page_count: int = 0
    status: str = "COMPLETE"  # COMPLETE, PARTIAL, FAILED
    warnings: List[str] = field(default_factory=list)
    parser_version: str = PARSER_VERSION


class DocumentParser:
    """Layout-aware PDF parsing engine with table extraction and blank page detection."""

    def __init__(self, fallback_enabled: bool = True):
        self.fallback_enabled = fallback_enabled

    def parse_pdf(self, file_path: Path, document_id: Optional[str] = None) -> ParsedDocument:
        """Parse a local PDF file into structured pages, text blocks, and tables."""
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        path = Path(file_path)

        if not path.exists():
            return ParsedDocument(
                document_id=doc_id,
                status="FAILED",
                warnings=[f"File '{path}' does not exist on disk."],
                parser_version=PARSER_VERSION,
            )

        try:
            return self._parse_with_pymupdf(path, doc_id)
        except Exception as primary_err:
            if not self.fallback_enabled:
                return ParsedDocument(
                    document_id=doc_id,
                    status="FAILED",
                    warnings=[f"PyMuPDF parsing failed: {str(primary_err)}"],
                    parser_version=PARSER_VERSION,
                )

            # Attempt fallback using pypdf
            try:
                fallback_doc = self._parse_with_pypdf(path, doc_id)
                fallback_doc.warnings.append(
                    f"Parsed using pypdf fallback after primary parser failed: {str(primary_err)}"
                )
                fallback_doc.status = "PARTIAL"
                return fallback_doc
            except Exception as fb_err:
                return ParsedDocument(
                    document_id=doc_id,
                    status="FAILED",
                    warnings=[
                        f"Primary parser error: {str(primary_err)}",
                        f"Fallback parser error: {str(fb_err)}",
                    ],
                    parser_version="failed",
                )

    def _parse_with_pymupdf(self, file_path: Path, doc_id: str) -> ParsedDocument:
        """Parse document using PyMuPDF (fitz) with native table recognition."""
        import pymupdf  # PyMuPDF

        pages: List[ParsedPage] = []
        all_tables: List[ParsedTable] = []
        full_text_parts: List[str] = []
        doc_warnings: List[str] = []

        doc = pymupdf.open(str(file_path))
        page_count = len(doc)

        if page_count == 0:
            doc.close()
            return ParsedDocument(
                document_id=doc_id,
                page_count=0,
                status="FAILED",
                warnings=["PDF contains zero pages."],
                parser_version=PARSER_VERSION,
            )

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]
            page_warnings: List[str] = []

            # 1. Extract text blocks
            raw_text = page.get_text("text").strip()
            is_blank = len(raw_text) == 0

            if is_blank:
                page_warnings.append(f"Page {page_num} contains no extractable digital text (scanned image).")
                doc_warnings.append(f"Page {page_num} is blank or unreadable.")

            # 2. Extract structured tables using layout parser
            page_tables: List[ParsedTable] = []
            try:
                tab_finder = page.find_tables()
                if tab_finder and tab_finder.tables:
                    for t_idx, tab in enumerate(tab_finder.tables):
                        extracted_rows = tab.extract()
                        if not extracted_rows:
                            continue

                        headers = [str(col).strip() if col else f"Col_{i}" for i, col in enumerate(extracted_rows[0])]
                        data_rows = [
                            [str(cell).strip() if cell is not None else "" for cell in r]
                            for r in extracted_rows[1:]
                        ]

                        table_text = f"Table on Page {page_num}:\n" + "\n".join(
                            [" | ".join(row) for row in extracted_rows if any(row)]
                        )

                        parsed_table = ParsedTable(
                            table_id=f"tab_{doc_id[:8]}_p{page_num}_{t_idx+1}",
                            page_number=page_num,
                            title=f"Page {page_num} Table {t_idx+1}",
                            headers=headers,
                            rows=data_rows,
                            raw_text=table_text,
                        )
                        page_tables.append(parsed_table)
                        all_tables.append(parsed_table)
            except Exception as t_err:
                page_warnings.append(f"Table detection on page {page_num} returned warning: {str(t_err)}")

            # Fallback for text-based tables (e.g., pipe-delimited financial statements)
            if not page_tables and raw_text:
                lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
                pipe_lines = [l for l in lines if "|" in l]
                if len(pipe_lines) >= 2:
                    t_rows = [[c.strip() for c in pl.split("|")] for pl in pipe_lines]
                    t_rows = [[c for c in row if c] for row in t_rows]
                    if len(t_rows) >= 2 and all(len(r) >= 2 for r in t_rows):
                        headers = t_rows[0]
                        data_rows = t_rows[1:]
                        first_pipe_idx = lines.index(pipe_lines[0])
                        table_title = lines[first_pipe_idx - 1] if first_pipe_idx > 0 else f"Page {page_num} Table"
                        table_text = f"Table on Page {page_num} ({table_title}):\n" + "\n".join(
                            [" | ".join(row) for row in t_rows]
                        )
                        parsed_table = ParsedTable(
                            table_id=f"tab_{doc_id[:8]}_p{page_num}_text1",
                            page_number=page_num,
                            title=table_title,
                            headers=headers,
                            rows=data_rows,
                            raw_text=table_text,
                        )
                        page_tables.append(parsed_table)
                        all_tables.append(parsed_table)

            parsed_page = ParsedPage(
                page_number=page_num,
                text=raw_text,
                tables=page_tables,
                is_blank=is_blank,
                warnings=page_warnings,
            )
            pages.append(parsed_page)
            if raw_text:
                full_text_parts.append(f"--- Page {page_num} ---\n{raw_text}")

        doc.close()

        status = "COMPLETE"
        if any(p.is_blank for p in pages):
            status = "PARTIAL"

        return ParsedDocument(
            document_id=doc_id,
            pages=pages,
            tables=all_tables,
            full_text="\n\n".join(full_text_parts),
            page_count=page_count,
            status=status,
            warnings=doc_warnings,
            parser_version=PARSER_VERSION,
        )

    def _parse_with_pypdf(self, file_path: Path, doc_id: str) -> ParsedDocument:
        """Fallback text extractor using pypdf."""
        import pypdf

        pages: List[ParsedPage] = []
        full_text_parts: List[str] = []
        doc_warnings: List[str] = ["Extracted with pypdf fallback (table structure limited)."]

        reader = pypdf.PdfReader(str(file_path))
        page_count = len(reader.pages)

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = reader.pages[page_idx]
            page_text = page.extract_text() or ""
            is_blank = len(page_text.strip()) == 0

            parsed_page = ParsedPage(
                page_number=page_num,
                text=page_text.strip(),
                tables=[],
                is_blank=is_blank,
                warnings=[f"Page {page_num} blank"] if is_blank else [],
            )
            pages.append(parsed_page)
            if page_text.strip():
                full_text_parts.append(f"--- Page {page_num} ---\n{page_text.strip()}")

        status = "PARTIAL" if any(p.is_blank for p in pages) else "COMPLETE"
        return ParsedDocument(
            document_id=doc_id,
            pages=pages,
            tables=[],
            full_text="\n\n".join(full_text_parts),
            page_count=page_count,
            status=status,
            warnings=doc_warnings,
            parser_version="pypdf-fallback",
        )

    def parse_pptx(self, file_path: Path, document_id: Optional[str] = None) -> ParsedDocument:
        """Parse PowerPoint (.pptx) presentation slides, tables, titles, and speaker notes."""
        from pptx import Presentation

        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PPTX file not found: {path}")

        prs = Presentation(str(path))
        pages: List[ParsedPage] = []
        all_tables: List[ParsedTable] = []
        full_text_parts: List[str] = []
        warnings: List[str] = []

        for slide_idx, slide in enumerate(prs.slides):
            slide_num = slide_idx + 1
            slide_texts: List[str] = []
            slide_tables: List[ParsedTable] = []

            # Extract title if present
            title_text = ""
            if slide.shapes.title and slide.shapes.title.text:
                title_text = slide.shapes.title.text.strip()
                slide_texts.append(f"Slide Title: {title_text}")

            for shape in slide.shapes:
                # Text frame
                if shape.has_text_frame and shape != slide.shapes.title:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            slide_texts.append(text)

                # Tables
                if shape.has_table:
                    tbl = shape.table
                    headers: List[str] = []
                    rows: List[List[str]] = []
                    for row_idx, row in enumerate(tbl.rows):
                        cell_vals = [cell.text.strip() for cell in row.cells]
                        if row_idx == 0:
                            headers = cell_vals
                        else:
                            rows.append(cell_vals)

                    table_text = "\n".join([" | ".join(headers)] + [" | ".join(r) for r in rows])
                    p_table = ParsedTable(
                        table_id=f"tbl_{doc_id}_s{slide_num}_{len(slide_tables)}",
                        page_number=slide_num,
                        title=title_text or f"Slide {slide_num} Table",
                        headers=headers,
                        rows=rows,
                        raw_text=table_text,
                    )
                    slide_tables.append(p_table)
                    all_tables.append(p_table)

            # Speaker Notes
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    slide_texts.append(f"Speaker Notes: {notes}")

            combined_slide_text = "\n".join(slide_texts)
            is_blank = len(combined_slide_text.strip()) == 0

            parsed_page = ParsedPage(
                page_number=slide_num,
                text=combined_slide_text,
                tables=slide_tables,
                is_blank=is_blank,
                warnings=[f"Slide {slide_num} has no text content"] if is_blank else [],
            )
            pages.append(parsed_page)
            if combined_slide_text:
                full_text_parts.append(f"--- Slide {slide_num} ---\n{combined_slide_text}")

        page_count = len(pages)
        status = "PARTIAL" if any(p.is_blank for p in pages) else "COMPLETE"
        if page_count == 0:
            status = "FAILED"
            warnings.append("Presentation contains zero slides.")

        return ParsedDocument(
            document_id=doc_id,
            pages=pages,
            tables=all_tables,
            full_text="\n\n".join(full_text_parts),
            page_count=page_count,
            status=status,
            warnings=warnings,
            parser_version="python-pptx-1.0",
        )

    def parse_html(self, file_path: Path, document_id: Optional[str] = None) -> ParsedDocument:
        """Parse SEC EDGAR HTML/HTM filing or web disclosure into structured tables and pages."""
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        path = Path(file_path)
        if not path.exists():
            return ParsedDocument(
                document_id=doc_id,
                status="FAILED",
                warnings=[f"File '{path}' does not exist on disk."],
                parser_version="bs4-html-sec",
            )

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")

            tables: List[ParsedTable] = []
            for t_idx, tbl in enumerate(soup.find_all("table")):
                rows_data: List[List[str]] = []
                for tr in tbl.find_all("tr"):
                    row_cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if any(row_cells):
                        rows_data.append(row_cells)
                if not rows_data:
                    continue
                headers = rows_data[0]
                body_rows = rows_data[1:] if len(rows_data) > 1 else rows_data
                table_text = "\n".join([" | ".join(r) for r in rows_data])
                tables.append(
                    ParsedTable(
                        table_id=f"tbl_{doc_id}_h{t_idx + 1}",
                        page_number=(t_idx // 3) + 1,
                        title=f"Table {t_idx + 1}",
                        headers=headers,
                        rows=body_rows,
                        raw_text=table_text,
                    )
                )

            # Extract clean narrative text
            raw_text = soup.get_text(separator="\n", strip=True)
            paragraphs = [p for p in raw_text.split("\n") if len(p.strip()) > 10]
            pages: List[ParsedPage] = []
            page_chunk_size = 2500
            current_page_text = ""
            current_page_num = 1

            for p in paragraphs:
                if len(current_page_text) + len(p) > page_chunk_size and current_page_text:
                    p_tables = [t for t in tables if t.page_number == current_page_num]
                    pages.append(
                        ParsedPage(
                            page_number=current_page_num,
                            text=current_page_text.strip(),
                            tables=p_tables,
                            is_blank=False,
                        )
                    )
                    current_page_num += 1
                    current_page_text = p + "\n"
                else:
                    current_page_text += p + "\n"

            if current_page_text.strip():
                p_tables = [t for t in tables if t.page_number == current_page_num]
                pages.append(
                    ParsedPage(
                        page_number=current_page_num,
                        text=current_page_text.strip(),
                        tables=p_tables,
                        is_blank=False,
                    )
                )

            return ParsedDocument(
                document_id=doc_id,
                pages=pages,
                tables=tables,
                full_text=raw_text,
                page_count=len(pages),
                status="COMPLETE",
                warnings=[],
                parser_version="bs4-html-sec",
            )
        except Exception as exc:
            return ParsedDocument(
                document_id=doc_id,
                status="FAILED",
                warnings=[f"HTML parser error: {str(exc)}"],
                parser_version="bs4-html-sec",
            )

    def parse_document(self, file_path: Path, document_id: Optional[str] = None) -> ParsedDocument:
        """Route parsing based on file extension (.pdf, .pptx, or .htm/.html)."""
        suffix = Path(file_path).suffix.lower()
        if suffix == ".pdf":
            return self.parse_pdf(file_path, document_id=document_id)
        elif suffix == ".pptx":
            return self.parse_pptx(file_path, document_id=document_id)
        elif suffix in (".htm", ".html", ".txt"):
            return self.parse_html(file_path, document_id=document_id)
        else:
            raise ValueError(f"Unsupported document format '{suffix}'. Supported formats: .pdf, .pptx, .htm, .html")
