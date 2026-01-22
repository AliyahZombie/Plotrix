import re
import unittest

from plotrix.mcp_client import _mcp_tool_public_name


class TestMcpToolNaming(unittest.TestCase):
    def test_name_charset_and_length(self) -> None:
        name = _mcp_tool_public_name("server.one", "tool/read.file")
        self.assertLessEqual(len(name), 64)
        self.assertRegex(name, re.compile(r"^[a-zA-Z0-9_-]{1,64}$"))

    def test_name_stable_for_long_inputs(self) -> None:
        server = "s" * 80
        tool = "t" * 80
        a = _mcp_tool_public_name(server, tool)
        b = _mcp_tool_public_name(server, tool)
        self.assertEqual(a, b)
        self.assertLessEqual(len(a), 64)


if __name__ == "__main__":
    unittest.main()
