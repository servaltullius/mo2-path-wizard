"""실행 중인 Mod Organizer 2 감지(Windows 전용).

MO2는 종료할 때 메모리의 설정을 ModOrganizer.ini에 다시 쓰므로, MO2가 켜진 상태에서 INI를 고치면
변경이 덮어써질 수 있다. 적용 전에 같은 인스턴스의 MO2가 실행 중인지 확인한다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_MO2_EXE_NAMES = ("modorganizer.exe",)


@dataclass(frozen=True)
class Mo2Status:
    supported: bool  # 이 환경에서 프로세스 목록을 볼 수 있는지
    running: tuple[Path, ...]  # 실행 중인 ModOrganizer.exe 경로들(경로를 못 읽으면 이름만)
    same_instance: bool  # 이 INI를 쓰는 MO2가 실행 중

    @property
    def any_running(self) -> bool:
        return bool(self.running)


def _list_windows_process_paths() -> list[Path]:
    import ctypes
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        raise OSError("CreateToolhelp32Snapshot failed")

    found: list[Path] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            name = entry.szExeFile
            if name.lower() in _MO2_EXE_NAMES:
                path = Path(name)
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, entry.th32ProcessID)
                if handle:
                    try:
                        buf = ctypes.create_unicode_buffer(32768)
                        size = wintypes.DWORD(len(buf))
                        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                            path = Path(buf.value)
                    finally:
                        kernel32.CloseHandle(handle)
                found.append(path)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return found


def list_running_mo2() -> list[Path] | None:
    """실행 중인 ModOrganizer.exe 경로 목록. 확인할 수 없는 환경이면 None."""
    if sys.platform != "win32":
        return None
    try:
        return _list_windows_process_paths()
    except Exception:
        return None


def _same_dir(a: Path, b: Path) -> bool:
    return str(a).replace("\\", "/").rstrip("/").lower() == str(b).replace("\\", "/").rstrip("/").lower()


def check_mo2_status(ini_path: Path | None, *, running: list[Path] | None = None) -> Mo2Status:
    """ini_path를 쓰는 MO2가 실행 중인지 판단한다.

    포터블 인스턴스는 ModOrganizer.exe가 INI와 같은 폴더에 있다. 경로를 읽지 못한 프로세스나
    전역(AppData) 인스턴스는 같은 인스턴스일 가능성을 배제할 수 없으므로 same_instance로 본다.
    """
    if running is None:
        running = list_running_mo2()
    if running is None:
        return Mo2Status(supported=False, running=(), same_instance=False)

    same = False
    portable = ini_path is not None and (ini_path.parent / "ModOrganizer.exe").is_file()
    for exe in running:
        if not exe.is_absolute():
            same = True  # 경로를 모르면 보수적으로
        elif ini_path is None or not portable:
            same = True
        elif _same_dir(exe.parent, ini_path.parent):
            same = True
    return Mo2Status(supported=True, running=tuple(running), same_instance=same)
