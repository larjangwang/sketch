from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sketch_assistant.exporter import create_package_export
from sketch_assistant.storage import ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_create_project_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir))
            project = store.create_project("บ้านทดสอบ", "คุณลูกค้า", "เทศบาล", "พักอาศัย")
            self.assertEqual(project["name"], "บ้านทดสอบ")
            self.assertTrue((Path(project["root_path"]) / "sketches").exists())

            sample = Path(temp_dir) / "sample.txt"
            sample.write_text("hello", encoding="utf-8")
            artifact = store.add_artifact(project["id"], "note", "sample.txt", sample, {"ok": True})
            artifacts = store.list_artifacts(project["id"])
            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifact["metadata"]["ok"], True)

    def test_checklist_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir))
            project = store.create_project("บ้านทดสอบ", "", "", "")
            store.save_checklist_status(project["id"], "arch-site-plan", "complete", "ok")
            status = store.checklist_status_map(project["id"])
            self.assertEqual(status["arch-site-plan"]["status"], "complete")
            self.assertEqual(status["arch-site-plan"]["note"], "ok")

    def test_create_export_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir))
            project = store.create_project("บ้านทดสอบ", "คุณลูกค้า", "เทศบาล", "พักอาศัย")
            checklist = [{"id": "arch", "title": "งานสถาปัตย์", "items": [{"id": "arch-site-plan", "title": "ผังบริเวณ"}]}]
            paths = create_package_export(store, project["id"], checklist)
            self.assertTrue(paths["summary_html"].exists())
            self.assertTrue(paths["checklist_csv"].exists())
            self.assertTrue(paths["placeholder_dxf"].exists())
            self.assertTrue(paths["summary_pdf"].exists())


if __name__ == "__main__":
    unittest.main()
