import hashlib
import re
from typing import List, Set, Tuple


class DuplicateChecker:
    @staticmethod
    def normalize_text(text: str) -> str:
        """Strip punctuation, whitespace, and convert to lower case for fingerprinting."""
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        return " ".join(cleaned.split())

    @classmethod
    def generate_fingerprint(cls, text: str, source_ref: str = "") -> str:
        """Generates SHA256 duplicate fingerprint from normalized content and source citation."""
        norm_text = cls.normalize_text(text)
        norm_ref = cls.normalize_text(source_ref)
        combined = f"{norm_text}|{norm_ref}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @classmethod
    def check_duplicate(cls, new_fingerprint: str, existing_fingerprints: Set[str]) -> bool:
        """Returns True if the exact normalized content already exists."""
        return new_fingerprint in existing_fingerprints

    @classmethod
    def calculate_jaccard_similarity(cls, text_a: str, text_b: str) -> float:
        """Token-level Jaccard similarity for near-duplicate detection."""
        words_a = set(cls.normalize_text(text_a).split())
        words_b = set(cls.normalize_text(text_b).split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a.intersection(words_b)
        union = words_a.union(words_b)
        return len(intersection) / len(union)


duplicate_checker = DuplicateChecker()
