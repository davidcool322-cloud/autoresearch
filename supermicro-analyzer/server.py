#!/usr/bin/env python3
"""Small local web app that summarizes public Supermicro product pages."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
from dataclasses import asdict, dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
OFFICIAL_BASE = "https://www.supermicro.com"
READER_BASE = "https://r.jina.ai/"
MODEL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9+.-]{1,39}$")
ProgressCallback = Callable[[int, str], None]
DC_SCM_SOURCE = (
    "https://www.supermicro.com/en/support/manuals/product/system/"
    "sys-222c-tn/Content/introduction/dc-scm-222c-tn.htm"
)


class ProductNotFound(Exception):
    """Raised when neither supported official product page exists."""


class SourceUnavailable(Exception):
    """Raised when the official page cannot be read."""


@dataclass(frozen=True)
class Product:
    model: str
    category: str
    name: str
    motherboard_model: str | None
    cpu: str
    memory: list[str]
    bmc: bool
    rot: bool
    bios_version: str | None
    bmc_version: str | None
    sources: list[str]


def _fetch_official_page(url: str) -> str:
    """Read an official page through a text gateway because the CDN blocks servers."""
    request = Request(
        READER_BASE + url,
        headers={"User-Agent": "SupermicroModelAnalyzer/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SourceUnavailable from exc


def _clean_markdown(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("**", "").replace("™", "™").replace("®", "®")
    value = re.sub(r"\s*\*\s*", "；", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"；{2,}", "；", value)
    return value.strip(" ；")


def _spec_items(value: str) -> list[str]:
    return [item.strip() for item in value.split("；") if item.strip()]


def _segment(text: str, start: str, end: str) -> str | None:
    match = re.search(
        re.escape(start) + r"(.*?)" + re.escape(end),
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return _clean_markdown(match.group(1)) if match else None


def _model_regex(model: str) -> str:
    return re.escape(model).replace(r"\-", r"\s*-\s*")


def _normalize_model(raw_model: str) -> str:
    return re.sub(r"\s*-\s*", "-", raw_model.strip().upper())


def _is_missing_page(text: str) -> bool:
    beginning = text[:700].lower()
    return (
        "title: not found" in beginning
        or "markdown content:\n404" in beginning
        or "title: access denied" in beginning
        or "target url returned error 403" in beginning
    )


def _parse_system(model: str, url: str, text: str) -> Product | None:
    if _is_missing_page(text) or not re.search(
        rf"#\s+.*\b{_model_regex(model)}\b", text, flags=re.IGNORECASE
    ):
        return None

    normalized = re.sub(r"\s+", " ", text)
    name_match = re.search(
        rf"#\s+(.+?\b{_model_regex(model)}\b)", text, flags=re.IGNORECASE
    )
    cpu_match = re.search(
        r"Processor\s+(.*?)(?:\s+GPU\s+|\s+System Memory\s+)",
        normalized,
        flags=re.IGNORECASE,
    )
    cpu = _clean_markdown(cpu_match.group(1)) if cpu_match else None
    memory = _segment(normalized, "System Memory ", " Drive Bays Configuration ")
    motherboard_match = re.search(
        r"\bMotherboard\s+(?:Super\s+)?([A-Z0-9][A-Z0-9+.-]+)",
        normalized,
        flags=re.IGNORECASE,
    )
    if not name_match or not cpu or not memory:
        return None

    return Product(
        model=model,
        category="系統",
        name=_clean_markdown(name_match.group(1)),
        motherboard_model=(
            motherboard_match.group(1).upper() if motherboard_match else None
        ),
        cpu=cpu,
        memory=_spec_items(memory),
        bmc=bool(re.search(r"\b(?:BMC|IPMI)\b", text, flags=re.IGNORECASE)),
        rot=bool(re.search(r"\bRoT\b|Root of Trust", text, flags=re.IGNORECASE)),
        bios_version=None,
        bmc_version=None,
        sources=[url],
    )


def _parse_motherboard(model: str, url: str, text: str) -> Product | None:
    if _is_missing_page(text) or not re.search(
        rf"\bMBD-{re.escape(model)}\b", text, flags=re.IGNORECASE
    ):
        return None

    normalized = re.sub(r"\s+", " ", text)
    title_block_match = re.search(
        rf"#\s+{re.escape(model)}[^\n]*\n(.*?)### Key Features",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    title_lines = (
        [
            line.strip()
            for line in title_block_match.group(1).splitlines()
            if line.strip() and not line.lstrip().startswith("[![")
        ]
        if title_block_match
        else []
    )
    cpu = _segment(normalized, "Processor CPU", "Core Count")
    memory = _segment(normalized, "System Memory Memory", "Memory Voltage")
    if not title_lines or not cpu or not memory:
        return None

    sources = [url]
    bmc = bool(re.search(r"\b(?:BMC|IPMI)\b", text, flags=re.IGNORECASE))
    rot = bool(re.search(r"\bRoT\b|Root of Trust", text, flags=re.IGNORECASE))

    # Some DC-SCM boards keep BMC and RoT on the module rather than the baseboard.
    if "DC-SCM" in text and (not bmc or not rot):
        try:
            module_text = _fetch_official_page(DC_SCM_SOURCE)
        except SourceUnavailable:
            module_text = ""
        if re.search(rf"\b{re.escape(model)}\b", module_text, flags=re.IGNORECASE):
            bmc = bmc or bool(
                re.search(r"\b(?:BMC|IPMI)\b", module_text, flags=re.IGNORECASE)
            )
            rot = rot or bool(
                re.search(r"\bRoT\b|Root of Trust", module_text, flags=re.IGNORECASE)
            )
            sources.append(DC_SCM_SOURCE)

    return Product(
        model=model,
        category="主機板",
        name=_clean_markdown(title_lines[0]),
        motherboard_model=None,
        cpu=cpu,
        memory=_spec_items(memory),
        bmc=bmc,
        rot=rot,
        bios_version=None,
        bmc_version=None,
        sources=sources,
    )


def _report(
    progress: ProgressCallback | None,
    percent: int,
    message: str,
) -> None:
    if progress:
        progress(percent, message)


def _attach_motherboard_capabilities(
    product: Product,
    progress: ProgressCallback | None = None,
) -> Product:
    if product.category != "系統" or not product.motherboard_model:
        return product

    _report(progress, 55, "確認搭配主機板")
    motherboard_url = (
        f"{OFFICIAL_BASE}/en/products/motherboard/{product.motherboard_model}"
    )
    try:
        motherboard_text = _fetch_official_page(motherboard_url)
    except SourceUnavailable:
        return product
    motherboard = _parse_motherboard(
        product.motherboard_model,
        motherboard_url,
        motherboard_text,
    )
    if not motherboard:
        return product

    _report(progress, 70, "確認 BMC 與 RoT")
    return replace(
        product,
        bmc=product.bmc or motherboard.bmc,
        rot=motherboard.rot,
        sources=[*product.sources, *motherboard.sources],
    )


def _attach_firmware(
    product: Product,
    progress: ProgressCallback | None = None,
) -> Product:
    firmware_model = product.motherboard_model or (
        product.model if product.category == "主機板" else None
    )
    if not firmware_model:
        return product

    _report(progress, 82, "確認最新韌體版本")
    firmware_url = (
        f"{OFFICIAL_BASE}/en/support/resources/downloadcenter/"
        f"firmware/MBD-{firmware_model}/BIOS"
    )
    try:
        firmware_text = _fetch_official_page(firmware_url)
    except SourceUnavailable:
        return product
    if _is_missing_page(firmware_text):
        return product

    bios_match = re.search(
        r"BIOS Revision:\s*([^\n|]+)", firmware_text, flags=re.IGNORECASE
    )
    bmc_match = re.search(
        r"BMC Firmware Revision:\s*([^\n|]+)",
        firmware_text,
        flags=re.IGNORECASE,
    )
    if not bios_match and not bmc_match:
        return product

    _report(progress, 92, "整理產品資料")
    return replace(
        product,
        bios_version=bios_match.group(1).strip() if bios_match else None,
        bmc_version=bmc_match.group(1).strip() if bmc_match else None,
        sources=[*product.sources, firmware_url],
    )


def lookup_product(
    raw_model: str,
    progress: ProgressCallback | None = None,
) -> Product:
    _report(progress, 5, "驗證型號")
    model = _normalize_model(raw_model)
    if not MODEL_PATTERN.fullmatch(model):
        raise ProductNotFound

    candidates = (
        (
            f"{OFFICIAL_BASE}/en/products/system/datasheet/{model.lower()}",
            _parse_system,
        ),
        (
            f"{OFFICIAL_BASE}/en/products/motherboard/{model}",
            _parse_motherboard,
        ),
    )
    source_failed = False
    for index, (url, parser) in enumerate(candidates):
        _report(
            progress,
            15 if index == 0 else 45,
            "確認系統產品頁" if index == 0 else "確認主機板產品頁",
        )
        try:
            text = _fetch_official_page(url)
        except SourceUnavailable:
            source_failed = True
            continue
        product = parser(model, url, text)
        if product:
            _report(
                progress,
                40 if index == 0 else 65,
                "取得系統規格" if index == 0 else "取得主機板規格",
            )
            product = _attach_motherboard_capabilities(product, progress)
            return _attach_firmware(product, progress)

    if source_failed:
        raise SourceUnavailable
    raise ProductNotFound


class AppHandler(BaseHTTPRequestHandler):
    server_version = "SupermicroModelAnalyzer/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/products/progress":
            self._serve_progress(parse_qs(parsed.query).get("model", [""])[0])
            return
        if parsed.path == "/api/products":
            self._serve_api(parse_qs(parsed.query).get("model", [""])[0])
            return
        self._serve_static(parsed.path)

    def _serve_api(self, model: str) -> None:
        try:
            product = lookup_product(model)
        except (ProductNotFound, SourceUnavailable):
            self._send_json(404, {"error": "再次確認型號"})
            return
        self._send_json(200, asdict(product))

    def _serve_progress(self, model: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def send_event(event: str, payload: dict[str, object]) -> None:
            content = (
                f"event: {event}\n"
                f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            ).encode("utf-8")
            self.wfile.write(content)
            self.wfile.flush()

        try:
            product = lookup_product(
                model,
                progress=lambda percent, message: send_event(
                    "progress",
                    {"percent": percent, "message": message},
                ),
            )
            send_event("progress", {"percent": 100, "message": "查詢完成"})
            send_event("result", asdict(product))
        except (ProductNotFound, SourceUnavailable):
            send_event("lookup-error", {"error": "再次確認型號"})
        except (BrokenPipeError, ConnectionResetError):
            return

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR not in target.parents or not target.is_file():
            self.send_error(404)
            return
        content = target.read_bytes()
        content_type, _ = mimetypes.guess_type(target.name)
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.address_string()} - {message % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Supermicro model analyzer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Open http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
