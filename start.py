import os
import time
import re
import threading
from typing import Iterator

import pyautogui
import keyboard
import argparse

DEFAULT_LOG_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\console.log"
DEFAULT_PLAYER_NAME = "awall propeller"

RECONNECT_TEMPLATE = "reconnect_button.png"
ACCEPT_TEMPLATE    = "accept_button.png"

CONFIDENCE            = 0.8   # порог для обоих шаблонов
PRE_DISCONNECT_DELAY  = 2.5   # пауза перед авто-J
AFTER_DISCONNECT_DELAY = 2.5  # пауза после J перед поиском Reconnect
BUTTON_TIMEOUT        = 10.0  # макс. ждать Reconnect
ACCEPT_CHECK_INTERVAL = 0.5   # интервал проверки кнопки Accept
# -----------------------------------------

auto_accept_enabled = True  # флаг авто-accept
auto_accept_lock = threading.Lock()
exit_event = threading.Event()
last_auto_j = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto disconnect/reconnect helper for CS2"
    )
    parser.add_argument(
        "--log-path",
        default=os.environ.get("LOG_PATH", DEFAULT_LOG_PATH),
        help="Path to CS2 console.log",
    )
    parser.add_argument(
        "--player-name",
        default=os.environ.get("PLAYER_NAME", DEFAULT_PLAYER_NAME),
        help="Exact player name used in logs",
    )
    return parser.parse_args()


def tail_log(path: str) -> Iterator[str]:
    """Yield new lines from log file, waiting if file is missing."""
    while not exit_event.is_set():
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                while not exit_event.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    yield line
        except FileNotFoundError:
            print(f"[warn] Log file not found: {path}. Waiting...")
            time.sleep(1.0)


def accept_monitor():
    """
    Фоновый мониторинг кнопки Accept.
    Каждые ACCEPT_CHECK_INTERVAL секунд проверяет экран.
    Если кнопка найдена и авто-accept включён, кликает по ней.
    """
    while not exit_event.is_set():
        with auto_accept_lock:
            enabled = auto_accept_enabled

        if enabled:
            try:
                btn = pyautogui.locateOnScreen(
                    ACCEPT_TEMPLATE,
                    confidence=CONFIDENCE,
                    grayscale=True,
                )
            except pyautogui.ImageNotFoundException:
                btn = None
            except Exception as exc:
                print(f"[error] locateOnScreen: {exc}")
                btn = None

            if btn:
                print("🔔 Accept button detected, clicking in 1s...")
                time.sleep(1.0)
                x, y = pyautogui.center(btn)
                pyautogui.click(x, y)
                print("[match accepted]")
        time.sleep(ACCEPT_CHECK_INTERVAL)


def cycle_reconnect(tailer, pattern):
    """
    Авто-цикл для одного матча:
      1) press('j') → disconnect
      2) ждать Reconnect (до BUTTON_TIMEOUT) → клик
      3) ждать в логе второе подряд сообщение connected
    """
    while not exit_event.is_set():
        print(f"…waiting {PRE_DISCONNECT_DELAY:.1f}s before auto-disconnect…")
        time.sleep(PRE_DISCONNECT_DELAY)

        print("→ auto-press J (disconnect)")
        pyautogui.press('j')
        global last_auto_j
        last_auto_j = time.time()
        time.sleep(AFTER_DISCONNECT_DELAY)

        print(
            f"…waiting up to {BUTTON_TIMEOUT:.0f}s for Reconnect button…",
            end="",
            flush=True,
        )
        start = time.time()
        btn = None
        while time.time() - start < BUTTON_TIMEOUT and not exit_event.is_set():
            try:
                btn = pyautogui.locateOnScreen(
                    RECONNECT_TEMPLATE,
                    confidence=CONFIDENCE,
                    grayscale=True,
                )
            except pyautogui.ImageNotFoundException:
                btn = None
            except Exception as exc:
                print(f"[error] locateOnScreen reconnect: {exc}")
                btn = None
            if btn:
                print(" found!")
                break
            time.sleep(0.2)
        else:
            print(f"\n✅ No Reconnect button in {BUTTON_TIMEOUT}s — ending cycle.")
            return

        x, y = pyautogui.center(btn)
        print(f"→ click reconnect at ({x},{y})")
        pyautogui.click(x, y)

        print("…waiting for reconnect confirmation in log…")
        for line in tailer:
            if pattern.search(line):
                print("[got reconnect]", line.strip())
                break


def toggle_accept() -> None:
    global auto_accept_enabled
    with auto_accept_lock:
        auto_accept_enabled = not auto_accept_enabled
        status = "ENABLED" if auto_accept_enabled else "DISABLED"
    print(f"🔁 Auto-accept {status}")


def wait_for_manual_j() -> None:
    """Block until user presses 'j' ignoring our automated presses."""
    while True:
        event = keyboard.read_event()
        if event.name == "j" and event.event_type == keyboard.KEY_DOWN:
            if time.time() - last_auto_j > 0.5:
                break


def main() -> None:
    args = parse_args()

    global LOG_PATH, PLAYER_NAME
    LOG_PATH = args.log_path
    PLAYER_NAME = args.player_name

    threading.Thread(target=accept_monitor, daemon=True).start()

    keyboard.add_hotkey("f2", toggle_accept)
    print("Press F2 to toggle auto-accept on/off.")

    pattern = re.compile(rf"\b{re.escape(PLAYER_NAME)} connected\b", re.IGNORECASE)

    print("=== CS2 Auto-Disconnect / Reconnect / Accept ===")
    try:
        while not exit_event.is_set():
            tailer = tail_log(LOG_PATH)

            print("\nWaiting for match start (first 'connected')…")
            for line in tailer:
                if pattern.search(line):
                    print("[match start ]", line.strip())
                    break

            print("Press J once (after 1st round starts) to begin auto-cycle.")
            wait_for_manual_j()
            print("[manual J   ] starting auto-reconnect loop…")

            cycle_reconnect(tailer, pattern)

            print("\n=== Match cycle ended; ready for next match… ===")

    except KeyboardInterrupt:
        print("\nInterrupted by user; exiting.")
    finally:
        exit_event.set()


if __name__ == "__main__":
    main()