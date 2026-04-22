"""One-shot startup summary: IP config + Wi-Fi. Prints once, then exits."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FALLBACK_CDDS_XML = _REPO_ROOT / "cyclonedds.xml"


def _resolve_cyclonedds_xml() -> Path | None:
    uri = os.environ.get("CYCLONEDDS_URI", "").strip()
    if uri:
        path = Path(uri.replace("file://", "").strip())
        if path.is_file():
            return path
    if _FALLBACK_CDDS_XML.is_file():
        return _FALLBACK_CDDS_XML
    return None


def _read_cyclonedds_ips() -> tuple[str | None, list[str], Path | None]:
    path = _resolve_cyclonedds_xml()
    if path is None:
        return None, [], None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None, [], path
    local_ip: str | None = None
    peers: list[str] = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "NetworkInterface":
            addr = elem.get("address")
            if addr:
                local_ip = addr
        elif tag == "Peer":
            addr = elem.get("address")
            if addr:
                peers.append(addr)
    return local_ip, peers, path


def _get_local_ip_fallback() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "unknown"


def _ping(host: str) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1000", host],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _get_wifi_info() -> str:
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "N/A"
    if result.returncode != 0:
        return "이더넷 또는 무선 어댑터 없음"
    match = re.search(r"(\d+)%", result.stdout)
    if match:
        return f"Wi-Fi {match.group(1)}%"
    return "Wi-Fi 연결됨 (신호 수치 파싱 실패)"


def _render_summary(
    local_ip: str,
    peer_info: list[tuple[str, bool]],
    cdds_path: Path | None,
    wifi: str,
) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", no_wrap=True)
    table.add_column("Value")

    table.add_row("내 IP", local_ip)
    if peer_info:
        for addr, reachable in peer_info:
            tag = "[OK] 도달" if reachable else "[NG] 도달 불가"
            table.add_row("상대방 IP", f"{addr}  {tag}")
    else:
        table.add_row("상대방 IP", "cyclonedds.xml에 Peer 미정의")

    table.add_row("네트워크", wifi)

    subtitle = cdds_path.name if cdds_path else "no cyclonedds.xml"
    return Panel(
        table,
        title="연결 상태",
        subtitle=subtitle,
        box=box.ASCII,
        expand=False,
    )


def main() -> None:
    local_ip, peers, cdds_path = _read_cyclonedds_ips()
    if not local_ip:
        local_ip = _get_local_ip_fallback()
    peer_info = [(addr, _ping(addr)) for addr in peers]
    wifi = _get_wifi_info()

    Console(legacy_windows=False, force_terminal=False, no_color=True).print(
        _render_summary(local_ip, peer_info, cdds_path, wifi)
    )


if __name__ == "__main__":
    main()
