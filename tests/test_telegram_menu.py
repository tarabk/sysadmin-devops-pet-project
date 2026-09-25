import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bot", ROOT / "deploy/telegram-bot/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)


class FakePrometheus:
    def __init__(self, value=50, stamp=1000):
        self.value, self.stamp = value, stamp
        self.calls = []

    def query(self, expression, now):
        self.calls.append(expression)
        if self.value is None:
            return []
        return [{"metric": {}, "value": [now, str(self.stamp if expression.startswith("timestamp(") else self.value)]}]


class FakeTelegram:
    def __init__(self):
        self.calls = []

    def call(self, method, payload):
        self.calls.append((method, payload))


def message(chat=123, kind="private", sender=None, text="/menu"):
    return {"message_id": 50, "chat": {"id": chat, "type": kind},
            "from": {"id": chat if sender is None else sender}, "text": text}


class Tests(unittest.TestCase):
    def snap(self, value=50, stamp=1000):
        return bot.Snapshot(FakePrometheus(value, stamp), 1000)

    def test_home_categories_and_no_queries(self):
        prom = FakePrometheus()
        text, keys = bot.render("home", bot.Snapshot(prom, 1000))
        self.assertEqual([b["text"] for row in keys["inline_keyboard"] for b in row], ["VM", "Containers", "Website"])
        self.assertFalse(prom.calls)

    def test_all_menu_routes_render_and_fit_callback_limit(self):
        todo, visited = ["home"], set()
        while todo:
            route = todo.pop()
            if route in visited:
                continue
            visited.add(route)
            text, keys = bot.render(route, self.snap())
            self.assertTrue(text)
            self.assertLess(len(text), 4096)
            for row in keys["inline_keyboard"]:
                for button in row:
                    self.assertLessEqual(len(button["callback_data"].encode()), 64)
                    todo.append(button["callback_data"])
        self.assertGreaterEqual(len(visited), 55)

    def test_missing_metric_is_not_zero(self):
        text, _ = bot.render("vm:cpu", self.snap(None))
        self.assertIn("Usage: No data", text)
        self.assertNotIn("0.0%", text)

    def test_stale_source_is_not_healthy(self):
        text, _ = bot.render("s:https", self.snap(1, 800))
        self.assertIn("No recent data", text)
        self.assertNotIn("Status: OK", text)

    def test_nan_is_not_zero(self):
        text, _ = bot.render("vm:memory", self.snap(float("nan")))
        self.assertIn("No data", text)

    def test_false_probe_is_failed(self):
        text, _ = bot.render("s:ready", self.snap(0))
        self.assertIn("Status: FAILED", text)

    def test_local_scope_is_visible(self):
        text, _ = bot.render("s:https", self.snap(1))
        self.assertIn("loopback", text)

    def test_unknown_container_cannot_be_injected_into_promql(self):
        snap = self.snap()
        text, _ = bot.render('c:app:bad"}:cpu', snap)
        self.assertIn("Taskboard Monitoring", text)
        self.assertEqual(snap.prometheus.calls, [])

    def test_unauthorized_private_chat_is_ignored(self):
        tg = FakeTelegram()
        bot.Bot(tg, FakePrometheus(), 123).handle({"message": message(999)})
        self.assertEqual(tg.calls, [])

    def test_groups_are_rejected(self):
        tg = FakeTelegram()
        bot.Bot(tg, FakePrometheus(), 123).handle({"message": message(123, "group")})
        self.assertEqual(tg.calls, [])

    def test_sender_must_match_allowed_user(self):
        tg = FakeTelegram()
        bot.Bot(tg, FakePrometheus(), 123).handle({"message": message(sender=999)})
        self.assertFalse(tg.calls)

    def test_callback_edits_existing_message(self):
        tg = FakeTelegram()
        client = bot.Bot(tg, FakePrometheus(), 123)
        client.handle({"callback_query": {"id": "q1", "from": {"id": 123}, "message": message(), "data": "vm"}})
        self.assertEqual([c[0] for c in tg.calls], ["answerCallbackQuery", "editMessageText"])
        self.assertEqual(tg.calls[-1][1]["message_id"], 50)

    def test_unauthorized_callback_exposes_no_metrics(self):
        tg, prom = FakeTelegram(), FakePrometheus()
        bot.Bot(tg, prom, 123).handle({"callback_query": {"id": "q1", "from": {"id": 999}, "message": message(999), "data": "vm:cpu"}})
        self.assertEqual(tg.calls[0][1]["text"], "Access denied.")
        self.assertFalse(prom.calls)

    def test_prometheus_failure_gets_recoverable_screen(self):
        tg, prom = FakeTelegram(), FakePrometheus()
        with patch.object(prom, "query", side_effect=bot.ServiceError("test")):
            bot.Bot(tg, prom, 123).handle({"callback_query": {"id": "q1", "from": {"id": 123}, "message": message(), "data": "vm:cpu"}})
        self.assertIn("temporarily unavailable", tg.calls[-1][1]["text"])
        self.assertEqual(tg.calls[-1][1]["reply_markup"]["inline_keyboard"][0][0]["text"], "Refresh")

    def test_unlimited_container_has_no_invented_percentage(self):
        text, _ = bot.render("c:app:backend:cpu", self.snap(None))
        self.assertIn("positive resource limit", text)

    def test_config_rejects_token_prefix_and_group_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = pathlib.Path(tmp) / "token"
            cfg = pathlib.Path(tmp) / "config.json"
            token.write_text("TOKEN=123:" + "x" * 32)
            data = {"allowed_chat_id": 123, "prometheus_url": "http://127.0.0.1:9090", "token_file": str(token)}
            cfg.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                bot.load_config(cfg)
            token.write_text("123:" + "x" * 32)
            data["allowed_chat_id"] = -123
            cfg.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                bot.load_config(cfg)

    def test_metrics_are_cached_per_screen(self):
        snap = self.snap()
        snap.metric("foo")
        snap.metric("foo")
        self.assertEqual(len(snap.prometheus.calls), 2)

    def test_timestamp_must_be_recent(self):
        self.assertIsNone(self.snap(10, 800).metric("foo"))
        self.assertEqual(self.snap(10, 950).metric("foo"), 10)


if __name__ == "__main__":
    unittest.main()
