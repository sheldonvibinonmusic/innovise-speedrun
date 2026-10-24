"""Page-Aware and Table-Aware Document Chunking.

Segments parsed financial documents into coherent, context-preserving chunks:
- Narrative text: 400-700 tokens with 50-80 token overlap
- Tables: Header-repeated table blocks to preserve line item coordinates
- Rich metadata: document ID, page number, section title, and chunk type
"""

import hashlib
import re
from typing import Any, Dict, List, Optional
import uuid

from app.db.models import DocumentChunk
from app.ingestion.parser import ParsedDocument, ParsedPage, ParsedTable


def estimate_tokens(text: str) -> int:
    """Fast approximation of token count based on whitespace and punctuation."""
    return max(1, len(re.findall(r"\w+|[^\w\s]", text)))


class DocumentChunker:
    """Splits parsed pages and tables into retrieval-ready, citation-traceable chunks."""

    def __init__(
        self,
        chunk_size_tokens: int = 500,
        chunk_overlap_tokens: int = 60,
    ):
        self.chunk_size_tokens = chunk_size_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens

    def chunk_document(
        self,
        doc: ParsedDocument,
        company_ticker: Optional[str] = None,
        reporting_period: Optional[str] = None,
    ) -> List[DocumentChunk]:
        """Convert a ParsedDocument into a list of persistent DocumentChunk objects."""
        chunks: List[DocumentChunk] = []
        chunk_counter = 0
        seen_content_hashes = set()

        for page in doc.pages:
            page_num = page.page_number
            page_text = page.text.strip()

            # 1. Chunk narrative text if present
            if page_text:
                paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                current_chunk_words: List[str] = []
                current_tokens = 0
                current_section = f"Page {page_num}"

                for para in paragraphs:
                    # Detect potential section headings (short line ending without period)
                    if len(para) < 100 and not para.endswith((".", ":", ";")):
                        current_section = para

                    para_tokens = estimate_tokens(para)

                    if current_tokens + para_tokens > self.chunk_size_tokens and current_chunk_words:
                        content_str = "\n\n".join(current_chunk_words)
                        content_hash = hashlib.sha256(content_str.encode()).hexdigest()

                        if content_hash not in seen_content_hashes:
                            seen_content_hashes.add(content_hash)
                            chunk_id = f"chk_{doc.document_id[:8]}_{chunk_counter:04d}"
                            chunk = DocumentChunk(
                                id=chunk_id,
                                document_id=doc.document_id,
                                page_number=page_num,
                                chunk_index=chunk_counter,
                                chunk_type="narrative",
                                section_title=current_section,
                                content=content_str,
                                token_count=estimate_tokens(content_str),
                            )
                            chunk.metadata_dict = {
                                "company_ticker": company_ticker,
                                "reporting_period": reporting_period,
                                "content_hash": content_hash,
                            }
                            chunks.append(chunk)
                            chunk_counter += 1

                        # Keep overlap from previous paragraph
                        overlap_words = current_chunk_words[-1:] if len(current_chunk_words) > 1 else []
                        current_chunk_words = overlap_words + [para]
                        current_tokens = sum(estimate_tokens(w) for w in current_chunk_words)
                    else:
                        current_chunk_words.append(para)
                        current_tokens += para_tokens

                # Final remainder narrative chunk
                if current_chunk_words:
                    content_str = "\n\n".join(current_chunk_words)
                    content_hash = hashlib.sha256(content_str.encode()).hexdigest()
                    if content_hash not in seen_content_hashes:
                        seen_content_hashes.add(content_hash)
                        chunk_id = f"chk_{doc.document_id[:8]}_{chunk_counter:04d}"
                        chunk = DocumentChunk(
                            id=chunk_id,
                            document_id=doc.document_id,
                            page_number=page_num,
                            chunk_index=chunk_counter,
                            chunk_type="narrative",
                            section_title=current_section,
                            content=content_str,
                            token_count=estimate_tokens(content_str),
                        )
                        chunk.metadata_dict = {
                            "company_ticker": company_ticker,
                            "reporting_period": reporting_period,
                            "content_hash": content_hash,
                        }
                        chunks.append(chunk)
                        chunk_counter += 1

            # 2. Chunk structured tables (repeat headers for table preservation)
            for tab in page.tables:
                if not tab.rows:
                    continue

                table_header_str = " | ".join(tab.headers)
                # Group rows in batches of up to 10 rows per table chunk
                batch_size = 10
                for r_idx in range(0, len(tab.rows), batch_size):
                    row_batch = tab.rows[r_idx : r_idx + batch_size]
                    rows_formatted = "\n".join([" | ".join(r) for r in row_batch if any(r)])

                    content_str = (
                        f"[Financial Table - {tab.title or f'Page {page_num}'}]\n"
                        f"Headers: {table_header_str}\n"
                        f"---\n"
                        f"{rows_formatted}"
                    )
                    content_hash = hashlib.sha256(content_str.encode()).hexdigest()

                    if content_hash not in seen_content_hashes:
                        seen_content_hashes.add(content_hash)
                        chunk_id = f"chk_{doc.document_id[:8]}_{chunk_counter:04d}"
                        chunk = DocumentChunk(
                            id=chunk_id,
                            document_id=doc.document_id,
                            page_number=page_num,
                            chunk_index=chunk_counter,
                            chunk_type="table",
                            section_title=tab.title or f"Table on Page {page_num}",
                            content=content_str,
                            token_count=estimate_tokens(content_str),
                        )
                        chunk.metadata_dict = {
                            "company_ticker": company_ticker,
                            "reporting_period": reporting_period,
                            "table_id": tab.table_id,
                            "content_hash": content_hash,
                        }
                        chunks.append(chunk)
                        chunk_counter += 1

        return chunks
