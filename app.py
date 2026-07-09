from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import sys
import io
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
TEMPLATE_DIR = ROOT / "templates"
FIGMA_API_BASE = "https://api.figma.com/v1"
DEFAULT_TIMEOUT = 30
DATA_DIR = ROOT / "data"


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()
SESSION_STORE_FILE = Path(os.getenv("FIGMA_PLAYGROUND_STORE", DATA_DIR / "session_store.local.json"))
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("FIGMA_PLAYGROUND_PASSWORD", "admin")
SESSION_CACHE: dict[str, dict[str, Any]] = {}
APP_SESSIONS: dict[str, str] = {}


def parse_file_key(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    patterns = [
        r"figma\.com/(?:file|design)/([A-Za-z0-9]+)",
        r"figma\.com/proto/([A-Za-z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{10,}", text):
        return text
    return ""


def figma_get(
    token: str,
    path: str,
    params: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{FIGMA_API_BASE}{path}{query}",
        headers={"X-Figma-Token": token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        try:
            data = json.loads(body)
            message = data.get("err") or data.get("message") or body
        except Exception:
            message = body or f"Figma API error {exc.code}"
        raise FigmaApiError(friendly_figma_error(exc.code, str(message)), exc.code) from exc
    except TimeoutError as exc:
        raise FigmaApiError(
            "Request ke Figma API timeout. Coba load ringan dulu, atau file ini terlalu besar untuk full analysis.",
            504,
        ) from exc
    except urllib.error.URLError as exc:
        raise FigmaApiError(f"Tidak bisa menghubungi Figma API: {exc.reason}", 502) from exc

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise FigmaApiError("Respons Figma bukan JSON object.", 502)
    return data


def download_binary(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/pdf,application/octet-stream,*/*", "User-Agent": "FigmaApiPlayground/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except TimeoutError as exc:
        raise FigmaApiError("Download PDF dari Figma terlalu lama. Coba export section lebih sedikit dulu.", 504) from exc
    except urllib.error.URLError as exc:
        raise FigmaApiError(f"PDF dari Figma belum bisa didownload: {exc.reason}", 502) from exc


def image_bytes_to_pdf(image_bytes: bytes) -> bytes:
    try:
        from PIL import Image
    except Exception as exc:
        raise FigmaApiError("Figma menolak export PDF langsung, dan Pillow belum tersedia untuk membuat PDF fallback dari image.", 500) from exc

    with Image.open(io.BytesIO(image_bytes)) as image:
        if image.mode in {"RGBA", "LA", "P"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            alpha = image.getchannel("A") if image.mode in {"RGBA", "LA"} else None
            background.paste(image.convert("RGB"), mask=alpha)
            image = background
        else:
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="PDF", resolution=144.0)
        return output.getvalue()


def render_single_node_url(token: str, file_key: str, node_id: str, fmt: str, scale: str = "1") -> str:
    params = {"ids": node_id, "format": fmt}
    if fmt != "pdf":
        params["scale"] = scale
    data = figma_get(token, f"/images/{file_key}", params, timeout=90)
    images = data.get("images") or {}
    if not isinstance(images, dict):
        return ""
    return str(images.get(node_id) or "")


def frame_count_from_pages(pages: list[dict[str, Any]]) -> int:
    return sum(len(page.get("frames") or []) for page in pages)


def load_session_store() -> dict[str, Any]:
    if not SESSION_STORE_FILE.exists():
        return {"users": {}}
    try:
        data = json.loads(SESSION_STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"users": {}}
    return data if isinstance(data, dict) else {"users": {}}


def save_session_store(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_STORE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_user_store(username: str, data: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    store = data if data is not None else load_session_store()
    users = store.setdefault("users", {})
    user = users.setdefault(username, {"figma_projects": []})
    if not isinstance(user.get("figma_projects"), list):
        user["figma_projects"] = []
    return store, user


def public_project(project: dict[str, Any]) -> dict[str, Any]:
    token = str(project.get("token") or "")
    token_mask = ""
    if token:
        token_mask = f"{token[:6]}...{token[-4:]}" if len(token) > 12 else "saved-token"
    return {
        "id": project.get("id", ""),
        "title": project.get("title", ""),
        "figma_url": project.get("figma_url", ""),
        "file_key": project.get("file_key", ""),
        "file_name": project.get("file_name", ""),
        "last_loaded_at": project.get("last_loaded_at", ""),
        "token_mask": token_mask,
    }


def saved_projects_for(username: str) -> list[dict[str, Any]]:
    _store, user = ensure_user_store(username)
    return [public_project(item) for item in user.get("figma_projects", [])]


def find_saved_project(username: str, project_id: str) -> dict[str, Any] | None:
    _store, user = ensure_user_store(username)
    for project in user.get("figma_projects", []):
        if str(project.get("id") or "") == project_id:
            return project
    return None


def upsert_saved_project(username: str, project: dict[str, Any]) -> str:
    store = load_session_store()
    _store, user = ensure_user_store(username, store)
    projects = user.setdefault("figma_projects", [])
    project_id = str(project.get("id") or "")
    if not project_id:
        for existing in projects:
            same_title = str(existing.get("title") or "").casefold() == str(project.get("title") or "").casefold()
            same_key = str(existing.get("file_key") or "") == str(project.get("file_key") or "")
            if same_title or same_key:
                project_id = str(existing.get("id") or "")
                break
    if not project_id:
        project_id = secrets.token_urlsafe(12)
    project["id"] = project_id
    for index, existing in enumerate(projects):
        if str(existing.get("id") or "") == project_id:
            projects[index] = {**existing, **project}
            save_session_store(store)
            return project_id
    projects.append(project)
    save_session_store(store)
    return project_id


def delete_saved_project(username: str, project_id: str) -> bool:
    store = load_session_store()
    _store, user = ensure_user_store(username, store)
    projects = user.setdefault("figma_projects", [])
    next_projects = [item for item in projects if str(item.get("id") or "") != project_id]
    user["figma_projects"] = next_projects
    save_session_store(store)
    return len(next_projects) != len(projects)


class FigmaApiError(RuntimeError):
    def __init__(self, message: str, status: int = 500) -> None:
        super().__init__(message)
        self.status = status


def friendly_figma_error(status: int, message: str) -> str:
    if status == 400:
        return "Request ke Figma belum valid. Coba cek file key, node/section yang dipilih, atau kurangi jumlah section."
    if status == 403:
        return "Token Figma tidak bisa dipakai untuk file ini. Cek apakah token masih aktif dan akun tersebut punya akses ke file."
    if status == 404:
        return "File Figma tidak ditemukan. Cek lagi URL/file key dan pastikan file bisa dibuka oleh akun token tersebut."
    if status == 429:
        return "Figma sedang membatasi request. Tunggu sekitar satu menit, lalu coba lagi dengan section lebih sedikit."
    if status >= 500:
        return "Figma belum berhasil membuat respons/render. Coba ulangi, atau export section lebih sedikit dulu."
    return message or "Request ke Figma belum berhasil."


def extract_pages(file_json: dict[str, Any]) -> list[dict[str, Any]]:
    document = file_json.get("document") or {}
    pages: list[dict[str, Any]] = []
    for page in document.get("children") or []:
        if not isinstance(page, dict):
            continue
        frames: list[dict[str, Any]] = []

        def add_frame_rows(node: Any, section_name: str = "", depth: int = 0) -> None:
            if not isinstance(node, dict):
                return
            node_type = str(node.get("type") or "")
            node_section_name = section_name
            if node_type == "SECTION":
                node_section_name = str(node.get("name") or section_name)
            box = node.get("absoluteBoundingBox") or {}
            if node_type in {"FRAME", "COMPONENT", "INSTANCE", "SECTION"}:
                frames.append(
                    {
                        "id": node.get("id", ""),
                        "name": node.get("name", ""),
                        "type": node_type,
                        "section_name": node_section_name if node_type != "SECTION" else "",
                        "depth": depth,
                        "x": round(float(box.get("x") or 0), 2),
                        "y": round(float(box.get("y") or 0), 2),
                        "width": round(float(box.get("width") or 0), 2),
                        "height": round(float(box.get("height") or 0), 2),
                        "child_count": len(node.get("children") or []),
                        "prototype_start": bool(node.get("prototypeStartNodeID")),
                    }
                )
            for child in node.get("children") or []:
                add_frame_rows(child, node_section_name, depth + 1)

        for node in page.get("children") or []:
            add_frame_rows(node)
        frames.sort(key=lambda item: (item["y"], item["x"], item["name"].casefold()))
        pages.append({"id": page.get("id", ""), "name": page.get("name", ""), "frames": frames})
    return pages


def collect_nodes(node: Any, output: dict[str, dict[str, Any]]) -> None:
    if not isinstance(node, dict):
        return
    node_id = str(node.get("id") or "")
    if node_id:
        output[node_id] = node
    for child in node.get("children") or []:
        collect_nodes(child, output)


def extract_interaction_edges(file_json: dict[str, Any]) -> list[dict[str, Any]]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    collect_nodes(file_json.get("document"), nodes_by_id)
    edges: list[dict[str, Any]] = []
    for node_id, node in nodes_by_id.items():
        interactions = node.get("interactions") or []
        for interaction in interactions:
            if not isinstance(interaction, dict):
                continue
            for action in interaction.get("actions") or []:
                if not isinstance(action, dict):
                    continue
                destination_id = action.get("destinationId")
                if not destination_id:
                    continue
                destination = nodes_by_id.get(str(destination_id), {})
                trigger = interaction.get("trigger") or {}
                edges.append(
                    {
                        "source_id": node_id,
                        "source_name": node.get("name", ""),
                        "source_type": node.get("type", ""),
                        "destination_id": destination_id,
                        "destination_name": destination.get("name", ""),
                        "destination_type": destination.get("type", ""),
                        "trigger": trigger.get("type") or "",
                        "action_type": action.get("type") or "",
                        "navigation": action.get("navigation") or "",
                    }
                )
    edges.sort(key=lambda item: (item["source_name"].casefold(), item["destination_name"].casefold()))
    return edges


def collect_nodes_with_context(file_json: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    nodes: dict[str, dict[str, Any]] = {}
    context: dict[str, dict[str, Any]] = {}
    top_frames: list[dict[str, Any]] = []
    document = file_json.get("document") or {}

    def box_of(node: dict[str, Any]) -> dict[str, float]:
        box = node.get("absoluteBoundingBox") or {}
        return {
            "x": round(float(box.get("x") or 0), 2),
            "y": round(float(box.get("y") or 0), 2),
            "width": round(float(box.get("width") or 0), 2),
            "height": round(float(box.get("height") or 0), 2),
        }

    def walk(
        node: Any,
        page: dict[str, str],
        current_frame: dict[str, str] | None,
        current_section: dict[str, Any] | None,
    ) -> None:
        if not isinstance(node, dict):
            return
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        children = node.get("children") or []

        if node_type == "CANVAS":
            page = {"id": node_id, "name": str(node.get("name") or "")}
            for child in children:
                walk(child, page, None, None)
            return

        section_context = current_section
        frame_context = current_frame

        if node_type == "SECTION" and page.get("id"):
            section_context = {
                "id": node_id,
                "name": str(node.get("name") or ""),
                "type": node_type,
                "page_id": page.get("id", ""),
                "page_name": page.get("name", ""),
                **box_of(node),
            }
            top_frames.append(dict(section_context))

        is_screen_frame = node_type in {"FRAME", "COMPONENT", "INSTANCE"} and page.get("id") and current_frame is None
        if is_screen_frame:
            frame_context = {"id": node_id, "name": str(node.get("name") or ""), "type": node_type}
            frame_row = {
                "id": node_id,
                "name": node.get("name", ""),
                "type": node_type,
                "page_id": page.get("id", ""),
                "page_name": page.get("name", ""),
                "section_id": (section_context or {}).get("id", ""),
                "section_name": (section_context or {}).get("name", ""),
                **box_of(node),
            }
            top_frames.append(frame_row)

        if node_id:
            nodes[node_id] = node
            context[node_id] = {
                "page_id": page.get("id", ""),
                "page_name": page.get("name", ""),
                "frame_id": (frame_context or {}).get("id", "") if frame_context else "",
                "frame_name": (frame_context or {}).get("name", "") if frame_context else "",
                "frame_type": (frame_context or {}).get("type", "") if frame_context else "",
                "section_id": (section_context or {}).get("id", "") if section_context else "",
                "section_name": (section_context or {}).get("name", "") if section_context else "",
                "section_type": (section_context or {}).get("type", "") if section_context else "",
            }

        for child in children:
            walk(child, page, frame_context, section_context)

    walk(document, {"id": "", "name": ""}, None, None)
    return nodes, context, top_frames
def analyze_prototype_flow(file_json: dict[str, Any]) -> dict[str, Any]:
    nodes, context, top_frames = collect_nodes_with_context(file_json)
    official_flow_starts = extract_official_flow_starts(file_json, context, top_frames)
    raw_edges = extract_interaction_edges(file_json)
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    noisy_edges: list[dict[str, Any]] = []

    for edge in raw_edges:
        source_context = context.get(str(edge.get("source_id") or ""), {})
        destination_context = context.get(str(edge.get("destination_id") or ""), {})
        destination_node = nodes.get(str(edge.get("destination_id") or ""), {})
        source_frame_id = source_context.get("frame_id") or edge.get("source_id")
        source_frame_name = source_context.get("frame_name") or edge.get("source_name")
        source_frame_type = source_context.get("frame_type") or edge.get("source_type")
        destination_frame_id = destination_context.get("frame_id") or edge.get("destination_id")
        destination_frame_name = destination_context.get("frame_name") or edge.get("destination_name")
        destination_frame_type = destination_context.get("frame_type") or destination_node.get("type") or edge.get("destination_type")
        trigger = str(edge.get("trigger") or "").upper()
        action_type = str(edge.get("action_type") or "").upper()

        normalized = {
            **edge,
            "source_frame_id": source_frame_id or "",
            "source_frame_name": source_frame_name or "",
            "source_frame_type": source_frame_type or "",
            "destination_frame_id": destination_frame_id or "",
            "destination_frame_name": destination_frame_name or "",
            "destination_frame_type": destination_frame_type or "",
            "source_section_id": source_context.get("section_id", ""),
            "source_section_name": source_context.get("section_name", ""),
            "destination_section_id": destination_context.get("section_id", ""),
            "destination_section_name": destination_context.get("section_name", ""),
        }

        if not destination_frame_id or not destination_frame_name:
            normalized["category"] = "NO_DESTINATION"
            normalized["reason"] = "Interaction target is missing or not mapped to a top-level frame."
            noisy_edges.append(normalized)
            continue
        if source_frame_id == destination_frame_id:
            normalized["category"] = "INTERNAL_INTERACTION"
            normalized["reason"] = "Source and target are inside the same frame, so this is not a screen-to-screen flow."
            noisy_edges.append(normalized)
            continue
        if trigger == "ON_HOVER":
            normalized["category"] = "MICRO_INTERACTION"
            normalized["reason"] = "Hover interaction is treated as component behavior, not primary product flow."
            noisy_edges.append(normalized)
            continue

        confidence = 0.62
        if trigger == "ON_CLICK":
            confidence = 0.90
        elif trigger == "DRAG":
            confidence = 0.76
        elif action_type in {"NODE", "NAVIGATE"}:
            confidence = 0.70

        key = (str(source_frame_id), str(destination_frame_id), trigger, action_type)
        item = grouped.get(key)
        if not item:
            grouped[key] = {
                "source_frame_id": source_frame_id,
                "source_frame_name": source_frame_name,
                "source_frame_type": source_frame_type,
                "destination_frame_id": destination_frame_id,
                "destination_frame_name": destination_frame_name,
                "destination_frame_type": destination_frame_type,
                "source_section_id": source_context.get("section_id", ""),
                "source_section_name": source_context.get("section_name", ""),
                "destination_section_id": destination_context.get("section_id", ""),
                "destination_section_name": destination_context.get("section_name", ""),
                "trigger": trigger,
                "action_type": action_type,
                "navigation": edge.get("navigation") or "",
                "confidence": confidence,
                "raw_count": 1,
                "category": "SCREEN_FLOW",
                "reason": "Mapped source and destination to different top-level frames; treated as product flow candidate.",
                "examples": [edge],
            }
        else:
            item["raw_count"] += 1
            item["confidence"] = max(float(item.get("confidence") or 0), confidence)
            if len(item["examples"]) < 3:
                item["examples"].append(edge)

    flow_edges = list(grouped.values())
    flow_edges.sort(
        key=lambda item: (
            -float(item.get("confidence") or 0),
            str(item.get("source_frame_name") or "").casefold(),
            str(item.get("destination_frame_name") or "").casefold(),
        )
    )

    outgoing = {str(edge["source_frame_id"]) for edge in flow_edges}
    incoming = {str(edge["destination_frame_id"]) for edge in flow_edges}
    all_frame_ids = {str(frame["id"]) for frame in top_frames}
    frame_by_id = {str(frame["id"]): frame for frame in top_frames}

    start_candidates = [frame_by_id[item] for item in sorted(outgoing - incoming) if item in frame_by_id]
    dead_ends = [frame_by_id[item] for item in sorted(incoming - outgoing) if item in frame_by_id]
    orphan_frames = [frame_by_id[item] for item in sorted(all_frame_ids - incoming - outgoing) if item in frame_by_id]
    flow_paths = build_flow_paths(flow_edges, official_flow_starts)
    merged_flow_groups = build_merged_flow_groups(flow_paths)
    journey_groups = build_journey_groups(merged_flow_groups)

    return {
        "raw_edges": raw_edges,
        "flow_edges": flow_edges,
        "noisy_edges": noisy_edges,
        "flow_paths": flow_paths,
        "merged_flow_groups": merged_flow_groups,
        "journey_groups": journey_groups,
        "official_flow_starts": official_flow_starts,
        "start_candidates": start_candidates,
        "dead_ends": dead_ends,
        "orphan_frames": orphan_frames,
        "stats": {
            "raw_edges": len(raw_edges),
            "screen_flow_edges": len(flow_edges),
            "flow_paths": len(flow_paths),
            "merged_flows": len(merged_flow_groups),
            "journeys": len(journey_groups),
            "official_flows": len(official_flow_starts),
            "ignored_edges": len(noisy_edges),
            "top_level_frames": len(top_frames),
            "start_candidates": len(start_candidates),
            "dead_ends": len(dead_ends),
            "orphan_frames": len(orphan_frames),
        },
    }

def extract_official_flow_starts(
    file_json: dict[str, Any],
    context: dict[str, dict[str, Any]],
    top_frames: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    collect_nodes(file_json.get("document"), nodes)
    frame_by_id = {str(frame.get("id") or ""): frame for frame in top_frames}
    starts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_start(node_id: Any, name: Any = "") -> None:
        raw_id = str(node_id or "")
        if not raw_id:
            return
        node_context = context.get(raw_id, {})
        frame_id = node_context.get("frame_id") or raw_id
        frame = frame_by_id.get(str(frame_id), {})
        if not frame:
            node = nodes.get(raw_id, {})
            if str(node.get("type") or "") in {"FRAME", "COMPONENT", "INSTANCE", "SECTION"}:
                frame = {
                    "id": raw_id,
                    "name": node.get("name", raw_id),
                    "type": node.get("type", ""),
                    "page_id": node_context.get("page_id", ""),
                    "page_name": node_context.get("page_name", ""),
                }
        if not frame:
            return
        key = str(frame.get("id") or frame_id)
        if key in seen:
            return
        seen.add(key)
        starts.append(
            {
                "id": key,
                "name": str(name or frame.get("name") or f"Flow {len(starts) + 1}"),
                "frame_name": str(frame.get("name") or key),
                "frame_type": str(frame.get("type") or ""),
                "page_id": str(frame.get("page_id") or ""),
                "page_name": str(frame.get("page_name") or ""),
                "section_id": str(node_context.get("section_id") or frame.get("section_id") or ""),
                "section_name": str(node_context.get("section_name") or frame.get("section_name") or ""),
                "source": "FIGMA_FLOW_START",
            }
        )

    def walk_for_starts(node: Any) -> None:
        if not isinstance(node, dict):
            return
        for item in node.get("flowStartingPoints") or []:
            if isinstance(item, dict):
                add_start(item.get("nodeId") or item.get("nodeID") or item.get("id"), item.get("name"))
        prototype_start = node.get("prototypeStartNodeID") or node.get("prototypeStartNodeId")
        if prototype_start:
            add_start(prototype_start, node.get("name"))
        for child in node.get("children") or []:
            walk_for_starts(child)

    walk_for_starts(file_json.get("document"))
    for index, item in enumerate(starts, start=1):
        if not item.get("name") or item["name"] == item.get("frame_name"):
            item["name"] = f"Flow {index}"
    return starts


def build_flow_paths(
    flow_edges: list[dict[str, Any]],
    official_starts: list[dict[str, Any]] | None = None,
    max_depth: int = 30,
    max_paths: int = 120,
) -> list[dict[str, Any]]:
    adjacency: dict[str, list[dict[str, Any]]] = {}
    incoming: set[str] = set()
    outgoing: set[str] = set()
    frame_names: dict[str, str] = {}
    frame_types: dict[str, str] = {}
    frame_sections: dict[str, dict[str, str]] = {}

    for edge in flow_edges:
        source_id = str(edge.get("source_frame_id") or "")
        destination_id = str(edge.get("destination_frame_id") or "")
        if not source_id or not destination_id:
            continue
        adjacency.setdefault(source_id, []).append(edge)
        outgoing.add(source_id)
        incoming.add(destination_id)
        frame_names[source_id] = str(edge.get("source_frame_name") or source_id)
        frame_names[destination_id] = str(edge.get("destination_frame_name") or destination_id)
        frame_types[source_id] = str(edge.get("source_frame_type") or "")
        frame_types[destination_id] = str(edge.get("destination_frame_type") or "")
        frame_sections[source_id] = {"id": str(edge.get("source_section_id") or ""), "name": str(edge.get("source_section_name") or "")}
        frame_sections[destination_id] = {"id": str(edge.get("destination_section_id") or ""), "name": str(edge.get("destination_section_name") or "")}

    for edges in adjacency.values():
        edges.sort(
            key=lambda item: (
                0 if str(item.get("trigger") or "").upper() == "ON_CLICK" else 1,
                str(item.get("destination_frame_name") or "").casefold(),
                str(item.get("destination_frame_id") or ""),
            )
        )

    official_starts = official_starts or []
    start_records = [item for item in official_starts if str(item.get("id") or "") in outgoing]
    if not start_records:
        inferred = sorted(outgoing - incoming, key=lambda item: frame_names.get(item, item).casefold())
        if not inferred:
            inferred = sorted(outgoing, key=lambda item: frame_names.get(item, item).casefold())
        start_records = [
            {
                "id": frame_id,
                "name": f"Inferred Flow {index}",
                "frame_name": frame_names.get(frame_id, frame_id),
                "source": "INFERRED_START",
            }
            for index, frame_id in enumerate(inferred, start=1)
        ]

    paths: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()

    def make_path(path_edges: list[dict[str, Any]], start_record: dict[str, Any]) -> dict[str, Any]:
        first = path_edges[0]
        node_ids = [str(first.get("source_frame_id") or "")]
        for item in path_edges:
            node_ids.append(str(item.get("destination_frame_id") or ""))
        nodes = [
            {"id": node_id, "name": frame_names.get(node_id, node_id), "type": frame_types.get(node_id, ""), "section_id": frame_sections.get(node_id, {}).get("id", ""), "section_name": frame_sections.get(node_id, {}).get("name", "")}
            for node_id in node_ids
            if node_id
        ]
        confidence_values = [float(item.get("confidence") or 0) for item in path_edges]
        return {
            "official_flow_id": str(start_record.get("id") or ""),
            "official_flow_name": str(start_record.get("name") or ""),
            "official_flow_source": str(start_record.get("source") or ""),
            "start_frame_name": str(start_record.get("frame_name") or ""),
            "node_count": len(nodes),
            "edge_count": len(path_edges),
            "nodes": nodes,
            "edges": path_edges,
            "confidence": round(sum(confidence_values) / max(len(confidence_values), 1), 4),
            "is_cycle": len(set(node_ids)) != len(node_ids),
        }

    def add_path(path_edges: list[dict[str, Any]], start_record: dict[str, Any]) -> None:
        if not path_edges:
            frame_id = str(start_record.get("id") or "")
            if frame_id:
                synthetic = {
                    "official_flow_id": frame_id,
                    "official_flow_name": str(start_record.get("name") or ""),
                    "official_flow_source": str(start_record.get("source") or ""),
                    "start_frame_name": str(start_record.get("frame_name") or frame_id),
                    "node_count": 1,
                    "edge_count": 0,
                    "nodes": [{"id": frame_id, "name": str(start_record.get("frame_name") or frame_id), "type": str(start_record.get("frame_type") or ""), "section_id": str(start_record.get("section_id") or ""), "section_name": str(start_record.get("section_name") or "")}],
                    "edges": [],
                    "confidence": 0.0,
                    "is_cycle": False,
                }
                signature = f"{frame_id}|single"
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    paths.append(synthetic)
            return
        signature = "|".join(
            [str(start_record.get("id") or ""), str(path_edges[0].get("source_frame_id") or "")]
            + [str(item.get("destination_frame_id") or "") for item in path_edges]
        )
        if signature in seen_signatures:
            return
        seen_signatures.add(signature)
        paths.append(make_path(path_edges, start_record))

    def walk(current_id: str, path_edges: list[dict[str, Any]], visited: set[str], start_record: dict[str, Any]) -> None:
        if len(paths) >= max_paths:
            return
        next_edges = adjacency.get(current_id) or []
        if not next_edges or len(path_edges) >= max_depth:
            add_path(path_edges, start_record)
            return
        progressed = False
        for edge in next_edges:
            destination_id = str(edge.get("destination_frame_id") or "")
            if not destination_id:
                continue
            progressed = True
            if destination_id in visited:
                add_path([*path_edges, edge], start_record)
                continue
            walk(destination_id, [*path_edges, edge], {*visited, destination_id}, start_record)
        if not progressed:
            add_path(path_edges, start_record)

    for start_record in start_records:
        start_id = str(start_record.get("id") or "")
        walk(start_id, [], {start_id}, start_record)
        if len(paths) >= max_paths:
            break

    if not paths:
        for edge in flow_edges[:max_paths]:
            add_path([edge], {"id": edge.get("source_frame_id"), "name": "Inferred Flow", "source": "INFERRED_START"})

    paths.sort(
        key=lambda item: (
            0 if item.get("official_flow_source") == "FIGMA_FLOW_START" else 1,
            str(item.get("official_flow_name") or "").casefold(),
            -int(item.get("node_count") or 0),
        )
    )
    for index, path in enumerate(paths, start=1):
        path["index"] = index
        if path.get("official_flow_source") == "FIGMA_FLOW_START":
            path["category"] = "FIGMA_FLOW"
        elif path.get("node_count", 0) >= 4:
            path["category"] = "MULTI_STEP_FLOW"
        elif path.get("node_count", 0) == 3:
            path["category"] = "SHORT_FLOW"
        else:
            path["category"] = "DIRECT_TRANSITION"
    return paths


def build_merged_flow_groups(flow_paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    def new_tree_node(node: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(node.get("id") or ""),
            "name": str(node.get("name") or node.get("id") or ""),
            "type": str(node.get("type") or ""),
            "section_id": str(node.get("section_id") or ""),
            "section_name": str(node.get("section_name") or ""),
            "children": [],
            "_child_index": {},
        }

    for path in flow_paths:
        nodes = [node for node in path.get("nodes") or [] if node.get("id")]
        if not nodes:
            continue
        root_id = str(nodes[0].get("id") or "")
        if root_id not in groups:
            groups[root_id] = {
                "root_id": root_id,
                "root_name": str(nodes[0].get("name") or root_id),
                "root_type": str(nodes[0].get("type") or ""),
                "section_id": str(nodes[0].get("section_id") or ""),
                "section_name": str(nodes[0].get("section_name") or ""),
                "path_count": 0,
                "max_depth": 0,
                "source_flows": [],
                "tree": new_tree_node(nodes[0]),
            }
        group = groups[root_id]
        group["path_count"] += 1
        group["max_depth"] = max(int(group.get("max_depth") or 0), len(nodes))
        flow_name = str(path.get("official_flow_name") or f"Flow {path.get('index') or group['path_count']}")
        if flow_name and flow_name not in group["source_flows"]:
            group["source_flows"].append(flow_name)

        current = group["tree"]
        for node in nodes[1:]:
            node_id = str(node.get("id") or "")
            child_index = current.setdefault("_child_index", {})
            if node_id not in child_index:
                child = new_tree_node(node)
                current["children"].append(child)
                child_index[node_id] = child
            current = child_index[node_id]

    def strip_internal(node: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": node.get("id", ""),
            "name": node.get("name", ""),
            "type": node.get("type", ""),
            "section_id": node.get("section_id", ""),
            "section_name": node.get("section_name", ""),
            "children": [strip_internal(child) for child in node.get("children") or []],
        }

    output: list[dict[str, Any]] = []
    for index, group in enumerate(groups.values(), start=1):
        tree = strip_internal(group["tree"])
        output.append(
            {
                "index": index,
                "name": f"Merged Flow {index}",
                "root_id": group["root_id"],
                "root_name": group["root_name"],
                "root_type": group["root_type"],
                "section_id": group.get("section_id", ""),
                "section_name": group.get("section_name", ""),
                "path_count": group["path_count"],
                "max_depth": group["max_depth"],
                "branch_count": count_branch_nodes(tree),
                "screen_count": count_tree_nodes(tree),
                "source_flows": group["source_flows"],
                "tree": tree,
            }
        )
    output.sort(key=lambda item: (-int(item.get("path_count") or 0), str(item.get("root_name") or "").casefold()))
    for index, item in enumerate(output, start=1):
        item["index"] = index
        item["name"] = f"Flow {index}"
    return output


JOURNEY_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("onboarding", "Onboarding", ("onboarding", "intro", "walkthrough", "welcome", "splash", "mulai", "perkenalan")),
    ("login", "Login", ("login", "log in", "masuk", "signin", "sign in", "password", "kata sandi")),
    ("registration", "Registration / Daftar", ("register", "registration", "daftar", "sign up", "signup", "form", "pendaftaran", "registrasi")),
    ("verification", "Verification / OTP", ("otp", "verifikasi", "verification", "kode", "pin", "validasi")),
    ("home", "Home / Dashboard", ("home", "beranda", "dashboard", "homepage", "main menu")),
    ("profile", "Profile", ("profile", "profil", "akun", "account", "pengaturan", "settings")),
    ("payment", "Payment", ("payment", "bayar", "pembayaran", "checkout", "invoice", "tagihan")),
    ("search", "Search / Browse", ("search", "cari", "browse", "list", "daftar item", "kategori")),
    ("detail", "Detail Review", ("detail", "rincian", "summary", "ringkasan", "review")),
    ("success", "Success / Result", ("success", "sukses", "berhasil", "selesai", "done", "complete")),
]


def collect_tree_names(node: dict[str, Any]) -> list[str]:
    names = [str(node.get("name") or "")]
    for child in node.get("children") or []:
        names.extend(collect_tree_names(child))
    return [name for name in names if name]


def infer_journey(group: dict[str, Any]) -> dict[str, Any]:
    section_name = str(group.get("section_name") or "").strip()
    if section_name:
        normalized_section = re.sub(r"[^a-z0-9]+", "-", section_name.casefold()).strip("-") or "section"
        return {
            "key": f"section-{normalized_section[:60]}",
            "label": section_name,
            "confidence": 0.95,
            "evidence": ["Figma section", section_name],
            "source": "FIGMA_SECTION",
        }
    names = [
        str(group.get("name") or ""),
        str(group.get("root_name") or ""),
        *[str(item) for item in group.get("source_flows") or []],
        *collect_tree_names(group.get("tree") or {}),
    ]
    haystack = " ".join(names).casefold()
    matches: list[str] = []
    for key, label, keywords in JOURNEY_RULES:
        found = [keyword for keyword in keywords if keyword in haystack]
        if found:
            return {
                "key": key,
                "label": label,
                "confidence": min(1.0, 0.55 + len(found) * 0.12),
                "evidence": found[:8],
                "source": "KEYWORD_HEURISTIC",
            }
    root = str(group.get("root_name") or "Scenario").strip() or "Scenario"
    normalized = re.sub(r"[^a-z0-9]+", "-", root.casefold()).strip("-") or "scenario"
    return {
        "key": f"scenario-{normalized[:40]}",
        "label": root,
        "confidence": 0.35,
        "evidence": [root],
        "source": "ROOT_FRAME_FALLBACK",
    }


def build_journey_groups(merged_flow_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for group in merged_flow_groups:
        journey = infer_journey(group)
        group["journey_key"] = journey["key"]
        group["journey_label"] = journey["label"]
        group["journey_confidence"] = journey["confidence"]
        group["journey_evidence"] = journey["evidence"]
        bucket = buckets.setdefault(
            journey["key"],
            {
                "key": journey["key"],
                "label": journey["label"],
                "confidence": journey["confidence"],
                "evidence": list(journey["evidence"]),
                "source": journey.get("source", ""),
                "flow_indexes": [],
                "flow_count": 0,
                "path_count": 0,
                "screen_count": 0,
                "branch_count": 0,
            },
        )
        bucket["flow_indexes"].append(group.get("index"))
        bucket["flow_count"] += 1
        bucket["path_count"] += int(group.get("path_count") or 0)
        bucket["screen_count"] += int(group.get("screen_count") or 0)
        bucket["branch_count"] += int(group.get("branch_count") or 0)
        bucket["confidence"] = max(float(bucket.get("confidence") or 0), float(journey.get("confidence") or 0))
        for item in journey.get("evidence") or []:
            if item not in bucket["evidence"]:
                bucket["evidence"].append(item)
    journeys = list(buckets.values())
    journeys.sort(key=lambda item: (-int(item.get("flow_count") or 0), str(item.get("label") or "").casefold()))
    return journeys

def count_tree_nodes(node: dict[str, Any]) -> int:
    return 1 + sum(count_tree_nodes(child) for child in node.get("children") or [])


def count_branch_nodes(node: dict[str, Any]) -> int:
    count = 1 if len(node.get("children") or []) > 1 else 0
    return count + sum(count_branch_nodes(child) for child in node.get("children") or [])

def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "figma-export.json"


def response_filename(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or fallback


class Handler(BaseHTTPRequestHandler):
    server_version = "FigmaApiPlayground/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/me":
            username = self.current_username()
            self.send_json({"authenticated": bool(username), "username": username or "", "projects": saved_projects_for(username) if username else []})
            return
        if parsed.path == "/":
            self.send_file(TEMPLATE_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path.startswith("/static/"):
            relative = parsed.path.replace("/static/", "", 1)
            target = (STATIC_DIR / relative).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve())):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_file(target, mime)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed_path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        try:
            if parsed_path == "/api/login":
                self.api_login()
            elif parsed_path == "/api/logout":
                self.api_logout()
            elif parsed_path == "/api/saved-figma-list":
                self.api_saved_figma_list()
            elif parsed_path == "/api/delete-saved-figma":
                self.api_delete_saved_figma()
            elif parsed_path == "/api/load-file":
                self.api_load_file()
            elif parsed_path == "/api/render-frames":
                self.api_render_frames()
            elif parsed_path == "/api/prototype":
                self.api_prototype()
            elif parsed_path == "/api/export-order":
                self.api_export_order()
            elif parsed_path == "/api/export-fut-section-pdfs":
                self.api_export_fut_section_pdfs()
            elif parsed_path == "/api/export-snapshot":
                self.api_export_snapshot()
            elif parsed_path == "/api/import-snapshot":
                self.api_import_snapshot()
            elif parsed_path == "/api/clear-session":
                self.api_clear_session()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except FigmaApiError as exc:
            self.send_json({"error": str(exc)}, exc.status)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise FigmaApiError(f"Request JSON tidak valid: {exc.msg}", 400) from exc
        return data if isinstance(data, dict) else {}

    def send_json(self, data: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        raw = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def cookie_value(self, name: str) -> str:
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            if "=" not in part:
                continue
            key, value = part.strip().split("=", 1)
            if key == name:
                return urllib.parse.unquote(value)
        return ""

    def current_username(self) -> str:
        session_id = self.cookie_value("fp_session")
        return APP_SESSIONS.get(session_id, "")

    def require_username(self) -> str:
        username = self.current_username()
        if not username:
            raise FigmaApiError("Login required. Silakan login ulang.", 401)
        return username

    def set_auth_cookie(self, session_id: str, max_age: int) -> None:
        cookie = f"fp_session={urllib.parse.quote(session_id)}; Path=/; SameSite=Lax; Max-Age={max_age}"
        self.send_header("Set-Cookie", cookie)

    def api_login(self) -> None:
        payload = self.read_json()
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
            self.send_json({"error": "ID atau password salah."}, 401)
            return
        session_id = secrets.token_urlsafe(24)
        APP_SESSIONS[session_id] = username
        raw = json.dumps({"ok": True, "username": username, "projects": saved_projects_for(username)}, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.set_auth_cookie(session_id, 60 * 60 * 24 * 30)
        self.end_headers()
        self.wfile.write(raw)

    def api_logout(self) -> None:
        session_id = self.cookie_value("fp_session")
        if session_id:
            APP_SESSIONS.pop(session_id, None)
        raw = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.set_auth_cookie("", 0)
        self.end_headers()
        self.wfile.write(raw)

    def api_saved_figma_list(self) -> None:
        username = self.require_username()
        self.send_json({"projects": saved_projects_for(username)})

    def api_delete_saved_figma(self) -> None:
        username = self.require_username()
        payload = self.read_json()
        project_id = str(payload.get("id") or "")
        if not project_id:
            self.send_json({"error": "Saved Figma id wajib diisi."}, 400)
            return
        delete_saved_project(username, project_id)
        self.send_json({"ok": True, "projects": saved_projects_for(username)})

    def api_load_file(self) -> None:
        username = self.require_username()
        payload = self.read_json()
        saved_project_id = str(payload.get("saved_project_id") or "").strip()
        figma_title = str(payload.get("figma_title") or "").strip()
        token = str(payload.get("token") or "").strip()
        figma_url = str(payload.get("figma_url") or "").strip()

        saved_project: dict[str, Any] | None = None
        if saved_project_id:
            saved_project = find_saved_project(username, saved_project_id)
            if not saved_project:
                self.send_json({"error": "Saved Figma tidak ditemukan."}, 404)
                return
            figma_title = str(saved_project.get("title") or figma_title or "").strip()
            token = str(saved_project.get("token") or "").strip()
            figma_url = str(saved_project.get("figma_url") or saved_project.get("file_key") or "").strip()

        if not figma_title:
            self.send_json({"error": "Judul Figma wajib diisi."}, 400)
            return
        if not token:
            self.send_json({"error": "Figma token wajib diisi."}, 400)
            return
        file_key = parse_file_key(figma_url)
        if not file_key:
            self.send_json({"error": "URL Figma tidak valid atau file key tidak ditemukan."}, 400)
            return

        data = figma_get(token, f"/files/{file_key}", {"depth": "3"}, timeout=35)
        session_id = secrets.token_urlsafe(24)
        SESSION_CACHE[session_id] = {
            "file_json": data,
            "file_key": file_key,
            "file_name": data.get("name", ""),
            "token": token,
            "is_full": False,
        }
        saved_id = upsert_saved_project(
            username,
            {
                "id": saved_project_id,
                "title": figma_title,
                "token": token,
                "figma_url": figma_url,
                "file_key": file_key,
                "file_name": data.get("name", ""),
                "last_loaded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        pages = extract_pages(data)
        frame_count = frame_count_from_pages(pages)
        self.send_json(
            {
                "session_id": session_id,
                "saved_project_id": saved_id,
                "saved_projects": saved_projects_for(username),
                "file_key": file_key,
                "file_name": data.get("name", ""),
                "figma_title": figma_title,
                "last_modified": data.get("lastModified", ""),
                "pages": pages,
                "frame_count": frame_count,
                "load_mode": "metadata-depth-3",
                "message": "Loaded and saved in local session store. Next login can reuse this Figma entry without re-entering token or file key.",
            }
        )
    def api_render_frames(self) -> None:
        self.require_username()
        payload = self.read_json()
        session_id = str(payload.get("session_id") or "")
        cached = SESSION_CACHE.get(session_id, {}) if session_id else {}
        token = str(payload.get("token") or cached.get("token") or "").strip()
        file_key = str(payload.get("file_key") or cached.get("file_key") or "").strip()
        ids = [str(item) for item in payload.get("ids") or [] if str(item).strip()]
        fmt = str(payload.get("format") or "png").lower()
        if fmt not in {"png", "jpg", "svg", "pdf"}:
            fmt = "png"
        if not token or not file_key:
            self.send_json({"error": "Token dan file key wajib tersedia."}, 400)
            return
        if not ids:
            self.send_json({"error": "Pilih minimal satu frame."}, 400)
            return
        data = figma_get(token, f"/images/{file_key}", {"ids": ",".join(ids[:50]), "format": fmt, "scale": str(payload.get("scale") or "1")})
        self.send_json({"images": data.get("images") or {}, "format": fmt})

    def api_prototype(self) -> None:
        self.require_username()
        payload = self.read_json()
        session_id = str(payload.get("session_id") or "")
        cached = SESSION_CACHE.get(session_id)
        if not cached:
            self.send_json({"error": "Session file tidak ditemukan. Load file ulang."}, 400)
            return
        token = str(payload.get("token") or cached.get("token") or "").strip()
        file_key = str(payload.get("file_key") or cached.get("file_key") or "").strip()
        if not cached.get("is_full"):
            if not token or not file_key:
                self.send_json({"error": "Token dan file key wajib tersedia untuk full flow analysis."}, 400)
                return
            data = figma_get(token, f"/files/{file_key}", timeout=90)
            cached["file_json"] = data
            cached["file_name"] = data.get("name", cached.get("file_name", ""))
            cached["is_full"] = True
        analysis = analyze_prototype_flow(cached["file_json"])
        analysis["load_mode"] = "full-file"
        self.send_json(analysis)

    def api_export_order(self) -> None:
        payload = self.read_json()
        export_type = str(payload.get("export_type") or "current_page_frames")
        export_data = {
            "export_type": export_type,
            "file_key": payload.get("file_key"),
            "file_name": payload.get("file_name"),
            "page_id": payload.get("page_id"),
            "page_name": payload.get("page_name"),
            "frames": payload.get("frames") or [],
            "pages": payload.get("pages") or [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        raw = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
        prefix_by_type = {
            "current_page_frames": "figma-current-page-frames",
            "checked_frames": "figma-checked-frames",
            "all_pages_frames": "figma-all-pages-frames",
        }
        filename = safe_filename(f"{prefix_by_type.get(export_type, 'figma-frame-order')}-{export_data.get('file_key') or 'export'}.json")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename={filename}")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def api_export_fut_section_pdfs(self) -> None:
        self.require_username()
        payload = self.read_json()
        session_id = str(payload.get("session_id") or "")
        cached = SESSION_CACHE.get(session_id, {}) if session_id else {}
        token = str(payload.get("token") or cached.get("token") or "").strip()
        file_key = str(payload.get("file_key") or cached.get("file_key") or "").strip()
        file_name = str(payload.get("file_name") or cached.get("file_name") or "figma").strip()
        page_name = str(payload.get("page_name") or "").strip()
        raw_sections = payload.get("sections") or []
        sections = [item for item in raw_sections if isinstance(item, dict) and str(item.get("id") or "").strip()]

        if not token or not file_key:
            self.send_json(
                {
                    "error": "Export PDF perlu Saved Figma atau Load & Save File yang masih punya token. Snapshot saja belum cukup untuk membuat PDF visual."
                },
                400,
            )
            return
        if not sections:
            self.send_json({"error": "Pilih minimal satu section dulu sebelum export PDF untuk FUT Automation."}, 400)
            return
        if len(sections) > 50:
            self.send_json({"error": "Export dibatasi maksimal 50 section sekali jalan supaya Figma tidak timeout."}, 400)
            return

        manifest = {
            "source": "figma-api-playground",
            "export_type": "fut_split_section_pdfs",
            "file_key": file_key,
            "file_name": file_name,
            "page_name": page_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "contains_token": False,
            "requested_count": len(sections),
            "exported_count": 0,
            "failed_sections": [],
            "sections": [],
        }
        zip_buffer = io.BytesIO()
        used_names: set[str] = set()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, section in enumerate(sections, start=1):
                section_id = str(section.get("id") or "")
                section_name = str(section.get("name") or section_id)
                pdf_bytes = b""
                content_type = ""
                render_mode = "figma_pdf"
                try:
                    pdf_url = render_single_node_url(token, file_key, section_id, "pdf")
                    if pdf_url:
                        pdf_bytes, content_type = download_binary(pdf_url, timeout=90)
                except FigmaApiError:
                    pdf_bytes = b""

                if not pdf_bytes:
                    render_mode = "png_wrapped_pdf"
                    fallback_errors: list[str] = []
                    for fallback_scale in ("0.5", "0.25", "0.1"):
                        try:
                            image_url = render_single_node_url(token, file_key, section_id, "png", scale=fallback_scale)
                            if not image_url:
                                fallback_errors.append(f"scale {fallback_scale}: Figma belum mengirim link image.")
                                continue
                            image_bytes, content_type = download_binary(image_url, timeout=90)
                            pdf_bytes = image_bytes_to_pdf(image_bytes)
                            content_type = "application/pdf"
                            render_mode = f"png_wrapped_pdf_scale_{fallback_scale}"
                            break
                        except FigmaApiError as exc:
                            fallback_errors.append(f"scale {fallback_scale}: {exc}")
                    if not pdf_bytes:
                        manifest["failed_sections"].append(
                            {
                                "id": section_id,
                                "name": section_name,
                                "reason": " | ".join(fallback_errors) or "Figma belum mengirim hasil render.",
                            }
                        )
                        continue

                if not pdf_bytes:
                    manifest["failed_sections"].append({"id": section_id, "name": section_name, "reason": "Figma belum mengirim hasil render untuk section ini."})
                    continue
                filename_base = response_filename(f"flow-{index:02d}-{section_name}", f"flow-{index:02d}")
                filename = f"{filename_base}.pdf"
                counter = 2
                while filename in used_names:
                    filename = f"{filename_base}-{counter}.pdf"
                    counter += 1
                used_names.add(filename)
                archive.writestr(filename, pdf_bytes)
                manifest["sections"].append(
                    {
                        "order": index,
                        "id": section_id,
                        "name": section_name,
                        "type": section.get("type") or "SECTION",
                        "pdf": filename,
                        "content_type": content_type,
                        "render_mode": render_mode,
                    }
                )
            manifest["exported_count"] = len(manifest["sections"])
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))

        if manifest["exported_count"] <= 0:
            reasons = "; ".join(
                f"{item.get('name') or item.get('id')}: {item.get('reason') or 'gagal dirender'}"
                for item in manifest["failed_sections"][:5]
            )
            self.send_json(
                {
                    "error": "PDF belum berhasil dibuat dari section yang dipilih. Coba section lebih kecil atau render section preview dulu. "
                    + (f"Detail: {reasons}" if reasons else "")
                },
                502,
            )
            return

        raw = zip_buffer.getvalue()
        filename = response_filename(f"fut-section-pdfs-{file_name or file_key}", "fut-section-pdfs") + ".zip"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f"attachment; filename={filename}")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def api_export_snapshot(self) -> None:
        self.require_username()
        payload = self.read_json()
        session_id = str(payload.get("session_id") or "")
        cached = SESSION_CACHE.get(session_id)
        if not cached:
            self.send_json({"error": "Session file tidak ditemukan. Load file atau import snapshot dulu."}, 400)
            return
        file_json = cached.get("file_json") or {}
        file_key = str(cached.get("file_key") or payload.get("file_key") or "")
        file_name = str(cached.get("file_name") or file_json.get("name") or payload.get("file_name") or "")
        snapshot = {
            "snapshot_version": "1.0",
            "source": "figma-api-playground",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "figma_title": str(payload.get("figma_title") or file_name or file_key or "Figma Snapshot"),
            "file_key": file_key,
            "file_name": file_name,
            "last_modified": file_json.get("lastModified", ""),
            "load_mode": "full-file" if cached.get("is_full") else "metadata-depth-3",
            "contains_token": False,
            "file_json": file_json,
        }
        raw = json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8")
        filename = safe_filename(f"figma-snapshot-{snapshot['figma_title'] or file_key or 'export'}.json")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename={filename}")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def api_import_snapshot(self) -> None:
        self.require_username()
        payload = self.read_json()
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            self.send_json({"error": "Snapshot JSON tidak valid."}, 400)
            return
        file_json = snapshot.get("file_json")
        if not isinstance(file_json, dict) or not isinstance(file_json.get("document"), dict):
            self.send_json({"error": "Snapshot tidak berisi file_json.document yang valid."}, 400)
            return
        file_key = str(snapshot.get("file_key") or "")
        file_name = str(snapshot.get("file_name") or file_json.get("name") or "Imported Snapshot")
        figma_title = str(snapshot.get("figma_title") or file_name or file_key or "Imported Snapshot")
        session_id = secrets.token_urlsafe(24)
        SESSION_CACHE[session_id] = {
            "file_json": file_json,
            "file_key": file_key,
            "file_name": file_name,
            "token": "",
            "is_full": True,
            "snapshot_imported": True,
        }
        pages = extract_pages(file_json)
        self.send_json(
            {
                "session_id": session_id,
                "file_key": file_key,
                "file_name": file_name,
                "figma_title": figma_title,
                "last_modified": snapshot.get("last_modified") or file_json.get("lastModified", ""),
                "pages": pages,
                "frame_count": frame_count_from_pages(pages),
                "load_mode": f"snapshot:{snapshot.get('load_mode') or 'unknown'}",
                "snapshot_imported": True,
                "message": "Snapshot imported locally. No Figma API request was made.",
            }
        )
    def api_clear_session(self) -> None:
        payload = self.read_json()
        session_id = str(payload.get("session_id") or "")
        if session_id:
            SESSION_CACHE.pop(session_id, None)
        self.send_json({"ok": True})


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main() -> None:
    port = int(os.getenv("PORT", "5050"))
    server = ReusableThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Figma API Playground running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()













