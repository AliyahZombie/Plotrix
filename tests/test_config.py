import os
import unittest
from pathlib import Path

from trpgai.config import AppConfig, ChatConfig, ProviderConfig, load_config, save_config


class TestConfig(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        cfg = AppConfig(
            active_provider="p1",
            providers={
                "p1": ProviderConfig(
                    base_url="https://example.invalid",
                    api_key="test-key",
                    timeout_s=12.5,
                    verify_tls=False,
                    extra_headers={"X-Test": "1"},
                    models=["test-model"],
                    model="test-model",
                )
            },
            chat=ChatConfig(
                system_prompt="sys",
                temperature=0.1,
                max_tokens=123,
                max_completion_tokens=None,
                max_output_tokens=None,
                stream=False,
                enable_tool_roll=False,
            ),
        )

        tmp = Path("tests") / "_tmp_config.json"
        try:
            save_config(cfg, tmp)
            loaded = load_config(tmp)
            self.assertEqual(loaded.to_dict(), cfg.to_dict())
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

    def test_env_overrides_api_key(self) -> None:
        tmp = Path("tests") / "_tmp_config.json"
        try:
            save_config(AppConfig(), tmp)
            os.environ["TRPGAI_API_KEY"] = "from-env"
            loaded = load_config(tmp)
            p = loaded.providers[loaded.active_provider]
            self.assertEqual(p.api_key, "from-env")
        finally:
            os.environ.pop("TRPGAI_API_KEY", None)
            try:
                tmp.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
