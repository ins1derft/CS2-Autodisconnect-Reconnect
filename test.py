import pyautogui
import sys

TEMPLATE_PATH = "reconnect_button.png"

btn = None
for conf in (0.8, 0.7, 0.6):
    btn = pyautogui.locateOnScreen(
        TEMPLATE_PATH,
        confidence=conf,
        grayscale=True
    )
    if btn:
        print(f"Найдено совпадение с confidence={conf}")
        break

if not btn:
    print("❌ Кнопка Reconnect не найдена. Проверьте шаблон и параметры поиска.")
    sys.exit(1)

x, y = pyautogui.center(btn)
pyautogui.click(x, y)