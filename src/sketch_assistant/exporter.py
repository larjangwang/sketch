from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sketch_assistant.storage import ProjectStore


def create_package_export(store: ProjectStore, project_id: str, checklist_items: list[dict[str, Any]]) -> dict[str, Path]:
    project = store.get_project(project_id)
    root_path = Path(project["root_path"])
    export_dir = root_path / "exports" / datetime.now().strftime("%Y%m%d-%H%M%S")
    export_dir.mkdir(parents=True, exist_ok=True)
    artifacts = store.list_artifacts(project_id)
    status_map = store.checklist_status_map(project_id)

    html_path = export_dir / "permit-package-summary.html"
    csv_path = export_dir / "drawing-checklist.csv"
    dxf_path = export_dir / "concept-plan-placeholder.dxf"
    pdf_path = export_dir / "permit-package-summary.pdf"

    _write_html_summary(html_path, project, artifacts, checklist_items, status_map)
    _write_checklist_csv(csv_path, checklist_items, status_map)
    _write_placeholder_dxf(dxf_path, project)
    _write_minimal_pdf(pdf_path, project, checklist_items, status_map)

    return {
        "summary_html": html_path,
        "checklist_csv": csv_path,
        "placeholder_dxf": dxf_path,
        "summary_pdf": pdf_path,
    }


