import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from interviewer.config import (  # noqa: E402
    DEFAULT_MODELS,
    INTERVIEWS,
    INTERVIEWS_DIR,
    ConfigError,
    model_for,
    validate_interview,
)


class ConfigTests(unittest.TestCase):
    def test_shipped_interviews_load(self):
        self.assertEqual(set(INTERVIEWS), {"HOMELESS_BERLIN", "STOCK_MARKET"})
        stock = INTERVIEWS["STOCK_MARKET"]
        self.assertTrue(stock["first_question"].startswith("I am interested in learning more about why you currently do not own"))
        self.assertEqual(len(stock["interview_plan"]), 4)
        self.assertEqual(stock["interview_plan"][0]["length"], 6)
        self.assertTrue(stock["moderate_answers"])
        # Shipped interviews pin no model, so every provider uses its own default.
        for task in ("summary", "transition", "probe", "moderator"):
            self.assertNotIn("model", stock[task])
        self.assertIn("{current_topic_history}", stock["probe"]["prompt"])
        self.assertIn("not investing in the stock market", stock["probe"]["prompt"])

        berlin = INTERVIEWS["HOMELESS_BERLIN"]
        self.assertFalse(berlin["moderate_answers"])
        self.assertEqual(len(berlin["interview_plan"]), 3)
        self.assertIn("dag", berlin)
        self.assertEqual(berlin["dag"]["max_tokens"], 1000)
        self.assertTrue(berlin["end_of_interview_message"].endswith("---END---"))

    def test_template_is_ignored_but_valid(self):
        self.assertFalse(any(name.startswith("_") for name in INTERVIEWS))
        template = INTERVIEWS_DIR / "_TEMPLATE.toml"
        self.assertTrue(template.is_file())
        data = tomllib.loads(template.read_text(encoding="utf-8"))
        validated = validate_interview("_TEMPLATE.toml", data)
        self.assertEqual(len(validated["interview_plan"]), 2)
        self.assertIn("{question}", validated["moderator"]["prompt"])
        self.assertIn("{next_interview_topic}", validated["transition"]["prompt"])

    def test_invalid_config_names_the_file_and_field(self):
        with self.assertRaises(ConfigError) as caught:
            validate_interview("broken.toml", {"first_question": "Hello"})
        message = str(caught.exception)
        self.assertIn("broken.toml", message)
        self.assertIn("termination_message", message)

        with self.assertRaises(ConfigError) as caught:
            validate_interview(
                "lengths.toml",
                {
                    "first_question": "Hello",
                    "termination_message": "Stop.---END---",
                    "flagged_message": "Flagged.---END---",
                    "off_topic_message": "Off topic.",
                    "end_of_interview_message": "Thanks.---END---",
                    "interview_plan": [{"topic": "Only topic", "length": 0}],
                    "probe": {"prompt": "Ask about {current_topic}."},
                },
            )
        self.assertIn("lengths.toml", str(caught.exception))
        self.assertIn("interview_plan[0].length", str(caught.exception))

    def test_model_resolution_order(self):
        self.assertEqual(model_for({"model": "gpt-4o-mini"}, "gemini", "override"), "override")
        self.assertEqual(model_for({"model": "gpt-4o-mini"}, "gemini", None), "gpt-4o-mini")
        self.assertEqual(model_for({}, "openai", None), DEFAULT_MODELS["openai"])
        self.assertEqual(model_for({}, "gemini", None), "gemini-2.5-flash-lite")
        self.assertEqual(model_for({}, "claude", None), "claude-haiku-5-5")


if __name__ == "__main__":
    unittest.main()
