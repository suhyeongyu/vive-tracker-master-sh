"""Windows startup preflight for Vive tracker: firewall + SteamVR + trackers + valid pose."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import openvr
import psutil
from rich.console import Console
from rich.live import Live
from rich.table import Table


class PreflightError(RuntimeError):
    """Raised when a preflight step fails; message is user-facing Korean text."""


_STEAMVR_PROCESS_NAMES = {"vrserver.exe", "vrmonitor.exe"}

_STEAMVR_INSTALL_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\SteamVR\bin\win64\vrstartup.exe"),
    Path(r"C:\Program Files\Steam\steamapps\common\SteamVR\bin\win64\vrstartup.exe"),
]

_VIVEHUB_SHORTCUT = Path(
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\VIVE Hub\VIVE Hub.lnk"
)

_TRACKER_STATE_LABELS = {
    "disconnected": "연결 되지 않음",
    "syncing": "동기화중",
    "lost": "트래킹 손실",
    "out_of_range": "범위 벗어남",
    "ok": "연결됨",
}

_TRACKER_STATE_STYLES = {
    "disconnected": "red",
    "syncing": "cyan",
    "lost": "yellow",
    "out_of_range": "magenta",
    "ok": "green",
}

_TRACKER_STATE_ANSI = {
    "disconnected": "\x1b[31m",   # red
    "syncing": "\x1b[36m",        # cyan
    "lost": "\x1b[33m",           # yellow
    "out_of_range": "\x1b[35m",   # magenta
    "ok": "\x1b[32m",             # green
}
_ANSI_RESET = "\x1b[0m"

_TRACKING_LABELS = {
    openvr.TrackingResult_Uninitialized: "Uninitialized",
    openvr.TrackingResult_Calibrating_InProgress: "Calibrating_InProgress",
    openvr.TrackingResult_Calibrating_OutOfRange: "Calibrating_OutOfRange",
    openvr.TrackingResult_Running_OK: "Running_OK",
    openvr.TrackingResult_Running_OutOfRange: "Running_OutOfRange",
    openvr.TrackingResult_Fallback_RotationOnly: "Fallback_RotationOnly",
}

_MAP_PENDING_RESULTS = {
    openvr.TrackingResult_Uninitialized,
    openvr.TrackingResult_Calibrating_InProgress,
    openvr.TrackingResult_Calibrating_OutOfRange,
}

_CATEGORY_TO_FW_PROFILE = {
    "Public": "Public",
    "Private": "Private",
    "DomainAuthenticated": "Domain",
    "0": "Public",
    "1": "Private",
    "2": "Domain",
}


def _log(msg: str) -> None:
    print(f"[preflight] {msg}", flush=True)


def _display_width(s: str) -> int:
    """한글 등 동아시아 wide 문자는 2칸으로 계산."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _pad_display(s: str, width: int) -> str:
    return s + " " * max(0, width - _display_width(s))


def _state_colored(state: str, width: int = 14) -> str:
    label = _TRACKER_STATE_LABELS.get(state, state)
    color = _TRACKER_STATE_ANSI.get(state, "")
    padded = _pad_display(label, width)
    if color:
        return f"{color}{padded}{_ANSI_RESET}"
    return padded


def _steamvr_running() -> bool:
    targets = {n.lower() for n in _STEAMVR_PROCESS_NAMES}
    for proc in psutil.process_iter(attrs=["name"]):
        name = (proc.info.get("name") or "").lower()
        if name in targets:
            return True
    return False


def _find_vrstartup() -> Path | None:
    for candidate in _STEAMVR_INSTALL_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _run_powershell_json(command: str, step_label: str) -> list[dict]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise PreflightError(
            f"{step_label} PowerShell 호출 실패 - {command.split('|', 1)[0].strip()}\n"
            f"      stderr: {result.stderr.strip()}"
        )
    stdout = result.stdout.strip()
    if not stdout:
        return []
    data = json.loads(stdout)
    return data if isinstance(data, list) else [data]


def _query_connection_profiles() -> list[dict]:
    return _run_powershell_json(
        "Get-NetConnectionProfile | Select-Object Name,InterfaceAlias,NetworkCategory | ConvertTo-Json",
        "[1/5]",
    )


