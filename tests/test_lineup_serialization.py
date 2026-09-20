import datetime
import unittest
from types import SimpleNamespace

from espn_fantasy_server import is_starting_slot, serialize_box_player


def make_player(**overrides):
    values = {
        "name": "Test Player",
        "position": "WR",
        "slot_position": "WR",
        "proTeam": "BUF",
        "pro_opponent": "MIA",
        "points": 12.3,
        "projected_points": 14.5,
        "game_date": datetime.datetime.now() + datetime.timedelta(hours=1),
        "game_played": 0,
        "on_bye_week": False,
        "active_status": "active",
        "injuryStatus": "ACTIVE",
        "injured": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class LineupSerializationTests(unittest.TestCase):
    def test_starting_slots_exclude_bench_ir_and_free_agents(self):
        self.assertTrue(is_starting_slot("WR"))
        self.assertTrue(is_starting_slot("RB/WR/TE"))
        self.assertFalse(is_starting_slot("BE"))
        self.assertFalse(is_starting_slot("IR"))
        self.assertFalse(is_starting_slot("ER"))
        self.assertFalse(is_starting_slot("FA"))
        self.assertFalse(is_starting_slot(None))

    def test_serialize_box_player_marks_future_starter_unlocked(self):
        result = serialize_box_player(make_player())

        self.assertEqual(result["lineup_slot"], "WR")
        self.assertTrue(result["is_starter"])
        self.assertFalse(result["locked"])
        self.assertEqual(result["projected_points"], 14.5)
        self.assertIsNotNone(result["game_date"])

    def test_serialize_box_player_marks_started_bench_player_locked(self):
        player = make_player(
            slot_position="BE",
            game_date=datetime.datetime.now() - datetime.timedelta(minutes=1),
        )

        result = serialize_box_player(player)

        self.assertFalse(result["is_starter"])
        self.assertTrue(result["locked"])

    def test_serialize_box_player_handles_bye_without_game_date(self):
        player = make_player(game_date=None, on_bye_week=True, active_status="bye")

        result = serialize_box_player(player)

        self.assertFalse(result["locked"])
        self.assertTrue(result["on_bye_week"])
        self.assertIsNone(result["game_date"])


if __name__ == "__main__":
    unittest.main()
