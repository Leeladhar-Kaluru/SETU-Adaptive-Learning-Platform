import hashlib
from typing import List, Dict, Any, Tuple


class ChunkingService:
    def create_chunks(self, pages: List[Dict[str, Any]], chunk_size_words: int = 250, overlap_words: int = 40) -> List[Dict[str, Any]]:
        """
        Creates heading-aware chunks with exact page provenance.

        Pages are merged only while they belong to the same heading. Every word
        keeps the page it came from, so `page_start`/`page_end` and
        `heading_path` always describe the text inside that chunk.
        """
        groups: List[Tuple[str, List[Tuple[str, int]]]] = []
        current_heading = ""
        current_tokens: List[Tuple[str, int]] = []

        for page in pages:
            page_num = page.get("page_number") or 1
            page_text = (page.get("text") or "").strip()
            if not page_text:
                continue

            page_heading = ""
            for raw_line in page_text.splitlines():
                line = raw_line.strip()
                if line.startswith(("#", "Chapter", "CHAPTER", "Unit", "UNIT", "Section", "SECTION", "LESSON")):
                    page_heading = line.lstrip("# ").strip()
                    break

            if page_heading and current_tokens and page_heading != current_heading:
                groups.append((current_heading, current_tokens))
                current_tokens = []
            if page_heading:
                current_heading = page_heading

            current_tokens.extend((word, page_num) for word in page_text.split())

        if current_tokens:
            groups.append((current_heading, current_tokens))

        chunks: List[Dict[str, Any]] = []
        chunk_idx = 0
        for heading, tokens in groups:
            start = 0
            while start < len(tokens):
                end = min(start + chunk_size_words, len(tokens))
                slice_tokens = tokens[start:end]
                chunk_text = " ".join(word for word, _ in slice_tokens)
                page_numbers = [page for _, page in slice_tokens]
                chunks.append({
                    "chunk_index": chunk_idx,
                    "page_start": min(page_numbers),
                    "page_end": max(page_numbers),
                    "heading_path": [heading] if heading else [],
                    "text": chunk_text,
                    "text_hash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                })
                chunk_idx += 1
                if end >= len(tokens):
                    break
                start = max(start + 1, end - max(0, overlap_words))

        return chunks


chunking_service = ChunkingService()