def _query_firewall_profiles() -> list[dict]:
    return _run_powershell_json(
        "Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json",
        "[1/5]",
    )


def _is_enabled(profile: dict) -> bool:
    return str(profile.get("Enabled")).lower() in ("true", "1")


def _step1_check_firewall() -> None:
    _log("[1/5] Windows 방화벽 상태 확인 중...")

    connections = _query_connection_profiles()
    if not connections:
        _log("      연결된 네트워크 어댑터 없음 - 방화벽 검사 건너뜀")
        _log("      경고: 네트워크가 끊긴 상태입니다. DDS 통신은 실제 네트워크 복구 후 가능.")
        return

    active_fw_names: dict[str, list[str]] = {}
    for conn in connections:
        category = str(conn.get("NetworkCategory", ""))
        fw_name = _CATEGORY_TO_FW_PROFILE.get(category)
        if fw_name is None:
            continue
        label = f"{conn.get('InterfaceAlias', '?')} ({conn.get('Name', '?')})"
        active_fw_names.setdefault(fw_name, []).append(label)

    if not active_fw_names:
        _log(f"      연결된 어댑터의 NetworkCategory 미매핑: {connections}")
        _log("      경고: 방화벽 프로파일을 특정할 수 없어 검사 건너뜀")
        return

    _log(f"      현재 활성 프로파일: {', '.join(active_fw_names.keys())}")

    fw_profiles = _query_firewall_profiles()
    enabled = [p for p in fw_profiles if p["Name"] in active_fw_names and _is_enabled(p)]

    if enabled:
        lines = [
            "[1/5] Windows 방화벽이 켜져 있습니다 - DDS 통신이 차단될 수 있어 preflight를 종료합니다."
        ]
        for p in enabled:
            adapters = ", ".join(active_fw_names[p["Name"]])
            lines.append(f"      - {p['Name']} 프로파일 (어댑터: {adapters})")
        lines.append("      아래 중 하나로 조치 후 다시 실행하세요:")
        lines.append(
            "        - 관리자 PowerShell: Set-NetFirewallProfile -Profile "
            + ",".join(p["Name"] for p in enabled)
            + " -Enabled False"
        )
        lines.append("        - 또는 제어판 > Windows Defender 방화벽에서 해당 프로파일 해제")
        lines.append(
            "        - 또는 CycloneDDS UDP 포트(7400-7500 범위)에 인바운드/아웃바운드 허용 규칙 추가"
        )
        raise PreflightError("\n".join(lines))

    _log("      활성 프로파일 모두 off - 통과")


def _step2_start_steamvr(start_steamvr: bool) -> None:
    _log("[2/5] SteamVR 프로세스 확인 중...")
    if _steamvr_running():
        _log("      SteamVR 이미 실행 중")
        return

    if not start_steamvr:
        raise PreflightError(
            "[2/5] SteamVR이 실행되어 있지 않고 자동 기동이 비활성화되어 있습니다. "
            "수동으로 SteamVR을 실행한 뒤 다시 시도하세요."
        )

    vrstartup = _find_vrstartup()
    if vrstartup is None:
        raise PreflightError(
            "[2/5] SteamVR 설치를 찾을 수 없음 - Steam에서 SteamVR 설치를 확인하세요.\n"
            f"      탐색 경로:\n        "
            + "\n        ".join(str(p) for p in _STEAMVR_INSTALL_CANDIDATES)
        )

    _log(f"      vrstartup.exe 실행: {vrstartup}")
    _log("      (Steam 로그인이 필요하면 SteamVR이 자동으로 로그인 창을 띄웁니다)")
    subprocess.Popen([str(vrstartup)])


