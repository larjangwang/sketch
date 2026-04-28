from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sketch_assistant.config import DEFAULT_MODEL  # noqa: E402
from sketch_assistant.gemini import extract_sketch_with_gemini  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract structured data from a construction sketch image.")
    parser.add_argument("image", type=Path, help="Path to image file")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY", ""), help="Gemini API key")
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL), help="Gemini model name")
    args = parser.parse_args()

    result = extract_sketch_with_gemini(args.api_key, args.image, args.model)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
