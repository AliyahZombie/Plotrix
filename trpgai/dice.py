from __future__ import annotations

import random
from dataclasses import dataclass


class DiceSyntaxError(ValueError):
    pass


@dataclass(frozen=True)
class _IntTerm:
    value: int


@dataclass(frozen=True)
class _DiceTerm:
    count: int
    sides: int | str
    keep_drop: tuple[str, int] | None
    explode: bool


def _parse_positive_int(s: str, i: int) -> tuple[int | None, int]:
    j = i
    while j < len(s) and s[j].isdigit():
        j += 1
    if j == i:
        return None, i
    return int(s[i:j]), j


def _parse_term(s: str, i: int) -> tuple[_IntTerm | _DiceTerm, int]:
    n, i2 = _parse_positive_int(s, i)

    if i2 < len(s) and s[i2] in {"d", "D"}:
        count = n if n is not None else 1
        if count <= 0:
            raise DiceSyntaxError("dice count must be >= 1")
        i = i2 + 1

        if i >= len(s):
            raise DiceSyntaxError("missing dice sides")

        sides: int | str
        if s[i] == "%":
            sides = 100
            i += 1
        elif s[i] in {"f", "F"}:
            sides = "F"
            i += 1
        else:
            sides_n, i = _parse_positive_int(s, i)
            if sides_n is None:
                raise DiceSyntaxError("invalid dice sides")
            if sides_n <= 0:
                raise DiceSyntaxError("dice sides must be >= 1")
            sides = sides_n

        keep_drop: tuple[str, int] | None = None
        explode = False

        while i < len(s):
            if s[i] == "!":
                explode = True
                i += 1
                continue

            if i + 1 < len(s) and s[i : i + 2].lower() in {"kh", "kl", "dh", "dl"}:
                op = s[i : i + 2].lower()
                if keep_drop is not None:
                    raise DiceSyntaxError("only one of kh/kl/dh/dl is supported")
                i += 2
                k, i = _parse_positive_int(s, i)
                if k is None:
                    raise DiceSyntaxError(f"{op} requires a number")
                if k < 0:
                    raise DiceSyntaxError(f"{op} must be >= 0")
                keep_drop = (op, k)
                continue

            break

        return _DiceTerm(count=count, sides=sides, keep_drop=keep_drop, explode=explode), i

    if n is None:
        raise DiceSyntaxError("expected a number or dice term")
    return _IntTerm(value=n), i2


def _parse_expression(s: str) -> list[tuple[int, _IntTerm | _DiceTerm]]:
    s = "".join(ch for ch in s.strip() if not ch.isspace())
    if not s:
        raise DiceSyntaxError("empty expression")

    i = 0
    sign = 1
    parts: list[tuple[int, _IntTerm | _DiceTerm]] = []

    while i < len(s):
        if s[i] in {"+", "-"}:
            sign = 1 if s[i] == "+" else -1
            i += 1
            if i >= len(s):
                raise DiceSyntaxError("dangling operator")

        term, i = _parse_term(s, i)
        parts.append((sign, term))
        sign = 1

    return parts


def _eval_dice(term: _DiceTerm, rng: random.Random) -> tuple[list[int], list[int]]:
    rolls: list[int] = []
    max_rolls = 1000

    def roll_one() -> int:
        if term.sides == "F":
            return rng.choice([-1, 0, 1])
        return rng.randint(1, int(term.sides))

    for _ in range(term.count):
        r = roll_one()
        rolls.append(r)
        if term.explode and term.sides != "F":
            sides = int(term.sides)
            while r == sides and len(rolls) < max_rolls:
                r = roll_one()
                rolls.append(r)

    kept = list(rolls)

    if term.keep_drop is None:
        return rolls, kept

    op, k = term.keep_drop
    if k <= 0:
        return rolls, [] if op in {"kh", "kl"} else kept

    if k >= len(kept):
        return rolls, kept if op in {"kh", "kl"} else []

    sorted_rolls = sorted(kept)
    if op == "kh":
        kept_vals = sorted_rolls[-k:]
    elif op == "kl":
        kept_vals = sorted_rolls[:k]
    elif op == "dh":
        kept_vals = sorted_rolls[:-k]
    elif op == "dl":
        kept_vals = sorted_rolls[k:]
    else:
        raise DiceSyntaxError(f"unknown modifier: {op}")

    return rolls, kept_vals


def roll_expression(expression: str, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    parts = _parse_expression(expression)

    total = 0
    term_texts: list[str] = []
    details: list[dict] = []

    for sign, term in parts:
        if isinstance(term, _IntTerm):
            subtotal = sign * term.value
            total += subtotal
            term_texts.append(str(subtotal))
            details.append({"type": "int", "sign": sign, "value": term.value, "subtotal": subtotal})
            continue

        rolls, kept = _eval_dice(term, rng)
        subtotal = sign * sum(kept)
        total += subtotal

        if term.keep_drop is None:
            shown = "+".join(str(x) for x in rolls)
        else:
            shown = f"{rolls} -> {kept}"

        mod = ""
        if term.keep_drop is not None:
            mod += f"{term.keep_drop[0]}{term.keep_drop[1]}"
        if term.explode:
            mod += "!"

        dice_name = f"{term.count}d{term.sides}{mod}"
        term_texts.append(f"{sign:+d}({shown})" if sign < 0 else f"({shown})")

        details.append(
            {
                "type": "dice",
                "sign": sign,
                "count": term.count,
                "sides": term.sides,
                "explode": term.explode,
                "keep_drop": term.keep_drop,
                "rolls": rolls,
                "kept": kept,
                "subtotal": subtotal,
                "display": dice_name,
            }
        )

    expr_clean = "".join(ch for ch in expression.strip() if not ch.isspace())
    breakdown = " + ".join(term_texts).replace("+ -", "- ")
    text = f"{expr_clean} => {breakdown} = {total}"

    return {"expr": expr_clean, "total": total, "terms": details, "text": text}
