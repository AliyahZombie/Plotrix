import unittest

from plotrix.dice import DiceSyntaxError, roll_expression


class TestDice(unittest.TestCase):
    def test_roll_simple_seeded(self) -> None:
        r = roll_expression("2d6+1", seed=123)
        self.assertEqual(r["expr"], "2d6+1")
        self.assertIsInstance(r["total"], int)
        self.assertIn("=>", r["text"])

    def test_roll_keep_highest(self) -> None:
        r = roll_expression("4d6kh3", seed=1)
        self.assertEqual(r["expr"], "4d6kh3")
        self.assertEqual(len(r["terms"]), 1)
        term = r["terms"][0]
        self.assertEqual(term["type"], "dice")
        self.assertEqual(term["keep_drop"], ("kh", 3))
        self.assertLessEqual(len(term["kept"]), len(term["rolls"]))

    def test_bad_syntax(self) -> None:
        with self.assertRaises(DiceSyntaxError):
            roll_expression("", seed=0)
        with self.assertRaises(DiceSyntaxError):
            roll_expression("d", seed=0)
        with self.assertRaises(DiceSyntaxError):
            roll_expression("2d0", seed=0)


if __name__ == "__main__":
    unittest.main()
