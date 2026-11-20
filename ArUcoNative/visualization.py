# -*- coding: utf-8 -*-
"""
ArUcoNative: Модуль візуалізації маркерів та HUD в OpenCV.
"""

import cv2
import numpy as np

def draw_marker_info(frame, corners, marker_id, angle):
    """
    Малює зелений контур маркера, стрілку орієнтації, центральну точку та інформаційний бейдж із кутом.
    """
    pts = np.int32(corners).reshape((-1, 1, 2))

    # 1. Зелений контур маркера
    cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 102), thickness=2, lineType=cv2.LINE_AA)

    # 2. Виділена синьо-блакитна верхня грань (0 -> 1)
    c0 = (int(corners[0][0]), int(corners[0][1]))
    c1 = (int(corners[1][0]), int(corners[1][1]))
    cv2.line(frame, c0, c1, color=(248, 189, 56), thickness=3, lineType=cv2.LINE_AA)

    # 3. Стрілка напрямку від центру до верхньої грані
    center_x = int(np.mean(corners[:, 0]))
    center_y = int(np.mean(corners[:, 1]))
    mid_top_x = int((c0[0] + c1[0]) / 2)
    mid_top_y = int((c0[1] + c1[1]) / 2)

    cv2.circle(frame, (center_x, center_y), 4, (255, 255, 255), -1, lineType=cv2.LINE_AA)
    cv2.arrowedLine(frame, (center_x, center_y), (mid_top_x, mid_top_y), (248, 189, 56), 2, tipLength=0.25)

    # 4. Плашка (бейдж) з номером маркера та кутом нахилу
    min_x = int(np.min(corners[:, 0]))
    min_y = int(np.min(corners[:, 1]))

    angle_str = f"{angle:+.1f}°" if angle is not None else "0.0°"
    text = f"ArUco #{marker_id} | {angle_str}"

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.55
    thickness = 2

    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)

    badge_x = max(10, min_x)
    badge_y = max(text_h + 15, min_y - 12)

    pad_x, pad_y = 6, 4
    rect_tl = (badge_x - pad_x, badge_y - text_h - pad_y)
    rect_br = (badge_x + text_w + pad_x, badge_y + pad_y + baseline)

    # Напівпрозорий чорний фон бейджа
    sub_img = frame[max(0, rect_tl[1]):min(frame.shape[0], rect_br[1]), max(0, rect_tl[0]):min(frame.shape[1], rect_br[0])]
    if sub_img.shape[0] > 0 and sub_img.shape[1] > 0:
        black_rect = np.zeros(sub_img.shape, dtype=np.uint8)
        res = cv2.addWeighted(sub_img, 0.25, black_rect, 0.75, 1.0)
        frame[max(0, rect_tl[1]):min(frame.shape[0], rect_br[1]), max(0, rect_tl[0]):min(frame.shape[1], rect_br[0])] = res

    # Зелена рамка навколо тексту
    cv2.rectangle(frame, rect_tl, rect_br, (0, 255, 102), 1, cv2.LINE_AA)
    # Яскраво-зелений текст
    cv2.putText(frame, text, (badge_x, badge_y), font, font_scale, (0, 255, 102), thickness, cv2.LINE_AA)

def draw_hud(frame, camera_id, fps, clients_count, primary_angle=None, primary_id=None):
    """
    Малює інформаційну панель зверху відеокадру.
    """
    h, w = frame.shape[:2]

    # Верхня темна смужка HUD
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 38), (15, 15, 18), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    font = cv2.FONT_HERSHEY_SIMPLEX

    # Статус камери та FPS
    cam_text = f"Cam: #{camera_id}  |  FPS: {fps:4.1f}  |  Scratch WS: {clients_count} clients"
    cv2.putText(frame, cam_text, (12, 24), font, 0.5, (220, 220, 225), 1, cv2.LINE_AA)

    # Стан розпізнавання маркера
    if primary_id is not None and primary_angle is not None:
        status_text = f"Detected: #{primary_id} ({primary_angle:+.1f} deg)"
        color = (0, 255, 102)
    else:
        status_text = "No marker detected"
        color = (150, 150, 160)

    (sw, sh), _ = cv2.getTextSize(status_text, font, 0.5, 1)
    cv2.putText(frame, status_text, (w - sw - 14, 24), font, 0.5, color, 1, cv2.LINE_AA)
