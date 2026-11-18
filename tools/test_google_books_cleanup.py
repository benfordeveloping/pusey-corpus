#!/usr/bin/env python3
"""Regression tests for modern Google Books notice removal (reader only)."""
from build import strip_google_books_front_matter

sample = (
    "Google\n\n"
    "This is a digital copy of a book that was preserved for generations "
    "on library shelves before it was carefully scanned by Google.\n\n"
    "Usage guidelines\n\n"
    "About Google Book Search\n\n"
    "Google helps readers discover the world's books.\n\n"
    "at |http: //books .google .com/I\n\n"
    "REMARKS ON THE PROSPECTIVE BENEFITS\n"
)
clean = strip_google_books_front_matter(sample)
assert "This is a digital copy" not in clean, clean[:150]
assert "About Google Book Search" not in clean
assert "REMARKS ON THE PROSPECTIVE BENEFITS" in clean
assert not clean.lstrip().startswith("Google")
# A mention of Google without the complete boilerplate must not be deleted.
ambiguous = "This is a digital copy of a book\nPreface by Pusey\n"
assert strip_google_books_front_matter(ambiguous) == ambiguous
# Historical material after the scanning notice must remain intact.
assert strip_google_books_front_matter("Original preface by Pusey") == "Original preface by Pusey"
print("Google Books front-matter filter tests passed")
