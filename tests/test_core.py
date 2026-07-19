import base64
import json
import os
import unittest
from unittest.mock import patch

import server


class CoreTests(unittest.TestCase):
    @patch.dict(os.environ, {"CLOUDMUSIC_EXE": r"C:\Music\cloudmusic.exe"})
    def test_configured_executable_path_takes_priority(self):
        self.assertEqual(server._cloudmusic_exe(), server.Path(r"C:\Music\cloudmusic.exe"))

    def test_build_song_url_contains_only_expected_command(self):
        url = server._build_play_url("song", 123456)
        self.assertTrue(url.startswith("orpheus://"))
        payload = base64.b64decode(url.removeprefix("orpheus://")).decode("utf-8")
        self.assertEqual(json.loads(payload), {"type": "song", "id": "123456", "cmd": "play"})

    def test_build_playlist_url(self):
        url = server._build_play_url("playlist", 42)
        payload = base64.b64decode(url.removeprefix("orpheus://")).decode("utf-8")
        self.assertEqual(json.loads(payload)["type"], "playlist")

    def test_rejects_non_positive_id(self):
        with self.assertRaises(ValueError):
            server._build_play_url("song", 0)

    def test_open_rejects_other_protocols(self):
        with self.assertRaises(ValueError):
            server._open_play_url("https://example.com")

    @patch.object(server, "_search")
    @patch.object(server, "_open_play_url")
    def test_search_and_play_uses_numeric_result_id(self, open_play_url, search):
        search.return_value = [{"id": 123, "name": "Test", "artists": ["Artist"]}]
        result = server.search_and_play("Test", artist="Artist")
        self.assertTrue(result["success"])
        open_play_url.assert_called_once()
        called_url = open_play_url.call_args.args[0]
        self.assertTrue(called_url.startswith("orpheus://"))

    @patch.object(server, "_search")
    @patch.object(server, "_open_play_url")
    def test_ambiguous_artist_does_not_play(self, open_play_url, search):
        search.return_value = [
            {"id": 123, "name": "Test", "artists": ["Artist-", "Someone Else"]}
        ]
        result = server.search_and_play("Test", artist="Artist")
        self.assertFalse(result["success"])
        open_play_url.assert_not_called()

    def test_song_selection_allows_one_exact_normalized_artist(self):
        match = {"id": 123, "name": "晴 天", "artists": ["周杰伦"]}
        self.assertEqual(server._select_song_match([match], "晴天", "周杰伦"), match)


if __name__ == "__main__":
    unittest.main()
