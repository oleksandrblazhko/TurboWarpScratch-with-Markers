# -*- coding: utf-8 -*-
"""
ArUcoNative: Модуль ініціалізації та захоплення вебкамери.
"""

import cv2
import platform

def create_camera(cam_id=0, width=640, height=480, fps=30):
    """
    Ініціалізує вебкамеру за індексом.
    На Windows використовує бекенд cv2.CAP_DSHOW для уникнення затримок та зависань.
    """
    is_windows = platform.system() == "Windows"
    backend = cv2.CAP_DSHOW if is_windows else cv2.CAP_ANY

    cap = cv2.VideoCapture(cam_id, backend)

    if not cap.isOpened() and is_windows:
        # Резервна спроба з CAP_ANY, якщо CAP_DSHOW не спрацював
        cap = cv2.VideoCapture(cam_id, cv2.CAP_ANY)

    if not cap.isOpened():
        raise RuntimeError(f"Не вдалося відкрити вебкамеру #{cam_id}. Перевірте підключення або спробуйте інший номер камери.")

    # Встановлення бажаної роздільної здатності та частоти кадрів
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    # Зчитуємо фактичні параметри камери
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"[Camera] Камера #{cam_id} успішно відкрита: {actual_w}x{actual_h} @ {actual_fps:.1f} FPS")
    return cap
