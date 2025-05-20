import os
import time
import re
import threading

import pyautogui
import keyboard

LOG_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\console.log"
PLAYER_NAME = "awall propeller"

RECONNECT_TEMPLATE = "reconnect_button.png"
ACCEPT_TEMPLATE    = "accept_button.png"

CONFIDENCE            = 0.8   # порог для обоих шаблонов
PRE_DISCONNECT_DELAY  = 2.5   # пауза перед авто-J
AFTER_DISCONNECT_DELAY = 2.5  # пауза после J перед поиском Reconnect
BUTTON_TIMEOUT        = 10.0  # макс. ждать Reconnect
ACCEPT_CHECK_INTERVAL = 0.5   # интервал проверки кнопки Accept
# -----------------------------------------

auto_accept_enabled = True  # флаг авто-accept
exit_event = threading.Event()


def tail_log(path):
    """Генератор строк, типа tail -F."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while not exit_event.is_set():
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line


def accept_monitor():
    """
    Фоновый мониторинг кнопки Accept.
    Каждые ACCEPT_CHECK_INTERVAL секунд проверяет экран.
    Если кнопка найдена и авто-accept включён, кликает по ней.
    """
    while not exit_event.is_set():
        if auto_accept_enabled:
            try:
                btn = pyautogui.locateOnScreen(
                    ACCEPT_TEMPLATE,
                    confidence=CONFIDENCE,
                    grayscale=True
                )
            except pyautogui.ImageNotFoundException:
                btn = None

            if btn:
                print("🔔 Accept button detected, clicking in 1s...")
                time.sleep(2.0)
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
        time.sleep(AFTER_DISCONNECT_DELAY)

        print(f"…waiting up to {BUTTON_TIMEOUT:.0f}s for Reconnect button…", end="", flush=True)
        start = time.time()
        btn = None
        while time.time() - start < BUTTON_TIMEOUT and not exit_event.is_set():
            try:
                btn = pyautogui.locateOnScreen(
                    RECONNECT_TEMPLATE,
                    confidence=CONFIDENCE,
                    grayscale=True
                )
            except pyautogui.ImageNotFoundException:
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

        print("…waiting for actual reconnect in log (skip duplicate)…")
        skip_once = True
        for line in tailer:
            if pattern.search(line):
                if skip_once:
                    print("[skip dup ]", line.strip())
                    skip_once = False
                    continue
                print("[got reconnect]", line.strip())
                break


def toggle_accept():
    global auto_accept_enabled
    auto_accept_enabled = not auto_accept_enabled
    status = 'ENABLED' if auto_accept_enabled else 'DISABLED'
    print(f"🔁 Auto-accept {status}")


def main():
    threading.Thread(target=accept_monitor, daemon=True).start()

    keyboard.add_hotkey('f2', toggle_accept)
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
            keyboard.wait('j')
            print("[manual J   ] starting auto-reconnect loop…")

            cycle_reconnect(tailer, pattern)

            print("\n=== Match cycle ended; ready for next match… ===")

    except KeyboardInterrupt:
        print("\nInterrupted by user; exiting.")
    finally:
        exit_event.set()


if __name__ == "__main__":
    main()