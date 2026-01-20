from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import default_config_path, load_config, save_config
from .dice import roll_expression
from .openai_client import ChatClient, ChatMessage
from .tui_chat import run_chat_tui
from .tui_config import edit_config_tui


def _cmd_roll(args: argparse.Namespace) -> int:
    result = roll_expression(args.expression, seed=args.seed)
    print(result["text"])
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else default_config_path()
    cfg = load_config(path)

    if args.print_json:
        print(json.dumps(cfg.to_dict(), ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    updated = edit_config_tui(cfg, path=path)
    save_config(updated, path)
    print(f"saved: {path}")
    return 0


def _print_help_in_chat() -> None:
    print("commands: /roll EXPR, /config, /reset, /exit")


def _cmd_chat(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config) if args.config else None
    cfg = load_config(cfg_path)

    if not getattr(args, "plain", False):
        return run_chat_tui(cfg, share_roll=bool(args.share_roll), config_path=cfg_path)

    client = ChatClient(cfg)
    messages: list[ChatMessage] = []
    if cfg.chat.system_prompt.strip():
        messages.append(ChatMessage(role="system", content=cfg.chat.system_prompt))

    print("enter message. /exit to quit. /help for commands.")

    while True:
        try:
            user_in = input("you> ").strip()
        except EOFError:
            print("")
            break

        if not user_in:
            continue

        if user_in in {"/exit", "/quit"}:
            break
        if user_in in {"/help", "help", "?"}:
            _print_help_in_chat()
            continue

        if user_in.startswith("/reset"):
            messages = []
            if cfg.chat.system_prompt.strip():
                messages.append(ChatMessage(role="system", content=cfg.chat.system_prompt))
            print("(session reset)")
            continue

        if user_in.startswith("/config"):
            path = cfg_path or default_config_path()
            updated = edit_config_tui(cfg, path=path)
            save_config(updated, path)
            cfg = updated
            client = ChatClient(cfg)
            print(f"saved: {path}")
            continue

        if user_in.startswith("/roll"):
            expr = user_in[len("/roll") :].strip()
            if not expr:
                print("usage: /roll 2d6+1")
                continue
            result = roll_expression(expr)
            print(result["text"])
            if args.share_roll:
                messages.append(ChatMessage(role="user", content=result["text"]))
            continue

        messages.append(ChatMessage(role="user", content=user_in))

        try:
            assistant_text, new_messages = client.chat(messages)
        except Exception as e:
            print(f"error: {e}")
            continue

        messages = new_messages
        print(f"ai> {assistant_text}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trpgai")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_chat = sub.add_parser("chat", help="interactive chat")
    p_chat.add_argument("--config", help="config path")
    p_chat.add_argument(
        "--share-roll",
        action="store_true",
        help="when using /roll, also send the result to the model",
    )
    p_chat.add_argument(
        "--plain",
        action="store_true",
        help="use stdin/stdout instead of curses TUI",
    )
    p_chat.set_defaults(func=_cmd_chat)

    p_roll = sub.add_parser("roll", help="roll dice expression")
    p_roll.add_argument("expression")
    p_roll.add_argument("--seed", type=int)
    p_roll.set_defaults(func=_cmd_roll)

    p_cfg = sub.add_parser("config", help="edit config (TUI) or print json")
    p_cfg.add_argument("--path", help="config path")
    p_cfg.add_argument("--print-json", action="store_true")
    p_cfg.set_defaults(func=_cmd_config)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = build_parser()
    args = p.parse_args(argv)
    func = getattr(args, "func", None)
    if not func:
        p.print_help()
        return 2
    return int(func(args))
