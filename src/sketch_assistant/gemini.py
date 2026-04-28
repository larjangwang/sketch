from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from sketch_assistant.config import DEFAULT_MODEL

_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0


class GeminiError(RuntimeError):
    pass


SKETCH_EXTRACTION_PROMPT = """
คุณคือผู้ช่วยสถาปนิกไทย อ่านภาพ sketch/แบบร่างก่อสร้างและสรุปเป็น JSON เท่านั้น

เป้าหมาย:
- ระบุประเภทแบบ เช่น floor_plan, elevation, section, detail, site_plan, unknown
- อ่านชื่อห้อง ขนาดโดยประมาณ dimension note grid ประตู หน้าต่าง บันได สุขภัณฑ์ และข้อความสำคัญ
- ระบุข้อมูลที่ยังขาด เช่น scale, north arrow, title block, setback, structural grid
- ให้ confidence ต่อรายการสำคัญ
- ห้ามสรุปว่าแบบผ่านราชการ ให้ระบุว่า requires_user_confirmation เป็น true เสมอเมื่อข้อมูลยังไม่ครบ

ตอบกลับเป็น JSON object เท่านั้น ห้ามมี markdown

schema:
{
  "drawingType": "floor_plan|elevation|section|detail|site_plan|unknown",
  "confidence": 0.0,
  "detectedRooms": [{"name":"", "approxWidthM": null, "approxDepthM": null, "confidence": 0.0}],
  "detectedOpenings": [{"label":"", "type":"door|window|opening|unknown", "location":"", "confidence": 0.0}],
  "detectedNotes": [""],
  "detectedDimensions": [""],
  "missingInformation": [""],
  "recommendedChecklistFlags": [""],
  "requiresUserConfirmation": true
}
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise GeminiError("Gemini response was not valid JSON")


def mock_sketch_analysis(image_path: Path) -> dict[str, Any]:
    return {
        "drawingType": "unknown",
        "confidence": 0.25,
        "detectedRooms": [],
        "detectedOpenings": [],
        "detectedNotes": [f"Mock extraction only: {image_path.name}"],
        "detectedDimensions": [],
        "missingInformation": ["ยังไม่ได้ตั้งค่า Gemini API key", "ต้องให้ผู้ใช้ยืนยัน scale และขนาดจริง"],
        "recommendedChecklistFlags": ["ตรวจ title block", "ตรวจมาตราส่วน", "ตรวจรายการแบบที่ต้องยื่น"],
        "requiresUserConfirmation": True,
    }


def extract_sketch_with_gemini(api_key: str, image_path: Path, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    if not api_key.strip():
        return mock_sketch_analysis(image_path)
    if not image_path.exists():
        raise GeminiError(f"Image not found: {image_path}")

    mime_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": SKETCH_EXTRACTION_PROMPT},
                    {"inline_data": {"mime_type": mime_type, "data": image_data}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }
    request_data = json.dumps(payload).encode("utf-8")

    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        req = urllib.request.Request(
            endpoint,
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            break  # success
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")
            if error.code in _RETRYABLE_CODES and attempt < _MAX_RETRIES:
                wait = _RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                last_error = GeminiError(f"Gemini API error {error.code} (attempt {attempt}/{_MAX_RETRIES}): {message}")
                time.sleep(wait)
                continue
            raise GeminiError(f"Gemini API error {error.code}: {message}") from error
        except urllib.error.URLError as error:
            raise GeminiError(f"Cannot reach Gemini API: {error.reason}") from error
    else:
        raise last_error or GeminiError("Gemini API failed after all retries")

    candidates = response_payload.get("candidates") or []
    if not candidates:
        raise GeminiError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    response_text = "\n".join(part.get("text", "") for part in parts).strip()
    if not response_text:
        raise GeminiError("Gemini returned an empty response")
    result = _extract_json(response_text)
    result.setdefault("requiresUserConfirmation", True)
    result["sourceImage"] = str(image_path)
    result["model"] = model
    return result
