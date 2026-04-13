from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from typing import Any

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None

try:
    from pywinauto import Desktop
except Exception:
    Desktop = None


LOGIN_TITLE_KEYWORDS = ("登录", "login", "用户登录", "账户登录")
LOGIN_BUTTON_KEYWORDS = ("登录", "login", "log in", "连接", "确定", "enter")
PASSWORD_KEYWORDS = ("密码", "password", "passwd", "pwd")
REMEMBER_KEYWORDS = ("记住", "remember")
AUTO_LOGIN_KEYWORDS = ("自动登录", "auto")
EXTRA_AUTH_KEYWORDS = ("验证码", "滑块", "短信", "otp", "动态码", "校验码", "口令", "通讯密码")
BAD_PASSWORD_KEYWORDS = ("密码错误", "账号或密码错误", "登录失败", "认证失败")
MAIN_WINDOW_KEYWORDS = ("交易", "行情", "自选", "资金", "持仓", "委托", "qmt交易端", "xtminiqmt")
PASSWORD_FALLBACK_EDIT_INDEX = 1
CAPTCHA_AUTO_FILLED_EDIT_INDEX = 2
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_CHAR = 0x0102


@dataclass(frozen=True)
class ControlDescriptor:
    control_type: str
    name: str = ""
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    visible: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class WindowDescriptor:
    handle: int
    process_id: int | None
    title: str
    class_name: str = ""
    controls: tuple[ControlDescriptor, ...] = ()
    visible: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class WindowClassification:
    handle: int
    process_id: int | None
    title: str
    login_candidate: bool
    main_candidate: bool
    extra_auth_detected: bool
    bad_password_detected: bool
    password_edit_index: int | None
    submit_button_index: int | None
    visible_edit_count: int
    summary: str = ""


@dataclass(frozen=True)
class DesktopObservation:
    process_id: int | None = None
    window_handle: int | None = None
    window_title: str = ""
    login_window_found: bool = False
    main_window_found: bool = False
    extra_auth_detected: bool = False
    bad_password_detected: bool = False
    password_edit_index: int | None = None
    submit_button_index: int | None = None
    visible_edit_count: int = 0
    port_ready: bool = False
    screenshot_path: str = ""
    window_titles: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "window_handle": self.window_handle,
            "window_title": self.window_title,
            "login_window_found": bool(self.login_window_found),
            "main_window_found": bool(self.main_window_found),
            "extra_auth_detected": bool(self.extra_auth_detected),
            "bad_password_detected": bool(self.bad_password_detected),
            "password_edit_index": self.password_edit_index,
            "submit_button_index": self.submit_button_index,
            "visible_edit_count": int(self.visible_edit_count),
            "port_ready": bool(self.port_ready),
            "screenshot_path": self.screenshot_path,
            "window_titles": list(self.window_titles),
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class LaunchResult:
    ok: bool
    process_id: int | None
    started: bool
    already_running: bool
    message: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "process_id": self.process_id,
            "started": bool(self.started),
            "already_running": bool(self.already_running),
            "message": self.message,
        }


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize_text(value: str) -> str:
    return _safe_str(value).casefold()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = _normalize_text(text)
    return any(keyword.casefold() in normalized for keyword in keywords)


