#!/usr/bin/env python3
"""Configure SteamVR to run without a physical headset using the null driver (Windows & Linux)."""

import json
import os
import winreg
from pathlib import Path

def find_steam_dir():
    # 1. Windows 레지스트리에서 Steam 설치 경로 확인
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "SteamPath")
        win_path = Path(path)
        if (win_path / "steamapps/common/SteamVR").exists():
            return win_path
    except (FileNotFoundError, OSError):
        pass

    # 2. 일반적인 기본 경로들 확인 (Windows & Linux 공통)
    possible_dirs = [
        Path("C:/Program Files (x86)/Steam"),
        Path("D:/SteamLibrary"),
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
    ]

    for d in possible_dirs:
        if (d / "steamapps/common/SteamVR").exists():
            return d

    raise FileNotFoundError("SteamVR 설치 디렉토리를 찾을 수 없습니다.")

def update_json(path: Path, updates: dict):
    # 파일이 존재하지 않을 경우를 대비한 예외 처리
    if not path.exists():
        print(f"Warning: {path} 파일을 찾을 수 없어 건너뜁니다.")
        return

    try:
        # SteamVR 설정 파일은 가끔 주석이 포함되어 있어 일반 json.loads가 실패할 수 있음
        content = path.read_text(encoding='utf-8')
        data = json.loads(content)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return

    for section, values in updates.items():
        if section not in data:
            data[section] = {}
        data[section].update(values)
        
    path.write_text(json.dumps(data, indent='\t'), encoding='utf-8')

def main():
    try:
        steam = find_steam_dir()
        print(f"Found Steam: {steam}")

        # 1. Null 드라이버 활성화
        null_settings = steam / "steamapps/common/SteamVR/drivers/null/resources/settings/default.vrsettings"
        update_json(null_settings, {"driver_null": {"enable": True}})
        print(f"Updated: {null_settings}")

        # 2. SteamVR 설정 (HMD 필수 체크 해제 등)
        steamvr_settings = steam / "steamapps/common/SteamVR/resources/settings/default.vrsettings"
        update_json(steamvr_settings, {
            "steamvr": {
                "requireHmd": False,
                "forcedDriver": "null",
                "activateMultipleDrivers": True,
            }
        })
        print(f"Updated: {steamvr_settings}")

        print("\n설정이 완료되었습니다! SteamVR을 재시작하세요.")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()