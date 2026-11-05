
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


def extract_text(file_content: bytes, file_name: str) -> str:
    """
    Extract text from PDF, DOCX or TXT files.
    """

    extension = Path(file_name).suffix.lower()

    if extension == ".pdf":
        reader = PdfReader(BytesIO(file_content))

        pages = []

        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)

        extracted_text = "\n\n".join(pages)

    elif extension == ".docx":
        document = Document(BytesIO(file_content))

        paragraphs = [
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        extracted_text = "\n\n".join(paragraphs)

    elif extension == ".txt":
        extracted_text = file_content.decode("utf-8-sig")

    else:
        raise ValueError("Unsupported document format")

    extracted_text = extracted_text.strip()

    if not extracted_text:
        raise ValueError(
            "No readable text found. The document may be empty or scanned."
        )

    return extracted_text