def _rect_sort_key(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = rect
    return top, left, bottom, right


def _nearest_label(edit: ControlDescriptor, labels: list[ControlDescriptor]) -> str:
    edit_left, edit_top, edit_right, edit_bottom = edit.rect
    best_text = ""
    best_score = None
    for label in labels:
        if not label.name:
            continue
        label_left, label_top, label_right, label_bottom = label.rect
        if label_top > edit_bottom + 16:
            continue
        vertical_gap = abs(edit_top - label_bottom)
        if label_right < edit_left:
            horizontal_gap = edit_left - label_right
        elif label_left > edit_right:
            horizontal_gap = label_left - edit_right
        else:
            horizontal_gap = 0
        score = vertical_gap * 5 + horizontal_gap
        if best_score is None or score < best_score:
            best_score = score
            best_text = label.name
    return best_text


def _classify_window_descriptor(descriptor: WindowDescriptor, *, port_ready: bool = False) -> WindowClassification:
    visible_controls = [control for control in descriptor.controls if control.visible]
    edits = sorted(
        [control for control in visible_controls if control.control_type == "Edit" and control.enabled],
        key=lambda item: _rect_sort_key(item.rect),
    )
    text_controls = sorted(
        [
            control
            for control in visible_controls
            if control.control_type in {"Text", "Button", "CheckBox", "ComboBox", "Document", "Pane"} and control.name
        ],
        key=lambda item: _rect_sort_key(item.rect),
    )
    buttons = sorted(
        [control for control in visible_controls if control.control_type == "Button" and control.enabled],
        key=lambda item: _rect_sort_key(item.rect),
    )
    text_blob = " ".join(
        [descriptor.title] + [control.name for control in text_controls if control.name] + [control.name for control in edits if control.name]
    )
    extra_auth_detected = _contains_any(text_blob, EXTRA_AUTH_KEYWORDS)
    bad_password_detected = _contains_any(text_blob, BAD_PASSWORD_KEYWORDS)
    password_edit_index = None
    for index, edit in enumerate(edits):
        label_text = f"{edit.name} {_nearest_label(edit, text_controls)}"
        if _contains_any(label_text, EXTRA_AUTH_KEYWORDS):
            extra_auth_detected = True
        if _contains_any(label_text, PASSWORD_KEYWORDS):
            password_edit_index = index
            break
    if password_edit_index is None:
        if len(edits) == 1:
            password_edit_index = 0
        elif len(edits) >= 2:
            password_edit_index = PASSWORD_FALLBACK_EDIT_INDEX
    submit_button_index = None
    for index, button in enumerate(buttons):
        if _contains_any(button.name, LOGIN_BUTTON_KEYWORDS):
            submit_button_index = index
            break
    login_signal = _contains_any(text_blob, LOGIN_TITLE_KEYWORDS + PASSWORD_KEYWORDS + REMEMBER_KEYWORDS + AUTO_LOGIN_KEYWORDS)
    main_signal = _contains_any(text_blob, MAIN_WINDOW_KEYWORDS)
    login_candidate = bool(edits) and (
        (submit_button_index is not None and len(edits) <= 3)
        or login_signal
        or extra_auth_detected
        or bad_password_detected
    )
    if main_signal and not login_signal and len(edits) > 3:
        login_candidate = False
    main_candidate = (not login_candidate) and (main_signal or bool(port_ready and descriptor.title and len(edits) > 3))
    summary = f"title={descriptor.title}; class={descriptor.class_name}; edits={len(edits)}; buttons={len(buttons)}"
    return WindowClassification(
        handle=descriptor.handle,
        process_id=descriptor.process_id,
        title=descriptor.title,
        login_candidate=login_candidate,
        main_candidate=main_candidate,
        extra_auth_detected=extra_auth_detected,
        bad_password_detected=bad_password_detected,
        password_edit_index=password_edit_index,
        submit_button_index=submit_button_index,
        visible_edit_count=len(edits),
        summary=summary,
    )


class WindowsDesktopHarness:
    def __init__(self, *, screenshot_dir: str = "") -> None:
        self._screenshot_dir = Path(screenshot_dir) if screenshot_dir else Path(tempfile.gettempdir()) / "xtqmt_miniqmt_login"

    def _desktop(self):
        if Desktop is None:
            raise RuntimeError("pywinauto_unavailable")
        return Desktop(backend="uia")

    def port_ready(self, host: str = "127.0.0.1", port: int = 58610, timeout_ms: int = 300) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(max(0.1, float(timeout_ms) / 1000.0))
        try:
            sock.connect((host, int(port)))
            return True
        except Exception:
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def is_interactive_desktop(self) -> bool:
        try:
            user32 = ctypes.windll.user32
            desktop = user32.OpenInputDesktop(0, False, 0x0100)
            if not desktop:
                return False
            user32.CloseDesktop(desktop)
            return True
        except Exception:
            return False

    def list_process_ids(self) -> tuple[int, ...]:
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq XtMiniQmt.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=10,
                check=False,
            )
        except Exception:
            return ()
        process_ids: list[int] = []
        for row in csv.reader([line for line in str(proc.stdout or "").splitlines() if line.strip()]):
            if not row:
                continue
            if _safe_str(row[0]).casefold() != "xtminiqmt.exe":
                continue
            try:
                process_ids.append(int(_safe_str(row[1]).replace(",", "")))
            except Exception:
                continue
        return tuple(process_ids)

    def launch_or_attach(self, qmt_exe: str) -> LaunchResult:
        running = self.list_process_ids()
        if running:
            return LaunchResult(
                ok=True,
                process_id=running[0],
                started=False,
                already_running=True,
                message="XtMiniQmt already running",
            )
        try:
            process = subprocess.Popen([qmt_exe])
        except Exception as exc:
            return LaunchResult(
                ok=False,
                process_id=None,
                started=False,
                already_running=False,
                message=f"failed to start XtMiniQmt: {exc}",
            )
        return LaunchResult(
            ok=True,
            process_id=int(process.pid),
            started=True,
            already_running=False,
            message="XtMiniQmt started",
        )

    def observe(self, *, process_id: int | None = None, port_host: str = "127.0.0.1", port_num: int = 58610) -> DesktopObservation:
        port_ready = self.port_ready(host=port_host, port=port_num)
        interactive_desktop = self.is_interactive_desktop()
        window_descriptors: list[WindowDescriptor] = []
        pywinauto_window_count = 0
        target_process_ids = [process_id] if process_id else list(self.list_process_ids())
        if Desktop is not None:
            desktop = self._desktop()
            for pid in target_process_ids:
                try:
                    windows = desktop.windows(process=pid, visible_only=False)
                except Exception:
                    windows = []
                pywinauto_window_count += len(windows)
                for window in windows:
                    descriptor = self._window_to_descriptor(window)
                    if descriptor.title or descriptor.controls:
                        window_descriptors.append(descriptor)
        host_window_descriptors: list[WindowDescriptor] = []
        if target_process_ids and not window_descriptors:
            host_window_descriptors = self._host_window_descriptors(target_process_ids)
            window_descriptors.extend(host_window_descriptors)
        classifications = [_classify_window_descriptor(descriptor, port_ready=port_ready) for descriptor in window_descriptors]
        login_candidates = sorted(
            [item for item in classifications if item.login_candidate],
            key=lambda item: (item.visible_edit_count, len(item.title)),
            reverse=True,
        )
        main_candidates = sorted(
            [item for item in classifications if item.main_candidate],
            key=lambda item: (len(item.title), item.visible_edit_count),
            reverse=True,
        )
        login_candidate = login_candidates[0] if login_candidates else None
        main_candidate = main_candidates[0] if main_candidates else None
        window_titles = tuple(dict.fromkeys(descriptor.title for descriptor in window_descriptors if descriptor.title))
        selected_process_id = process_id
        selected_handle = None
        selected_title = ""
        password_edit_index = None
        submit_button_index = None
        if login_candidate is not None:
            selected_process_id = login_candidate.process_id
            selected_handle = login_candidate.handle
            selected_title = login_candidate.title
            password_edit_index = login_candidate.password_edit_index
            submit_button_index = login_candidate.submit_button_index
        elif main_candidate is not None:
            selected_process_id = main_candidate.process_id
            selected_handle = main_candidate.handle
            selected_title = main_candidate.title
        screenshot_path, screenshot_attempted, screenshot_capture_error = self.capture_screenshot_details()
        evidence = {
            "interactive_desktop": bool(interactive_desktop),
            "pywinauto_window_count": int(pywinauto_window_count),
            "host_window_fallback_used": bool(host_window_descriptors),
            "host_visible_windows": [self._window_descriptor_payload(item) for item in host_window_descriptors],
            "window_classifications": [item.summary for item in classifications],
            "selected_login_title": login_candidate.title if login_candidate else "",
            "selected_main_title": main_candidate.title if main_candidate else "",
            "screenshot_capture_attempted": bool(screenshot_attempted),
            "screenshot_capture_error": screenshot_capture_error,
        }
        return DesktopObservation(
            process_id=selected_process_id,
            window_handle=selected_handle,
            window_title=selected_title,
            login_window_found=login_candidate is not None,
            main_window_found=main_candidate is not None,
            extra_auth_detected=any(item.extra_auth_detected for item in classifications),
            bad_password_detected=any(item.bad_password_detected for item in classifications),
            password_edit_index=password_edit_index,
            submit_button_index=submit_button_index,
            visible_edit_count=login_candidate.visible_edit_count if login_candidate else 0,
            port_ready=port_ready,
            screenshot_path=screenshot_path,
            window_titles=window_titles,
            evidence=evidence,
        )

    def capture_screenshot(self) -> str:
        path, _, _ = self.capture_screenshot_details()
        return path

    def capture_screenshot_details(self) -> tuple[str, bool, str]:
        if ImageGrab is None:
            return "", False, "imagegrab_unavailable"
        try:
            image = ImageGrab.grab()
        except Exception as exc:
            return "", True, f"grab_failed: {exc}"
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self._screenshot_dir / f"miniqmt_login_{stamp}.png"
        try:
            image.save(path)
        except Exception as exc:
            return "", True, f"save_failed: {exc}"
        return str(path), True, ""

    def submit_saved_password(self, observation: DesktopObservation, password: str) -> ActionResult:
        if not observation.window_handle:
            return ActionResult(ok=False, code="login_window_not_found", message="login window handle missing")
        try:
            window = self._desktop().window(handle=observation.window_handle).wrapper_object()
        except Exception as exc:
            return ActionResult(ok=False, code="login_window_not_found", message=f"login window attach failed: {exc}")
        self._prepare_window(window)
        edits = self._sorted_descendants(window, "Edit")
        if observation.password_edit_index is None or observation.password_edit_index >= len(edits):
            return ActionResult(ok=False, code="password_field_missing", message="password field not found")
        password_edit = edits[observation.password_edit_index]
        remember_enabled = self._enable_matching_toggle(window, REMEMBER_KEYWORDS)
        auto_login_enabled = self._enable_matching_toggle(window, AUTO_LOGIN_KEYWORDS)
        ignored_edit_indices = [CAPTCHA_AUTO_FILLED_EDIT_INDEX] if len(edits) > CAPTCHA_AUTO_FILLED_EDIT_INDEX else []

        password_rect = self._safe_rect(password_edit)
        if not self._message_click(observation.window_handle, password_rect):
            try:
                self._prepare_window(password_edit)
            except Exception:
                pass
        try:
            self._message_type_text(observation.window_handle, password)
        except Exception as exc:
            try:
                self._fill_edit(password_edit, password)
            except Exception as fill_exc:
                return ActionResult(
                    ok=False,
                    code="password_fill_failed",
                    message=f"password fill failed: {exc}; fallback: {fill_exc}",
                    details={
                        "password_edit_index": observation.password_edit_index,
                        "ignored_edit_indices": ignored_edit_indices,
                    },
                )

        buttons = self._sorted_descendants(window, "Button")
        submit_button = None
        if observation.submit_button_index is not None and observation.submit_button_index < len(buttons):
            submit_button = buttons[observation.submit_button_index]
        if submit_button is None:
            submit_button = self._first_matching_button(window, LOGIN_BUTTON_KEYWORDS)
        clicked = False
        if submit_button is not None:
            clicked = self._message_click(observation.window_handle, self._safe_rect(submit_button))
            if not clicked:
                clicked = self._click_wrapper(submit_button)
        if not clicked:
            try:
                window.type_keys("{ENTER}", set_foreground=True)
                clicked = True
            except Exception:
                clicked = False
        time.sleep(0.5)
        if clicked:
            return ActionResult(
                ok=True,
                code="submitted",
                message="password submitted",
                details={
                    "password_edit_index": observation.password_edit_index,
                    "ignored_edit_indices": ignored_edit_indices,
                    "remember_enabled": remember_enabled,
                    "auto_login_enabled": auto_login_enabled,
                },
            )
        return ActionResult(
            ok=False,
            code="submit_failed",
            message="submit button not available",
            details={
                "password_edit_index": observation.password_edit_index,
                "ignored_edit_indices": ignored_edit_indices,
                "remember_enabled": remember_enabled,
                "auto_login_enabled": auto_login_enabled,
            },
        )

    def _rect_center(self, rect: tuple[int, int, int, int]) -> tuple[int, int]:
        left, top, right, bottom = rect
        return int((left + right) / 2), int((top + bottom) / 2)

    def _message_click(self, hwnd: int, rect: tuple[int, int, int, int]) -> bool:
        center_x, center_y = self._rect_center(rect)
        point = wintypes.POINT(center_x, center_y)
        try:
            ctypes.windll.user32.ScreenToClient(hwnd, ctypes.byref(point))
            lparam = (int(point.y) << 16) | (int(point.x) & 0xFFFF)
            user32 = ctypes.windll.user32
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
            user32.SendMessageW(hwnd, WM_LBUTTONDOWN, 1, lparam)
            user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
            return True
        except Exception:
            return False

    def _message_type_text(self, hwnd: int, value: str) -> None:
        user32 = ctypes.windll.user32
        for char in str(value or ""):
            user32.SendMessageW(hwnd, WM_CHAR, ord(char), 0)
            time.sleep(0.02)

    def _window_to_descriptor(self, window) -> WindowDescriptor:
        controls: list[ControlDescriptor] = []
        for control_type in ("Edit", "Text", "Button", "CheckBox", "ComboBox", "Pane", "Document", "Custom"):
            for child in self._safe_descendants(window, control_type):
                controls.append(
                    ControlDescriptor(
                        control_type=control_type,
                        name=_safe_str(self._safe_window_text(child)),
                        rect=self._safe_rect(child),
                        visible=self._safe_is_visible(child),
                        enabled=self._safe_is_enabled(child),
                    )
                )
        return WindowDescriptor(
            handle=int(getattr(window, "handle", 0) or 0),
            process_id=self._safe_process_id(window),
            title=_safe_str(self._safe_window_text(window)),
            class_name=self._safe_class_name(window),
            controls=tuple(controls),
            visible=self._safe_is_visible(window),
            enabled=self._safe_is_enabled(window),
        )

    def _safe_descendants(self, window, control_type: str):
        try:
            return window.descendants(control_type=control_type)
        except Exception:
            return []

    def _safe_window_text(self, wrapper) -> str:
        try:
            return wrapper.window_text()
        except Exception:
            return ""

    def _safe_process_id(self, wrapper) -> int | None:
        try:
            return int(wrapper.process_id())
        except Exception:
            return None

    def _safe_class_name(self, wrapper) -> str:
        for getter_name in ("friendly_class_name", "class_name"):
            getter = getattr(wrapper, getter_name, None)
            if callable(getter):
                try:
                    value = getter()
                except Exception:
                    value = ""
                text = _safe_str(value)
                if text:
                    return text
        element_info = getattr(wrapper, "element_info", None)
        return _safe_str(getattr(element_info, "class_name", ""))

    def _safe_rect(self, wrapper) -> tuple[int, int, int, int]:
        try:
            rect = wrapper.rectangle()
            return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
        except Exception:
            return (0, 0, 0, 0)

    def _safe_is_visible(self, wrapper) -> bool:
        try:
            return bool(wrapper.is_visible())
        except Exception:
            return True

    def _safe_is_enabled(self, wrapper) -> bool:
        try:
            return bool(wrapper.is_enabled())
        except Exception:
            return True

    def _window_descriptor_payload(self, descriptor: WindowDescriptor) -> dict[str, Any]:
        return {
            "handle": int(descriptor.handle),
            "process_id": descriptor.process_id,
            "title": descriptor.title,
            "class_name": descriptor.class_name,
            "visible": bool(descriptor.visible),
            "enabled": bool(descriptor.enabled),
        }

    def _host_window_descriptors(self, process_ids: list[int]) -> list[WindowDescriptor]:
        if not process_ids:
            return []
        pid_filter = {int(pid) for pid in process_ids if pid}
        if not pid_filter:
            return []
        user32 = getattr(ctypes, "windll", None)
        if user32 is None or not getattr(user32, "user32", None):
            return []
        user32 = user32.user32
        descriptors: list[WindowDescriptor] = []

        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _callback(hwnd, _lparam):
            window_pid = wintypes.DWORD()
            try:
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            except Exception:
                return True
            pid_value = int(window_pid.value or 0)
            if pid_value not in pid_filter:
                return True
            title = self._win32_window_text(hwnd)
            class_name = self._win32_class_name(hwnd)
            if not title and not class_name:
                return True
            is_visible = bool(user32.IsWindowVisible(hwnd))
            if not is_visible:
                return True
            descriptors.append(
                WindowDescriptor(
                    handle=int(hwnd),
                    process_id=pid_value,
                    title=title,
                    class_name=class_name,
                    controls=(),
                    visible=is_visible,
                    enabled=True,
                )
            )
            return True

        try:
            user32.EnumWindows(enum_proc(_callback), 0)
        except Exception:
            return []
        return descriptors

    def _win32_window_text(self, hwnd: int) -> str:
        user32 = ctypes.windll.user32
        length = int(user32.GetWindowTextLengthW(hwnd) or 0)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        try:
            user32.GetWindowTextW(hwnd, buffer, length + 1)
        except Exception:
            return ""
        return _safe_str(buffer.value)

    def _win32_class_name(self, hwnd: int) -> str:
        user32 = ctypes.windll.user32
        buffer = ctypes.create_unicode_buffer(256)
        try:
            copied = int(user32.GetClassNameW(hwnd, buffer, 256) or 0)
        except Exception:
            return ""
        if copied <= 0:
            return ""
        return _safe_str(buffer.value)

    def _prepare_window(self, window) -> None:
        for method_name in ("restore", "set_focus"):
            method = getattr(window, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    pass

    def _sorted_descendants(self, window, control_type: str):
        candidates = [
            child
            for child in self._safe_descendants(window, control_type)
            if self._safe_is_visible(child) and self._safe_is_enabled(child)
        ]
        return sorted(candidates, key=lambda item: _rect_sort_key(self._safe_rect(item)))

    def _fill_edit(self, edit, value: str) -> None:
        self._prepare_window(edit)
        iface_value = getattr(edit, "iface_value", None)
        if iface_value is not None:
            try:
                iface_value.SetValue("")
            except Exception:
                pass
            try:
                iface_value.SetValue(value)
                return
            except Exception:
                pass
        for method_name in ("set_text", "set_edit_text"):
            method = getattr(edit, method_name, None)
            if callable(method):
                try:
                    method("")
                except Exception:
                    pass
                try:
                    method(value)
                    return
                except Exception:
                    pass
        for focus_method_name in ("set_focus",):
            focus_method = getattr(edit, focus_method_name, None)
            if callable(focus_method):
                try:
                    focus_method()
                except Exception:
                    pass
        try:
            edit.type_keys("^a{BACKSPACE}", set_foreground=True)
        except Exception:
            pass
        try:
            edit.type_keys(value, with_spaces=True, set_foreground=True, vk_packet=True, pause=0.02)
            return
        except TypeError:
            edit.type_keys(value, with_spaces=True, set_foreground=True, pause=0.02)
            return

    def _first_matching_button(self, window, keywords: tuple[str, ...]):
        for button in self._sorted_descendants(window, "Button"):
            if _contains_any(self._safe_window_text(button), keywords):
                return button
        return None

    def _click_wrapper(self, wrapper) -> bool:
        self._prepare_window(wrapper)
        invoke_method = getattr(wrapper, "invoke", None)
        if callable(invoke_method):
            try:
                invoke_method()
                return True
            except Exception:
                pass
        iface_invoke = getattr(wrapper, "iface_invoke", None)
        if iface_invoke is not None:
            try:
                iface_invoke.Invoke()
                return True
            except Exception:
                pass
        legacy_method = getattr(wrapper, "legacy_properties", None)
        if callable(legacy_method):
            try:
                wrapper.click()
                return True
            except Exception:
                pass
        try:
            wrapper.click_input()
            return True
        except Exception:
            pass
        try:
            wrapper.click()
            return True
        except Exception:
            return False

    def _enable_matching_toggle(self, window, keywords: tuple[str, ...]) -> bool:
        candidates = self._sorted_descendants(window, "CheckBox") + self._sorted_descendants(window, "Button")
        for candidate in candidates:
            if not _contains_any(self._safe_window_text(candidate), keywords):
                continue
            checked = self._checked_state(candidate)
            if checked is True:
                return True
            return self._click_wrapper(candidate)
        return False

    def _checked_state(self, wrapper) -> bool | None:
        for method_name in ("get_toggle_state", "get_check_state"):
            method = getattr(wrapper, method_name, None)
            if callable(method):
                try:
                    return bool(method())
                except Exception:
                    pass
        iface_toggle = getattr(wrapper, "iface_toggle", None)
        if iface_toggle is not None:
            try:
                return bool(int(iface_toggle.CurrentToggleState))
            except Exception:
                pass
        return None

