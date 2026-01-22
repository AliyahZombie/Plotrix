import unittest
from unittest import mock

from plotrix.config import AppConfig, ChatConfig, ProviderConfig
from plotrix.openai_client import ChatClient, ChatMessage


class TestPayload(unittest.TestCase):
    def test_omit_optional_fields_when_none(self) -> None:
        cfg = AppConfig(
            active_provider="p1",
            providers={
                "p1": ProviderConfig(
                    base_url="https://example.invalid",
                    api_key="",
                    timeout_s=5.0,
                    verify_tls=True,
                    extra_headers={},
                    models=["test"],
                    model="test",
                )
            },
            chat=ChatConfig(
                system_prompt="",
                temperature=None,
                max_tokens=None,
                max_completion_tokens=None,
                max_output_tokens=None,
                stream=False,
                enable_tool_roll=False,
            ),
        )

        client = ChatClient(cfg)
        messages = [ChatMessage(role="user", content="hi")]
        captured: dict = {}

        def fake_post(_self: ChatClient, _url: str, payload: dict) -> dict:
            captured.update(payload)
            return {"choices": [{"message": {"content": "ok"}}]}

        with mock.patch.object(ChatClient, "_post_json", new=fake_post):
            text, _new_messages = client.chat(messages)

        self.assertEqual(text, "ok")
        self.assertNotIn("temperature", captured)
        self.assertNotIn("max_tokens", captured)
        self.assertNotIn("max_completion_tokens", captured)
        self.assertNotIn("max_output_tokens", captured)

    def test_send_temperature_when_set(self) -> None:
        cfg = AppConfig(
            active_provider="p1",
            providers={
                "p1": ProviderConfig(
                    base_url="https://example.invalid",
                    api_key="",
                    timeout_s=5.0,
                    verify_tls=True,
                    extra_headers={},
                    models=["test"],
                    model="test",
                )
            },
            chat=ChatConfig(
                system_prompt="",
                temperature=0.2,
                max_tokens=None,
                max_completion_tokens=None,
                max_output_tokens=None,
                stream=False,
                enable_tool_roll=False,
            ),
        )

        client = ChatClient(cfg)
        messages = [ChatMessage(role="user", content="hi")]
        captured: dict = {}

        def fake_post(_self: ChatClient, _url: str, payload: dict) -> dict:
            captured.update(payload)
            return {"choices": [{"message": {"content": "ok"}}]}

        with mock.patch.object(ChatClient, "_post_json", new=fake_post):
            client.chat(messages)

        self.assertEqual(captured.get("temperature"), 0.2)

    def test_token_field_precedence(self) -> None:
        cfg = AppConfig(
            active_provider="p1",
            providers={
                "p1": ProviderConfig(
                    base_url="https://example.invalid",
                    api_key="",
                    timeout_s=5.0,
                    verify_tls=True,
                    extra_headers={},
                    models=["test"],
                    model="test",
                )
            },
            chat=ChatConfig(
                system_prompt="",
                temperature=None,
                max_tokens=11,
                max_completion_tokens=22,
                max_output_tokens=33,
                stream=False,
                enable_tool_roll=False,
            ),
        )

        client = ChatClient(cfg)
        messages = [ChatMessage(role="user", content="hi")]
        captured: dict = {}

        def fake_post(_self: ChatClient, _url: str, payload: dict) -> dict:
            captured.update(payload)
            return {"choices": [{"message": {"content": "ok"}}]}

        with mock.patch.object(ChatClient, "_post_json", new=fake_post):
            client.chat(messages)

        self.assertEqual(captured.get("max_completion_tokens"), 22)
        self.assertNotIn("max_output_tokens", captured)
        self.assertNotIn("max_tokens", captured)


if __name__ == "__main__":
    unittest.main()
