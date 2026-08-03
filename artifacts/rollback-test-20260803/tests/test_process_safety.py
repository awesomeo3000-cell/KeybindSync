from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import unittest
from ctypes import wintypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wow_keybind_app as app


class ProcessMatchingTests(unittest.TestCase):
    def test_renamed_loader_in_config_folder_is_blocked(self) -> None:
        config = Path(r"C:\Tools\Loader\Config.ini")
        running = [app.RunningProcess(123, "anything.exe", Path(r"C:\Tools\Loader\anything.exe"))]

        self.assertEqual(
            app.match_blocking_processes(running, app.APPLY_BLOCKING_PROCESSES, config),
            ["Config.ini folder process (anything.exe)"],
        )

    def test_explicit_loader_outside_config_folder_is_blocked(self) -> None:
        config = Path(r"C:\Tools\Config\Config.ini")
        loader = Path(r"D:\Portable\renamed.exe")
        running = [app.RunningProcess(123, "renamed.exe", loader)]

        self.assertEqual(
            app.match_blocking_processes(running, app.APPLY_BLOCKING_PROCESSES, config, loader),
            ["Selected loader (renamed.exe)"],
        )

    def test_explicit_loader_name_is_fallback_when_path_is_unavailable(self) -> None:
        loader = Path(r"D:\Portable\renamed.exe")
        running = [app.RunningProcess(123, "renamed.exe")]

        self.assertEqual(
            app.match_blocking_processes(running, app.APPLY_BLOCKING_PROCESSES, loader_executable=loader),
            ["Selected loader (renamed.exe)"],
        )

    def test_unrelated_process_is_not_blocked(self) -> None:
        config = Path(r"C:\Tools\Loader\Config.ini")
        running = [app.RunningProcess(123, "notes.exe", Path(r"C:\Other\notes.exe"))]

        self.assertEqual(
            app.match_blocking_processes(running, app.APPLY_BLOCKING_PROCESSES, config),
            [],
        )

    def test_current_process_is_not_blocked(self) -> None:
        config = Path(sys.executable).parent / "Config.ini"
        running = [app.RunningProcess(os.getpid(), Path(sys.executable).name, Path(sys.executable))]

        self.assertEqual(
            app.match_blocking_processes(running, app.APPLY_BLOCKING_PROCESSES, config),
            [],
        )

    def test_known_wow_process_is_blocked_without_a_path(self) -> None:
        running = [app.RunningProcess(123, "Wow.exe")]

        self.assertEqual(
            app.match_blocking_processes(running, app.APPLY_BLOCKING_PROCESSES),
            ["World of Warcraft"],
        )


@unittest.skipUnless(os.name == "nt", "Windows file sharing semantics")
class ExclusiveAccessTests(unittest.TestCase):
    def test_process_enumerator_includes_current_python_process(self) -> None:
        running = app._windows_running_processes()
        current = next((process for process in running if process.pid == os.getpid()), None)
        self.assertIsNotNone(current)
        self.assertIsNotNone(current.executable)

    def test_detects_file_opened_without_sharing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "Config.ini"
            target.write_text("[General]\n", encoding="utf-8")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = (
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            )
            create_file.restype = wintypes.HANDLE
            handle = create_file(str(target), 0x80000000, 0, None, 3, 0x80, None)
            self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
            try:
                self.assertTrue(app.file_has_exclusive_access_conflict(target))
            finally:
                kernel32.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
