"""The interface's texts are one object per language; a key written twice silently replaces the first."""

import re
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent / "web" / "app.js").read_text()


def top_level_keys(block):
    """Keys directly inside an object literal given without its outer braces; nested objects and strings are skipped."""
    keys, depth, i, expect_key = [], 0, 0, True
    while i < len(block):
        ch = block[i]
        if ch in "\"'`":
            end = i + 1
            while block[end] != ch:
                end += 2 if block[end] == "\\" else 1
            if depth == 0 and expect_key and re.match(r"\s*:", block[end + 1:]):
                keys.append(block[i + 1:end])
            i, expect_key = end + 1, False
            continue
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        elif depth == 0 and ch == ",":
            expect_key = True
        elif depth == 0 and expect_key and (ch.isalpha() or ch == "_"):
            word = re.match(r"\w+", block[i:]).group()
            if re.match(r"\s*:", block[i + len(word):]):
                keys.append(word)
            i, expect_key = i + len(word), False
            continue
        i += 1
    return keys


class Texts(unittest.TestCase):
    def blocks(self):
        start = SCRIPT.index("const STRINGS = {")
        english = SCRIPT.index("  en: {", start) + len("  en: {")
        german = SCRIPT.index("\n  de: {", english)
        end = SCRIPT.index("\n};", german)
        return SCRIPT[english:SCRIPT.rindex("}", english, german)], SCRIPT[german + len("\n  de: {"):SCRIPT.rindex("}", german, end)]

    def test_no_key_twice(self):
        for block in self.blocks():
            keys = top_level_keys(block)
            self.assertGreater(len(keys), 200)
            self.assertEqual(sorted(k for k in set(keys) if keys.count(k) > 1), [])

    def test_both_languages_have_the_same_keys(self):
        english, german = (set(top_level_keys(block)) for block in self.blocks())
        self.assertEqual(sorted(english ^ german), [])