def _step3_wait_openvr(timeout: float):
    _log(f"[3/5] OpenVR 런타임 대기 중 (최대 {int(timeout)}s, Steam 로그인 시간 포함)...")
    start = time.monotonic()
    last_report = 0.0
    last_error: Exception | None = None
    while time.monotonic() - start < timeout:
        try:
            vr_system = openvr.init(openvr.VRApplication_Other)
            _log(f"      openvr.init() 성공 (경과 {time.monotonic() - start:.1f}s)")
            return vr_system
        except openvr.OpenVRError as e:
            last_error = e
            elapsed = time.monotonic() - start
            if elapsed - last_report >= 5.0:
                _log(f"      [{int(elapsed):>3}s/{int(timeout)}s] SteamVR 런타임 대기 중... ({e})")
                last_report = elapsed
            time.sleep(1.0)

    raise PreflightError(
        f"[3/5] SteamVR 런타임 응답 없음 (마지막 에러: {last_error}). "
        "Steam 로그인 창을 확인하고 로그인 완료 후 다시 실행하세요."
    )


def _find_trackers(vr_system) -> list[int]:
    return [
        i
        for i in range(openvr.k_unMaxTrackedDeviceCount)
        if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker
    ]


def _vivehub_running() -> bool:
    for proc in psutil.process_iter(attrs=["name"]):
        name = (proc.info.get("name") or "").lower()
        if "vive" in name and ("hub" in name or "console" in name):
            return True
    return False


def _launch_vivehub() -> None:
    if _vivehub_running():
        _log("      ViveHub 이미 실행 중 - 재실행 생략")
        return
    if not _VIVEHUB_SHORTCUT.is_file():
        _log(f"      ViveHub 바로가기를 찾을 수 없음: {_VIVEHUB_SHORTCUT}")
        _log("      수동으로 ViveHub를 실행해주세요")
        return
    try:
        os.startfile(str(_VIVEHUB_SHORTCUT))
        _log(f"      ViveHub 실행: {_VIVEHUB_SHORTCUT}")
    except OSError as e:
        _log(f"      ViveHub 실행 실패: {e}")


def _classify_tracker(pose, device_class: int) -> str:
    if device_class != openvr.TrackedDeviceClass_GenericTracker:
        return "disconnected"
    if not pose.bDeviceIsConnected:
        return "disconnected"
    result = int(pose.eTrackingResult)
    if result in _MAP_PENDING_RESULTS:
        return "syncing"
    if result == openvr.TrackingResult_Running_OK:
        return "ok" if pose.bPoseIsValid else "lost"
    if result == openvr.TrackingResult_Running_OutOfRange:
        return "out_of_range"
    return "lost"


def _build_status_table(vr_system, elapsed: float, total: float) -> tuple[Table, list[str]]:
    indices = _find_trackers(vr_system)
    poses = vr_system.getDeviceToAbsoluteTrackingPose(
        openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount
    )

    table = Table(
        title=f"Vive Tracker 상태  [{elapsed:4.1f}s / {total:.0f}s]",
        title_style="bold",
    )
    table.add_column("tracker", justify="left")
    table.add_column("device", justify="right")
    table.add_column("상태", justify="left")
    table.add_column("eTrackingResult", justify="left")
    table.add_column("valid", justify="center")

    states: list[str] = []
    for i, idx in enumerate(indices):
        pose = poses[idx]
        device_class = vr_system.getTrackedDeviceClass(idx)
        state = _classify_tracker(pose, device_class)
        states.append(state)
        result_label = _TRACKING_LABELS.get(int(pose.eTrackingResult), str(int(pose.eTrackingResult)))
        style = _TRACKER_STATE_STYLES[state]
        table.add_row(
            f"tracker_{i}",
            str(idx),
            f"[{style}]{_TRACKER_STATE_LABELS[state]}[/{style}]",
            result_label,
            "OK" if pose.bPoseIsValid else "FAIL",
        )

    if not indices:
        table.add_row("-", "-", "[red]연결 되지 않음[/red]", "-", "-")

    return table, states


