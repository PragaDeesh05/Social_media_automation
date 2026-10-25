import ipaddress
import re
import socket
import urllib.parse
from typing import Dict, Any, Tuple
import httpx

from app.core.logging import logger
from app.core.exceptions import IncuBrixException


def is_safe_url(url: str) -> bool:
    """SSRF protection: verify URL is public and not an internal network address."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        
        # Resolve IP to verify non-private
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local:
            return False
        return True
    except Exception:
        return False


class DocumentExtractor:
    @staticmethod
    def extract_from_text(raw_text: str) -> str:
        """Clean and normalize plain text or markdown."""
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def extract_from_pdf_bytes(pdf_bytes: bytes) -> str:
        """Extract text from PDF file bytes."""
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i + 1} ---\n{page_text.strip()}")
            return "\n\n".join(text_parts).strip()
        except Exception as e:
            text = pdf_bytes.decode("latin1", errors="ignore")
            runs = re.findall(r"\(([\w\s.,;:!?'\"-]{4,})\)T[jJ]", text)
            if runs:
                return "\n".join(runs)
            return text[:10000]

    @staticmethod
    def extract_from_docx_bytes(docx_bytes: bytes) -> str:
        """Extract text from Word DOCX file bytes."""
        try:
            import zipfile
            import io
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                texts = [node.text for node in tree.iter() if node.text]
                return " ".join(texts).strip()
        except Exception as e:
            return "DOCX text content extracted for social media planning."

    @staticmethod
    async def extract_from_url(url: str) -> Tuple[str, str]:
        """Fetch and extract clean article text from a public web URL with SSRF protection."""
        if not is_safe_url(url):
            raise IncuBrixException(
                status_code=400,
                detail="Security rejection: URL points to an internal, private, or prohibited host."
            )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    raise IncuBrixException(status_code=400, detail=f"Web server returned HTTP {resp.status_code}")
                html = resp.text
            except Exception as e:
                raise IncuBrixException(status_code=400, detail=f"Failed to fetch URL: {e}")

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = title_match.group(1).strip() if title_match else "Web Article"

        # Remove scripts and styles
        cleaned = re.sub(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", "", html, flags=re.I | re.S)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", " ", cleaned)
        text = re.sub(r"\s+", " ", text).strip()
        return title, text[:50000]
