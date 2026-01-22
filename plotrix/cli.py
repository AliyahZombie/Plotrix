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
        print(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    updated = edit_config_tui(cfg, path=path)
    save_config(updated, path)
    print(f"已保存: {path}")
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    # Web UI is an optional extra.
    try:
        from .web.server import serve
    except Exception:
        print("Web UI 依赖未安装。请运行: pip install 'plotrix[web]'")
        return 2

    cfg_path = Path(args.config) if args.config else None
    return int(
        serve(
            host=str(args.host),
            port=int(args.port),
            open_browser=not bool(args.no_open),
            config_path=cfg_path,
        )
    )


def _print_help_in_chat() -> None:
    print("命令：/roll 表达式, /config, /reset, /exit")


def _cmd_chat(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config) if args.config else None
    cfg = load_config(cfg_path)

    if not getattr(args, "plain", False):
        return run_chat_tui(cfg, share_roll=bool(args.share_roll), config_path=cfg_path)

    client = ChatClient(cfg)
    messages: list[ChatMessage] = []
    if cfg.chat.system_prompt.strip():
        messages.append(ChatMessage(role="system", content=cfg.chat.system_prompt))

    print("输入消息。/exit 退出。/help 查看命令。")

    while True:
        try:
            user_in = input("你> ").strip()
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
                messages.append(
                    ChatMessage(role="system", content=cfg.chat.system_prompt)
                )
            print("（会话已重置）")
            continue

        if user_in.startswith("/config"):
            path = cfg_path or default_config_path()
            updated = edit_config_tui(cfg, path=path)
            save_config(updated, path)
            cfg = updated
            client = ChatClient(cfg)
            print(f"已保存: {path}")
            continue

        if user_in.startswith("/roll"):
            expr = user_in[len("/roll") :].strip()
            if not expr:
                print("用法：/roll 2d6+1")
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
            print(f"错误: {e}")
            continue

        messages = new_messages
        print(f"助手> {assistant_text}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    # Let argparse pick up the actual invoked command name.
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_chat = sub.add_parser("chat", help="交互式聊天")
    p_chat.add_argument("--config", help="配置文件路径")
    p_chat.add_argument(
        "--share-roll",
        action="store_true",
        help="使用 /roll 时，将结果一并发送给模型",
    )
    p_chat.add_argument(
        "--plain",
        action="store_true",
        help="使用 stdin/stdout（不启用 curses TUI）",
    )
    p_chat.set_defaults(func=_cmd_chat)

    p_roll = sub.add_parser("roll", help="掷骰（表达式）")
    p_roll.add_argument("expression")
    p_roll.add_argument("--seed", type=int)
    p_roll.set_defaults(func=_cmd_roll)

    p_cfg = sub.add_parser("config", help="编辑配置（TUI）或输出 JSON")
    p_cfg.add_argument("--path", help="配置文件路径")
    p_cfg.add_argument("--print-json", action="store_true")
    p_cfg.set_defaults(func=_cmd_config)

    p_web = sub.add_parser("web", help="启动本机 Web UI（localhost）")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", default=8787, type=int)
    p_web.add_argument("--config", help="配置文件路径")
    p_web.add_argument(
        "--no-open",
        action="store_true",
        help="不自动打开浏览器",
    )
    p_web.set_defaults(func=_cmd_web)

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
