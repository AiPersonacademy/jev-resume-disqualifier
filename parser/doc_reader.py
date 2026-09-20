"""
Document Reader for Resume Ingestion.
Supports PDF (via pypdf), DOCX (via python-docx), TXT, and Markdown files.
Extracts clean, normalized text while preserving paragraph structure.
"""

import io
from pathlib import Path
from typing import Dict, Any, Optional
import pypdf
import docx


class DocumentReader:
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

    @classmethod
    def read_file(cls, file_path: str | Path) -> Dict[str, Any]:
        """Reads a file from disk and returns parsed text and metadata."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format '{ext}'. Supported: {cls.SUPPORTED_EXTENSIONS}")

        with open(path, "rb") as f:
            content = f.read()

        return cls.read_bytes(content, filename=path.name, ext=ext)

    @classmethod
    def read_bytes(cls, data: bytes, filename: str = "document", ext: Optional[str] = None) -> Dict[str, Any]:
        """Parses raw bytes of a document into normalized text."""
        if ext is None:
            ext = Path(filename).suffix.lower() if "." in filename else ".txt"

        ext = ext.lower()
        text = ""
        page_count = 1

        if ext == ".pdf":
            text, page_count = cls._parse_pdf(data)
        elif ext == ".docx":
            text, page_count = cls._parse_docx(data)
        elif ext in {".txt", ".md"}:
            text = cls._parse_text(data)
            page_count = 1
        else:
            # Fallback to UTF-8 decoding
            text = data.decode("utf-8", errors="replace")

        cleaned_text = cls._clean_text(text)
        return {
            "filename": filename,
            "extension": ext,
            "page_count": page_count,
            "raw_text": cleaned_text,
            "character_count": len(cleaned_text),
            "word_count": len(cleaned_text.split())
        }

    @staticmethod
    def _parse_pdf(data: bytes) -> tuple[str, int]:
        """Extracts text from PDF bytes using pypdf."""
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages_text = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            pages_text.append(page_text.strip())
        return "\n\n".join(pages_text), len(reader.pages)

    @staticmethod
    def _parse_docx(data: bytes) -> tuple[str, int]:
        """Extracts text from DOCX bytes using python-docx."""
        doc = docx.Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        
        # Also extract text from tables
        table_texts = []
        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    table_texts.append(" | ".join(row_cells))

        full_text = "\n".join(paragraphs)
        if table_texts:
            full_text += "\n\n" + "\n".join(table_texts)

        return full_text, 1

    @staticmethod
    def _parse_text(data: bytes) -> str:
        """Parses plain text with graceful encoding detection."""
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalizes whitespace and common formatting artifacts."""
        lines = text.splitlines()
        normalized_lines = []
        for line in lines:
            line_str = " ".join(line.split())
            if line_str:
                normalized_lines.append(line_str)
        return "\n".join(normalized_lines)
