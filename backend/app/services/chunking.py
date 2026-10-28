import hashlib
from typing import List, Dict, Any

class ChunkingService:
    def create_chunks(self, pages: List[Dict[str, Any]], chunk_size_words: int = 250, overlap_words: int = 40) -> List[Dict[str, Any]]:
        """
        Creates semantic chunks preserving page boundaries and heading paths.
        Each chunk is guaranteed to have page_start, page_end, text, text_hash, and chunk_index.
        """
        chunks: List[Dict[str, Any]] = []
        chunk_idx = 0

        current_words: List[str] = []
        current_page_start = 1
        current_page_end = 1
        current_headings: List[str] = []

        for p in pages:
            page_num = p["page_number"]
            page_text = p["text"]
            
            # Simple header detection (e.g. lines starting with #, Chapter, Unit, Section)
            lines = page_text.splitlines()
            for line in lines:
                l = line.strip()
                if l.startswith(("#", "Chapter", "Unit", "Section", "LESSON")):
                    current_headings = [l.lstrip("# ").strip()]

            words = page_text.split()
            if not words:
                continue

            # Process words on this page
            i = 0
            while i < len(words):
                if not current_words:
                    current_page_start = page_num
                
                needed = chunk_size_words - len(current_words)
                slice_words = words[i:i + needed]
                current_words.extend(slice_words)
                current_page_end = page_num
                i += len(slice_words)

                if len(current_words) >= chunk_size_words:
                    chunk_text = " ".join(current_words)
                    thash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    chunks.append({
                        "chunk_index": chunk_idx,
                        "page_start": current_page_start,
                        "page_end": current_page_end,
                        "heading_path": list(current_headings),
                        "text": chunk_text,
                        "text_hash": thash
                    })
                    chunk_idx += 1
                    # Keep overlap for continuity
                    current_words = current_words[-overlap_words:] if overlap_words > 0 else []
                    current_page_start = page_num

        # Residual chunk
        if current_words:
            chunk_text = " ".join(current_words)
            thash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            chunks.append({
                "chunk_index": chunk_idx,
                "page_start": current_page_start,
                "page_end": current_page_end,
                "heading_path": list(current_headings),
                "text": chunk_text,
                "text_hash": thash
            })

        return chunks

chunking_service = ChunkingService()
