import unittest
from unittest import mock

from radiokiosk import smarthome
from radiokiosk.smarthome import SmartHome, pick


class Fields(unittest.TestCase):
    def test_a_value_is_picked_out_of_json_by_its_path(self):
        answer = '{"state": "21.456", "attributes": {"temperature": 21.456, "list": [{"on": true}]}}'
        self.assertEqual(pick(answer, "state"), "21.456")
        self.assertEqual(pick(answer, "attributes.temperature"), "21.46")
        self.assertEqual(pick(answer, "attributes.list.0.on"), "true")
        self.assertEqual(pick("  ON \n", ""), "ON")
        with self.assertRaises(RuntimeError):
            pick(answer, "attributes.humidity")


class Entries(unittest.TestCase):
    def setUp(self):
        self.kept = {}
        for name, stand_in in (("load_json", lambda name, default: default), ("save_json", self.kept.__setitem__)):
            patch = mock.patch.object(smarthome, name, stand_in)
            patch.start()
            self.addCleanup(patch.stop)
        self.home = SmartHome()

    def test_name_and_address_are_checked(self):
        for entry in ({"name": "", "url": "http://x"}, {"name": "Door", "url": "ftp://x"}, {"name": "Door", "url": "garage"}):
            with self.assertRaises(ValueError):
                self.home.save(entry)

    def test_the_token_is_kept_when_an_entry_is_changed_and_never_listed(self):
        self.home.save({"kind": "switch", "name": "Door", "url": "http://ha.local/api/webhook/door", "token": "secret", "confirm": True})
        item = self.home.items[0]
        self.home.save({"id": item["id"], "kind": "switch", "name": "Garage", "url": item["url"]})
        self.assertEqual((self.home.items[0]["name"], self.home.items[0]["token"], len(self.home.items)), ("Garage", "secret", 1))
        import asyncio
        listed = asyncio.run(self.home.listing())[0]
        self.assertNotIn("token", listed)
        self.assertTrue(listed["has_token"])


if __name__ == "__main__":
    unittest.main()