def _step4_monitor_trackers(
    vr_system,
    total_timeout: float,
    num_trackers: int,
    initial_scan_timeout: float = 1.0,
) -> None:
    _log(
        f"[4/5] Vive Tracker 상태 모니터링 "
        f"(기대 {num_trackers}개, 최대 {int(total_timeout)}s)..."
    )

    scan_start = time.monotonic()
    initial_indices: list[int] = []
    while time.monotonic() - scan_start < initial_scan_timeout:
        initial_indices = _find_trackers(vr_system)
        if initial_indices:
            break
        time.sleep(0.2)

    if not initial_indices:
        _log("      초기 스캔에서 트래커 미검출 - ViveHub 자동 실행 시도")
        _launch_vivehub()
    else:
        _log(f"      초기 스캔: 트래커 {len(initial_indices)}개 감지 (device_index={initial_indices})")

    start = time.monotonic()
    is_tty = sys.stdout.isatty()

    if is_tty:
        console = Console()
        with Live(console=console, refresh_per_second=4, transient=False) as live:
            while time.monotonic() - start < total_timeout:
                elapsed = time.monotonic() - start
                table, states = _build_status_table(vr_system, elapsed, total_timeout)
                live.update(table)

                if len(states) >= num_trackers and all(s == "ok" for s in states):
                    _log(
                        f"      {num_trackers}개 트래커 모두 '연결됨' - "
                        f"조기 통과 (경과 {elapsed:.1f}s)"
                    )
                    return

                time.sleep(0.25)
    else:
        # non-TTY (ros2 launch 캡처): 커서 제어가 stdout prefix에 깨져 in-place 렌더 불가.
        # append-only 전략: 매초 현재 상태를 한 줄씩 계속 출력 + 상태 변화 즉시 출력.
        col_width = 14
        heartbeat_interval = 1.0
        last_log = -999.0
        prev_states: list[str] | None = None
        header_logged = False
        while time.monotonic() - start < total_timeout:
            elapsed = time.monotonic() - start
            _, states = _build_status_table(vr_system, elapsed, total_timeout)

            if not header_logged and states:
                header = " | ".join(
                    _pad_display(f"tracker_{i}", col_width) for i in range(len(states))
                )
                _log(f"      {'[time      ]':<14} | {header}")
                _log(f"      {'-' * 14}-+-{'-+-'.join(['-' * col_width] * len(states))}")
                header_logged = True

            state_changed = states != prev_states
            if state_changed or elapsed - last_log >= heartbeat_interval:
                if states:
                    row = " | ".join(_state_colored(s, col_width) for s in states)
                    _log(f"      [{elapsed:5.1f}s/{int(total_timeout):>3}s] | {row}")
                else:
                    _log(f"      [{elapsed:5.1f}s/{int(total_timeout):>3}s] | 트래커 미검출")
                last_log = elapsed
                prev_states = list(states)

            if len(states) >= num_trackers and all(s == "ok" for s in states):
                _log(
                    f"      {num_trackers}개 트래커 모두 '연결됨' - "
                    f"조기 통과 (경과 {elapsed:.1f}s)"
                )
                return

            time.sleep(0.25)

    indices = _find_trackers(vr_system)
    if not indices:
        raise PreflightError(
            f"[4/5] {int(total_timeout)}s 동안 Vive Tracker 미검출 "
            f"(기대 {num_trackers}개) - 다음 항목을 확인하세요:\n"
            "        - USB 동글이 PC에 연결되어 있는가\n"
            "        - 트래커가 켜져 있고 페어링 LED(파란색)가 안정적인가\n"
            "        - 트래커 배터리가 충전되어 있는가\n"
            "        - ViveHub 창에서 페어링 상태를 확인하세요"
        )

    poses = vr_system.getDeviceToAbsoluteTrackingPose(
        openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount
    )
    if len(indices) < num_trackers:
        header = (
            f"[4/5] {int(total_timeout)}s 내에 {num_trackers}개 트래커가 연결되지 못했습니다 "
            f"(현재 {len(indices)}개 검출)."
        )
    else:
        header = f"[4/5] {int(total_timeout)}s 내에 모든 트래커가 '연결됨' 상태에 도달하지 못했습니다."
    lines = [header]
    for i, idx in enumerate(indices):
        pose = poses[idx]
        device_class = vr_system.getTrackedDeviceClass(idx)
        state = _classify_tracker(pose, device_class)
        result_label = _TRACKING_LABELS.get(int(pose.eTrackingResult), str(int(pose.eTrackingResult)))
        lines.append(
            f"        - tracker_{i} (device={idx}): {_TRACKER_STATE_LABELS[state]} / {result_label}"
        )
        if state == "syncing":
            lines.append("          -> ViveHub에서 환경 스캔/맵 생성 완료 필요")
        elif state == "out_of_range":
            lines.append("          -> 카메라 시야에 특징점 부족 - 위치 이동 필요")
        elif state == "lost":
            lines.append("          -> 트래킹 실패 - 맵 재생성 또는 환경 특징점 확보 필요")
        elif state == "disconnected":
            lines.append("          -> 동글/페어링/배터리 확인")
    raise PreflightError("\n".join(lines))