def _flatten_checklist_items(checklist_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for section in checklist_items:
        for item in section.get("items", []):
            rows.append({"section": section.get("title", ""), **item})
    return rows


def _write_html_summary(path: Path, project: dict[str, Any], artifacts: list[dict[str, Any]], checklist_items: list[dict[str, Any]], status_map: dict[str, dict[str, str]]) -> None:
    checklist_rows = _flatten_checklist_items(checklist_items)
    checklist_html = "\n".join(
        f"<tr><td>{html.escape(row['section'])}</td><td>{html.escape(row['title'])}</td><td>{html.escape(status_map.get(row['id'], {}).get('status', 'pending'))}</td></tr>"
        for row in checklist_rows
    )
    artifact_html = "\n".join(
        f"<li>{html.escape(artifact['kind'])}: {html.escape(artifact['title'])}</li>" for artifact in artifacts
    )
    path.write_text(
        f"""
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <title>Permit Package Summary</title>
  <style>
    body {{ font-family: Tahoma, Arial, sans-serif; margin: 32px; color: #1f2937; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px; text-align: left; }}
    th {{ background: #e2e8f0; }}
    .notice {{ background: #fff7ed; border: 1px solid #fed7aa; padding: 12px; margin: 16px 0; }}
  </style>
</head>
<body>
  <h1>{html.escape(project['name'])}</h1>
  <p>Client: {html.escape(project['client'])}</p>
  <p>Authority: {html.escape(project['authority'])}</p>
  <p>Building type: {html.escape(project['building_type'])}</p>
  <div class="notice">AI output is draft information. Licensed professional review is required before official submission.</div>
  <h2>Artifacts</h2>
  <ul>{artifact_html}</ul>
  <h2>Checklist</h2>
  <table><tr><th>Section</th><th>Item</th><th>Status</th></tr>{checklist_html}</table>
</body>
</html>
""".strip(),
        encoding="utf-8",
    )


def _write_checklist_csv(path: Path, checklist_items: list[dict[str, Any]], status_map: dict[str, dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["section", "id", "title", "status", "note"])
        for row in _flatten_checklist_items(checklist_items):
            status = status_map.get(row["id"], {})
            writer.writerow([row["section"], row["id"], row["title"], status.get("status", "pending"), status.get("note", "")])


def _write_placeholder_dxf(path: Path, project: dict[str, Any]) -> None:
    """Write a valid DXF R12 (AC1009) placeholder file that AutoCAD can open."""
    project_name = project["name"].replace("\n", " ").replace("(", "").replace(")", "")[:60]
    title_text = f"{project_name} - concept placeholder"
    lines = [
        "  0", "SECTION",
        "  2", "HEADER",
        "  9", "$ACADVER",
        "  1", "AC1009",
        "  9", "$INSBASE",
        " 10", "0.0",
        " 20", "0.0",
        " 30", "0.0",
        "  9", "$EXTMIN",
        " 10", "0.0",
        " 20", "0.0",
        " 30", "0.0",
        "  9", "$EXTMAX",
        " 10", "12000.0",
        " 20", "8000.0",
        " 30", "0.0",
        "  9", "$LUNITS",
        " 70", "4",
        "  9", "$LUPREC",
        " 70", "3",
        "  0", "ENDSEC",
        # TABLES
        "  0", "SECTION",
        "  2", "TABLES",
        "  0", "TABLE",
        "  2", "LTYPE",
        " 70", "1",
        "  0", "LTYPE",
        "  2", "CONTINUOUS",
        " 70", "0",
        "  3", "Solid line",
        " 72", "65",
        " 73", "0",
        " 40", "0.0",
        "  0", "ENDTAB",
        "  0", "TABLE",
        "  2", "LAYER",
        " 70", "3",
        "  0", "LAYER",
        "  2", "0",
        " 70", "0",
        " 62", "7",
        "  6", "CONTINUOUS",
        "  0", "LAYER",
        "  2", "A-WALL",
        " 70", "0",
        " 62", "1",
        "  6", "CONTINUOUS",
        "  0", "LAYER",
        "  2", "A-ANNO",
        " 70", "0",
        " 62", "3",
        "  6", "CONTINUOUS",
        "  0", "ENDTAB",
        "  0", "ENDSEC",
        # BLOCKS
        "  0", "SECTION",
        "  2", "BLOCKS",
        "  0", "ENDSEC",
        # ENTITIES
        "  0", "SECTION",
        "  2", "ENTITIES",
        # Bottom edge
        "  0", "LINE", "  8", "A-WALL",
        " 10", "0.0", " 20", "0.0", " 30", "0.0",
        " 11", "12000.0", " 21", "0.0", " 31", "0.0",
        # Right edge
        "  0", "LINE", "  8", "A-WALL",
        " 10", "12000.0", " 20", "0.0", " 30", "0.0",
        " 11", "12000.0", " 21", "8000.0", " 31", "0.0",
        # Top edge
        "  0", "LINE", "  8", "A-WALL",
        " 10", "12000.0", " 20", "8000.0", " 30", "0.0",
        " 11", "0.0", " 21", "8000.0", " 31", "0.0",
        # Left edge
        "  0", "LINE", "  8", "A-WALL",
        " 10", "0.0", " 20", "8000.0", " 30", "0.0",
        " 11", "0.0", " 21", "0.0", " 31", "0.0",
        # Title text
        "  0", "TEXT", "  8", "A-ANNO",
        " 10", "500.0", " 20", "8500.0", " 30", "0.0",
        " 40", "350.0",
        "  1", title_text,
        "  0", "ENDSEC",
        "  0", "EOF",
        "",
    ]
    path.write_text("\r\n".join(lines), encoding="ascii", errors="replace")


def _write_minimal_pdf(path: Path, project: dict[str, Any], checklist_items: list[dict[str, Any]], status_map: dict[str, dict[str, str]]) -> None:
    rows = _flatten_checklist_items(checklist_items)
    complete_count = sum(1 for row in rows if status_map.get(row["id"], {}).get("status") == "complete")
    lines = [
        "Permit Package Summary",
        f"Project: {project['name']}",
        f"Client: {project['client']}",
        f"Authority: {project['authority']}",
        f"Checklist complete: {complete_count}/{len(rows)}",
        "AI output is draft only. Licensed professional review is required.",
    ]
    escaped_lines = [line.encode("latin-1", errors="replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    text_commands = ["BT", "/F1 14 Tf", "72 760 Td"]
    for index, line in enumerate(escaped_lines):
        if index > 0:
            text_commands.append("0 -24 Td")
        text_commands.append(f"({line}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for pdf_object in objects:
        offsets.append(len(content))
        content.extend(pdf_object)
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    path.write_bytes(content)


def write_analysis_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
