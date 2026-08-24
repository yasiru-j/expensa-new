import io

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader

MAX_DIMENSION = 1600
JPEG_QUALITY = 85

_SIGNATURES: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF-": "application/pdf",
}


class UnsupportedFileTypeError(ValueError):
    pass


def sniff_content_type(data: bytes) -> str:
    """Identifies the file type from its magic bytes. A client-declared
    Content-Type header is trivial to spoof, so it's never trusted here."""
    for signature, content_type in _SIGNATURES.items():
        if data.startswith(signature):
            return content_type
    raise UnsupportedFileTypeError(
        "Unsupported file type. Only JPEG, PNG, and single-page PDF are accepted."
    )


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def render_pdf_first_page(pdf_bytes: bytes) -> tuple[bytes, str]:
    """Renders page 1 of a PDF to a PNG for the vision model call."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[0]
        bitmap = page.render(scale=2.0)
        pil_image = bitmap.to_pil()
    finally:
        pdf.close()

    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    return buffer.getvalue(), "image/png"


def downscale_image(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Downscales to a max dimension and re-encodes as JPEG, to cut OpenAI token
    cost without meaningfully hurting legibility (TRD §5.2). The ORIGINAL bytes
    are what get stored in MinIO — this is only ever used for the model call."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        return buffer.getvalue(), "image/jpeg"