def _step_network_reachability() -> None:
    """Warn-only: ping cyclonedds.xml peers. Ubuntu may still be booting,
    so failure here is informational - it must never block launch."""
    _log("[4.5/5] Ubuntu peer 네트워크 도달성 확인...")

    try:
        from summary_dashboard import (
            _get_local_ip_fallback,
            _get_wifi_info,
            _ping,
            _read_cyclonedds_ips,
        )
    except ImportError as e:
        _log(f"      summary_dashboard 로드 실패 ({e}) - 네트워크 체크 건너뜀")
        return

    local_ip, peers, _ = _read_cyclonedds_ips()
    if not local_ip:
        local_ip = _get_local_ip_fallback()

    _log(f"      내 IP: {local_ip}")
    _log(f"      Wi-Fi: {_get_wifi_info()}")

    if not peers:
        _log("      cyclonedds.xml에 Peer 미정의 - 네트워크 체크 건너뜀")
        return

    any_unreachable = False
    for peer in peers:
        reachable = _ping(peer)
        if reachable:
            label = _TRACKER_STATE_ANSI["ok"] + "도달 가능" + _ANSI_RESET
        else:
            label = _TRACKER_STATE_ANSI["disconnected"] + "도달 불가" + _ANSI_RESET
            any_unreachable = True
        _log(f"      peer {peer}: {label}")

    if any_unreachable:
        _log("        (Ubuntu가 부팅 중이거나 ICMP 차단이면 정상 - launch 계속 진행)")


def run_preflight(
    num_trackers: int,
    steamvr_timeout: float = 60.0,
    tracker_monitor_timeout: float = 30.0,
    start_steamvr: bool = True,
) -> None:
    """Run all 5 preflight steps. Raises PreflightError on failure.

    openvr.shutdown() is always called so the subsequent ROS 2 node can
    call openvr.init() (one-init-per-process constraint; see ADR-0002).
    """
    vr_system = None
    try:
        _step1_check_firewall()
        _step2_start_steamvr(start_steamvr)
        vr_system = _step3_wait_openvr(steamvr_timeout)
        _step4_monitor_trackers(vr_system, tracker_monitor_timeout, num_trackers)
        _step_network_reachability()
    finally:
        if vr_system is not None:
            _log("[5/5] preflight 핸들 해제 (openvr.shutdown)")
            try:
                openvr.shutdown()
            except Exception as e:
                _log(f"      openvr.shutdown 경고 (무시): {e}")
    _log("preflight 통과 - ROS 2 노드 기동 진행")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Vive tracker Windows preflight")
    parser.add_argument(
        "--num-trackers",
        type=int,
        default=1,
        help="기대 트래커 개수 (이만큼 모두 'ok'가 되어야 통과)",
    )
    parser.add_argument(
        "--steamvr-timeout",
        type=float,
        default=60.0,
        help="SteamVR 런타임 대기 최대 시간 (초)",
    )
    parser.add_argument(
        "--tracker-monitor-timeout",
        type=float,
        default=30.0,
        help="트래커 상태 모니터링 최대 시간 (초)",
    )
    args = parser.parse_args()

    try:
        run_preflight(
            num_trackers=args.num_trackers,
            steamvr_timeout=args.steamvr_timeout,
            tracker_monitor_timeout=args.tracker_monitor_timeout,
        )
        return 0
    except PreflightError as e:
        print(f"\n[preflight] 실패:\n{e}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
