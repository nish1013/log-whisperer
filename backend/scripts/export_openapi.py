"""Write the backend OpenAPI document to a file (default: openapi.json)."""

import json
import sys
from pathlib import Path

from log_whisperer.bootstrap.container import build_app
from log_whisperer.bootstrap.settings import Settings


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    app = build_app(Settings.from_env({"LLM_PROVIDER": "fake"}))
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
