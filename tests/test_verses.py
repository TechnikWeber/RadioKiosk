import datetime
import io
import unittest
import zipfile
from pathlib import Path

from radiokiosk.verses import Verses, parse_losungen, verse_index

SAMPLE = (Path(__file__).parent / "fixtures" / "losungen-sample.xml").read_bytes()


class VerseTest(unittest.TestCase):
    def test_the_same_verse_as_the_widget(self):
        # the values the Bible Verse Widget pins its own implementations to
        self.assertEqual(verse_index(datetime.date(2026, 1, 1), 1000), 815)
        self.assertEqual(verse_index(datetime.date(2026, 9, 1), 1000), 641)
        self.assertEqual(verse_index(datetime.date(2027, 1, 1), 1000), 987)

    def test_no_verse_twice_in_a_year(self):
        seen = [verse_index(datetime.date(2028, 1, 1) + datetime.timedelta(days=i), 1000) for i in range(366)]
        self.assertEqual(len(set(seen)), 366)

    def test_the_list_in_the_chosen_translation(self):
        verses = Verses({"verse": {"translation": "de"}})
        today = verses.today("en", datetime.date(2026, 1, 1))
        self.assertEqual((today["used"], len(today["texts"]), today["credit"]), ("list", 1, "Lutherbibel 1912"))
        english = Verses({}).today("en", datetime.date(2026, 1, 1))
        self.assertEqual(english["credit"], "World English Bible")
        self.assertNotEqual(english["texts"][0]["text"], today["texts"][0]["text"])
        self.assertEqual(Verses({}).today("fr")["credit"], "World English Bible")   # no French list: English

    def test_a_year_file_as_xml_and_as_the_zip_it_comes_in(self):
        days = parse_losungen(SAMPLE)
        self.assertEqual(days[0]["date"], "2026-01-01")
        self.assertEqual(days[1]["losung"], {"text": "Der HERR ist mein Hirte; mir wird nichts mangeln.", "ref": "Ps 23,1"})
        packed = io.BytesIO()
        with zipfile.ZipFile(packed, "w") as archive:
            archive.writestr("Losungen Free 2026.xml", SAMPLE)
        self.assertEqual(parse_losungen(packed.getvalue()), days)
        for wrong in (b"<html></html>", b"not xml"):
            with self.assertRaises(ValueError):
                parse_losungen(wrong)

    def test_without_the_years_file_the_list_stands_in(self):
        verses = Verses({"verse": {"source": "losungen"}})
        verses.losungen[1999] = {}   # looked up, nothing there
        today = verses.today("de", datetime.date(1999, 5, 1))
        self.assertEqual((today["used"], today["missing"]), ("list", True))
