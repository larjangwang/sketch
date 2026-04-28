from __future__ import annotations

import json
import queue
import threading
from datetime import datetime
from importlib import resources
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
import tkinter as tk
from tkinter import ttk

from sketch_assistant.config import read_settings, write_settings
from sketch_assistant.exporter import create_package_export, write_analysis_json
from sketch_assistant.gemini import GeminiError, extract_sketch_with_gemini
from sketch_assistant.storage import ProjectStore


STATUS_LABELS = {
    "pending": "รอตรวจ",
    "review": "ต้อง review",
    "complete": "ครบแล้ว",
    "missing": "ขาดข้อมูล",
}


class DrawingAssistantApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI Construction Drawing Assistant")
        self.geometry("1200x780")
        self.minsize(1040, 680)
        self.settings = read_settings()
        self.store = ProjectStore()
        self.current_project_id: str | None = None
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.checklist_items = self._load_checklist()
        self._build_styles()
        self._build_layout()
        self._refresh_projects()
        self.after(250, self._poll_worker_queue)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Surface.TFrame", background="#ffffff")
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), background="#f6f7f9", foreground="#172033")
        style.configure("Subtle.TLabel", font=("Segoe UI", 9), background="#f6f7f9", foreground="#667085")
        style.configure("PanelTitle.TLabel", font=("Segoe UI", 12, "bold"), background="#ffffff", foreground="#172033")
        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 6))
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 7))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(header, text="AI Construction Drawing Assistant", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(header, text="Local-first Windows MVP สำหรับช่วยอ่าน sketch ตรวจ checklist และ export ชุดแบบฉบับร่าง", style="Subtle.TLabel").pack(anchor=tk.W)

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        sidebar = ttk.Frame(body, style="Surface.TFrame", padding=12)
        body.add(sidebar, weight=1)
        main = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(main, weight=4)

        ttk.Label(sidebar, text="Projects", style="PanelTitle.TLabel").pack(anchor=tk.W, pady=(0, 8))
        self.project_tree = ttk.Treeview(sidebar, columns=("client", "authority"), show="tree headings", height=16)
        self.project_tree.heading("#0", text="ชื่อโครงการ")
        self.project_tree.heading("client", text="เจ้าของ")
        self.project_tree.heading("authority", text="หน่วยงาน")
        self.project_tree.column("#0", width=180, minwidth=140)
        self.project_tree.column("client", width=90, minwidth=70)
        self.project_tree.column("authority", width=90, minwidth=70)
        self.project_tree.pack(fill=tk.BOTH, expand=True)
        self.project_tree.bind("<<TreeviewSelect>>", self._on_project_selected)

        sidebar_buttons = ttk.Frame(sidebar, style="Surface.TFrame")
        sidebar_buttons.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(sidebar_buttons, text="New Project", style="Accent.TButton", command=self._create_project_dialog).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(sidebar_buttons, text="Refresh", command=self._refresh_projects).pack(fill=tk.X)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self._build_overview_tab()
        self._build_sketch_tab()
        self._build_checklist_tab()
        self._build_export_tab()
        self._build_settings_tab()

    def _build_overview_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="Project")
        ttk.Label(tab, text="Project Overview", style="PanelTitle.TLabel").pack(anchor=tk.W)
        self.project_details = tk.Text(tab, height=12, wrap=tk.WORD, font=("Segoe UI", 10), relief=tk.FLAT, padx=12, pady=12)
        self.project_details.pack(fill=tk.X, pady=(10, 14))
        ttk.Label(tab, text="Recent Artifacts", style="PanelTitle.TLabel").pack(anchor=tk.W)
        self.artifact_tree = ttk.Treeview(tab, columns=("kind", "created"), show="tree headings", height=12)
        self.artifact_tree.heading("#0", text="ไฟล์")
        self.artifact_tree.heading("kind", text="ประเภท")
        self.artifact_tree.heading("created", text="เวลา")
        self.artifact_tree.column("#0", width=420)
        self.artifact_tree.column("kind", width=120)
        self.artifact_tree.column("created", width=180)
        self.artifact_tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def _build_sketch_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="Sketch + AI")
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="Import Sketch", style="Accent.TButton", command=self._import_sketch).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Run Gemini Extraction", command=self._run_ai_extraction).pack(side=tk.LEFT, padx=(8, 0))

        pane = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)

        ttk.Label(left, text="Sketch Files", style="PanelTitle.TLabel").pack(anchor=tk.W)
        self.sketch_tree = ttk.Treeview(left, columns=("created",), show="tree headings", height=18)
        self.sketch_tree.heading("#0", text="ไฟล์ sketch")
        self.sketch_tree.heading("created", text="เวลา")
        self.sketch_tree.column("#0", width=360)
        self.sketch_tree.column("created", width=160)
        self.sketch_tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        ttk.Label(right, text="AI Extraction Result", style="PanelTitle.TLabel").pack(anchor=tk.W)
        self.ai_result_text = tk.Text(right, wrap=tk.WORD, font=("Consolas", 10), relief=tk.FLAT, padx=12, pady=12)
        self.ai_result_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def _build_checklist_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="Checklist")
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="Mark Complete", command=lambda: self._set_checklist_status("complete")).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Needs Review", command=lambda: self._set_checklist_status("review")).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Missing", command=lambda: self._set_checklist_status("missing")).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Reset", command=lambda: self._set_checklist_status("pending")).pack(side=tk.LEFT, padx=(8, 0))

        self.checklist_tree = ttk.Treeview(tab, columns=("status",), show="tree headings", height=22)
        self.checklist_tree.heading("#0", text="รายการตรวจแบบ")
        self.checklist_tree.heading("status", text="สถานะ")
        self.checklist_tree.column("#0", width=760)
        self.checklist_tree.column("status", width=140)
        self.checklist_tree.pack(fill=tk.BOTH, expand=True)

    def _build_export_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="Export")
        ttk.Label(tab, text="Export Package", style="PanelTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(tab, text="สร้าง package เบื้องต้นสำหรับตรวจงาน: HTML summary, checklist CSV, DXF placeholder และ PDF summary", style="Subtle.TLabel").pack(anchor=tk.W, pady=(4, 14))
        ttk.Button(tab, text="Create Draft Export Package", style="Accent.TButton", command=self._export_package).pack(anchor=tk.W)
        self.export_text = tk.Text(tab, height=18, wrap=tk.WORD, font=("Consolas", 10), relief=tk.FLAT, padx=12, pady=12)
        self.export_text.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

    def _build_settings_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="Settings")
        ttk.Label(tab, text="Settings", style="PanelTitle.TLabel").grid(row=0, column=0, sticky=tk.W, columnspan=2)
        ttk.Label(tab, text="Workspace Folder").grid(row=1, column=0, sticky=tk.W, pady=(16, 4))
        self.workspace_var = tk.StringVar(value=self.settings.get("workspace_dir", ""))
        ttk.Entry(tab, textvariable=self.workspace_var, width=80).grid(row=1, column=1, sticky=tk.EW, pady=(16, 4))

        ttk.Label(tab, text="Gemini API Key").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.api_key_var = tk.StringVar(value=self.settings.get("gemini_api_key", ""))
        ttk.Entry(tab, textvariable=self.api_key_var, width=80, show="*").grid(row=2, column=1, sticky=tk.EW, pady=4)

        ttk.Label(tab, text="Gemini Model").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.model_var = tk.StringVar(value=self.settings.get("gemini_model", "gemini-2.5-flash"))
        ttk.Entry(tab, textvariable=self.model_var, width=80).grid(row=3, column=1, sticky=tk.EW, pady=4)

        ttk.Button(tab, text="Save Settings", style="Accent.TButton", command=self._save_settings).grid(row=4, column=1, sticky=tk.E, pady=(14, 0))
        tab.columnconfigure(1, weight=1)

    def _load_checklist(self) -> list[dict[str, object]]:
        resource = resources.files("sketch_assistant.resources.checklists").joinpath("thai_lowrise_residential.json")
        return json.loads(resource.read_text(encoding="utf-8"))

    def _refresh_projects(self) -> None:
        self.project_tree.delete(*self.project_tree.get_children())
        for project in self.store.list_projects():
            self.project_tree.insert("", tk.END, iid=project["id"], text=project["name"], values=(project["client"], project["authority"]))
        if self.current_project_id:
            self._load_project(self.current_project_id)
        else:
            self._set_project_details("ยังไม่มีโครงการ เลือก New Project เพื่อเริ่มงาน")

    def _on_project_selected(self, _event: object) -> None:
        selection = self.project_tree.selection()
        if selection:
            self._load_project(selection[0])

    def _load_project(self, project_id: str) -> None:
        self.current_project_id = project_id
        project = self.store.get_project(project_id)
        details = [
            f"ชื่อโครงการ: {project['name']}",
            f"เจ้าของ/ลูกค้า: {project['client'] or '-'}",
            f"หน่วยงาน/เขตเป้าหมาย: {project['authority'] or '-'}",
            f"ประเภทอาคาร: {project['building_type'] or '-'}",
            f"โฟลเดอร์: {project['root_path']}",
            "",
            "สถานะ: draft local project - ต้องให้ผู้เชี่ยวชาญตรวจรับรองก่อนใช้งานจริง",
        ]
        self._set_project_details("\n".join(details))
        self._refresh_artifacts()
        self._refresh_sketches()
        self._refresh_checklist()

    def _set_project_details(self, value: str) -> None:
        self.project_details.configure(state=tk.NORMAL)
        self.project_details.delete("1.0", tk.END)
        self.project_details.insert(tk.END, value)
        self.project_details.configure(state=tk.DISABLED)

    def _refresh_artifacts(self) -> None:
        self.artifact_tree.delete(*self.artifact_tree.get_children())
        if not self.current_project_id:
            return
        for artifact in self.store.list_artifacts(self.current_project_id):
            self.artifact_tree.insert("", tk.END, iid=artifact["id"], text=artifact["title"], values=(artifact["kind"], artifact["created_at"]))

    def _refresh_sketches(self) -> None:
        self.sketch_tree.delete(*self.sketch_tree.get_children())
        if not self.current_project_id:
            return
        for artifact in self.store.list_artifacts(self.current_project_id, ["sketch"]):
            self.sketch_tree.insert("", tk.END, iid=artifact["id"], text=artifact["title"], values=(artifact["created_at"],))

    def _refresh_checklist(self) -> None:
        self.checklist_tree.delete(*self.checklist_tree.get_children())
        status_map = self.store.checklist_status_map(self.current_project_id) if self.current_project_id else {}
        for section in self.checklist_items:
            section_id = str(section["id"])
            self.checklist_tree.insert("", tk.END, iid=section_id, text=str(section["title"]), values=("",), open=True)
            for item in section.get("items", []):
                item_id = str(item["id"])
                status = status_map.get(item_id, {}).get("status", "pending")
                self.checklist_tree.insert(section_id, tk.END, iid=item_id, text=str(item["title"]), values=(STATUS_LABELS.get(status, status),))

    def _create_project_dialog(self) -> None:
        dialog = ProjectDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            project = self.store.create_project(**dialog.result)
            self.current_project_id = project["id"]
            self._refresh_projects()
            self.project_tree.selection_set(project["id"])
            self._load_project(project["id"])

    def _require_project(self) -> str | None:
        if not self.current_project_id:
            messagebox.showwarning("ยังไม่ได้เลือกโครงการ", "กรุณาสร้างหรือเลือกโครงการก่อน")
            return None
        return self.current_project_id

    def _import_sketch(self) -> None:
        project_id = self._require_project()
        if not project_id:
            return
        file_path = filedialog.askopenfilename(
            title="เลือกไฟล์ sketch/reference",
            filetypes=[
                ("Image/PDF files", "*.png *.jpg *.jpeg *.webp *.bmp *.pdf"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return
        artifact = self.store.import_file(project_id, Path(file_path), "sketch")
        self._refresh_sketches()
        self._refresh_artifacts()
        self.sketch_tree.selection_set(artifact["id"])

    def _run_ai_extraction(self) -> None:
        project_id = self._require_project()
        if not project_id:
            return
        selection = self.sketch_tree.selection()
        if not selection:
            messagebox.showwarning("ยังไม่ได้เลือก sketch", "กรุณาเลือกไฟล์ sketch ก่อน")
            return
        artifact = self.store.get_artifact(selection[0])
        image_path = Path(artifact["path"])
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip() or "gemini-2.5-flash"
        self._set_ai_result("กำลังอ่าน sketch ด้วย Gemini...\n(ถ้า Gemini ยุ่งจะลองใหม่อัตโนมัติสูงสุด 3 ครั้ง)\n")

        def worker() -> None:
            try:
                result = extract_sketch_with_gemini(api_key, image_path, model)
                self.worker_queue.put(("ai-result", (project_id, result)))
            except GeminiError as error:
                self.worker_queue.put(("ai-error", str(error)))
            except Exception as error:
                self.worker_queue.put(("ai-error", f"Unexpected error: {error}"))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_worker_queue(self) -> None:
        try:
            while True:
                kind, payload = self.worker_queue.get_nowait()
                if kind == "ai-result":
                    project_id, result = payload  # type: ignore[misc]
                    self._handle_ai_result(str(project_id), result)  # type: ignore[arg-type]
                elif kind == "ai-error":
                    self._set_ai_result(f"AI extraction failed:\n{payload}")
        except queue.Empty:
            pass
        self.after(250, self._poll_worker_queue)

    def _handle_ai_result(self, project_id: str, result: dict[str, object]) -> None:
        project = self.store.get_project(project_id)
        output_dir = Path(project["root_path"]) / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"ai-extraction-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        write_analysis_json(output_path, result)
        self.store.add_artifact(project_id, "ai-extraction", output_path.name, output_path, {"model": result.get("model", "mock")})
        self._set_ai_result(json.dumps(result, ensure_ascii=False, indent=2))
        self._refresh_artifacts()

    def _set_ai_result(self, value: str) -> None:
        self.ai_result_text.configure(state=tk.NORMAL)
        self.ai_result_text.delete("1.0", tk.END)
        self.ai_result_text.insert(tk.END, value)
        self.ai_result_text.configure(state=tk.DISABLED)

    def _set_checklist_status(self, status: str) -> None:
        project_id = self._require_project()
        if not project_id:
            return
        selection = self.checklist_tree.selection()
        if not selection:
            messagebox.showwarning("ยังไม่ได้เลือกรายการ", "กรุณาเลือกรายการ checklist")
            return
        checklist_id = selection[0]
        if any(str(section["id"]) == checklist_id for section in self.checklist_items):
            return
        note = ""
        if status in {"review", "missing"}:
            note = simpledialog.askstring("Note", "ระบุ note เพิ่มเติม", parent=self) or ""
        self.store.save_checklist_status(project_id, checklist_id, status, note)
        self._refresh_checklist()
        self._refresh_artifacts()

    def _export_package(self) -> None:
        project_id = self._require_project()
        if not project_id:
            return
        paths = create_package_export(self.store, project_id, self.checklist_items)
        for kind, path in paths.items():
            self.store.add_artifact(project_id, "export", path.name, path, {"export_kind": kind})
        self.export_text.configure(state=tk.NORMAL)
        self.export_text.delete("1.0", tk.END)
        self.export_text.insert(tk.END, "Export created:\n")
        for key, path in paths.items():
            self.export_text.insert(tk.END, f"- {key}: {path}\n")
        self.export_text.configure(state=tk.DISABLED)
        self._refresh_artifacts()

    def _save_settings(self) -> None:
        self.settings.update(
            {
                "workspace_dir": self.workspace_var.get().strip(),
                "gemini_api_key": self.api_key_var.get().strip(),
                "gemini_model": self.model_var.get().strip() or "gemini-2.5-flash",
            }
        )
        write_settings(self.settings)
        messagebox.showinfo("Saved", "บันทึก settings แล้ว กรุณา restart app ถ้าเปลี่ยน workspace folder")


class ProjectDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("New Project")
        self.transient(parent)
        self.grab_set()
        self.result: dict[str, str] | None = None
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        self.vars = {
            "name": tk.StringVar(),
            "client": tk.StringVar(),
            "authority": tk.StringVar(),
            "building_type": tk.StringVar(value="อาคารพักอาศัยขนาดเล็ก"),
        }
        labels = {
            "name": "ชื่อโครงการ",
            "client": "เจ้าของ/ลูกค้า",
            "authority": "หน่วยงาน/เขตเป้าหมาย",
            "building_type": "ประเภทอาคาร",
        }
        for row_index, key in enumerate(self.vars):
            ttk.Label(frame, text=labels[key]).grid(row=row_index, column=0, sticky=tk.W, pady=5)
            ttk.Entry(frame, textvariable=self.vars[key], width=48).grid(row=row_index, column=1, sticky=tk.EW, pady=5)
        actions = ttk.Frame(frame)
        actions.grid(row=len(self.vars), column=1, sticky=tk.E, pady=(14, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Create", style="Accent.TButton", command=self._submit).pack(side=tk.RIGHT, padx=(0, 8))
        frame.columnconfigure(1, weight=1)
        self.bind("<Return>", lambda _event: self._submit())
        self.vars["name"].set("โครงการตัวอย่าง")

    def _submit(self) -> None:
        name = self.vars["name"].get().strip()
        if not name:
            messagebox.showwarning("ข้อมูลไม่ครบ", "กรุณาระบุชื่อโครงการ", parent=self)
            return
        self.result = {key: value.get().strip() for key, value in self.vars.items()}
        self.destroy()


def run_app() -> None:
    app = DrawingAssistantApp()
    app.mainloop()
