import unittest

from trpgai.tui_chat import _format_tool_call, _format_tool_result


class TestToolCards(unittest.TestCase):
    def test_format_tool_call_json_args(self) -> None:
        call = {
            "id": "abc",
            "type": "function",
            "function": {"name": "roll_dice", "arguments": '{"expression":"2d6+1"}'},
        }
        s = _format_tool_call(call)
        self.assertIn("CALL roll_dice", s)
        self.assertIn("id=abc", s)
        self.assertIn("expression", s)

    def test_format_tool_result_prefers_text(self) -> None:
        s = _format_tool_result("abc", '{"text":"2d6+1 => (1+2)+1 = 4","total":4}')
        self.assertIn("RESULT", s)
        self.assertIn("id=abc", s)
        self.assertIn("2d6+1", s)

    def test_format_tool_result_error(self) -> None:
        s = _format_tool_result("abc", '{"error":"bad expr"}')
        self.assertIn("error", s)


if __name__ == "__main__":
    unittest.main()
