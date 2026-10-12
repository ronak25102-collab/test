"""Bounded comparison of republished text; issuer-origin grouping remains mandatory."""
import re


def text_fingerprint(text):
    words = re.findall(r"\w+", text[:100000].lower())
    return {tuple(words[i:i + 5]) for i in range(0, max(0, len(words) - 4), 3)}


def near_duplicate(left, right):
    a, b = text_fingerprint(left), text_fingerprint(right)
    return bool(a and b) and len(a & b) / len(a | b) >= .9
