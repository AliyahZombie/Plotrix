from __future__ import annotations

import threading
import time
import webbrowser
from pathlib import Path


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = True,
    config_path: Path | None = None,
) -> int:
    try:
        import uvicorn  # type: ignore
    except ImportError:  # pragma: no cover
        raise RuntimeError(
            "Web UI dependencies missing. Install with: pip install 'plotrix[web]'"
        ) from None

    from .app import create_app

    app = create_app(config_path=config_path)
    url = f"http://{host}:{port}/"

    if open_browser:
        # Open after the server is likely listening.
        def _open() -> None:
            time.sleep(0.4)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open, name="plotrix-web-open", daemon=True).start()

    uvicorn.run(app, host=host, port=int(port), log_level="info")
    return 0
