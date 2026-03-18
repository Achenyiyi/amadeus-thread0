import unittest

from amadeus_thread0.graph_parts.response_finalize import _NATURAL_REWRITE_ISSUE_KEYS


class ResponseFinalizeTests(unittest.TestCase):
    def test_natural_rewrite_triggers_on_brevity_and_template_drift(self):
        self.assertTrue(
            {"visible_template", "lecture_list", "overexplained"}.issubset(_NATURAL_REWRITE_ISSUE_KEYS)
        )


if __name__ == "__main__":
    unittest.main()
