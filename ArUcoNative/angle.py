# -*- coding: utf-8 -*-
"""
ArUcoNative: Модуль обчислення кута нахилу маркера відносно горизонту.
"""

import math

def calculate_tilt_angle(corners):
    """
    Обчислює оптичний кут нахилу маркера до горизонту в діапазоні [-180.0, +180.0] градусів.
    
    В OpenCV кути ArUco розташовані за годинниковою стрілкою:
      corners[0] - верхній лівий кут (top-left)
      corners[1] - верхній правий кут (top-right)
      corners[2] - нижній правий кут (bottom-right)
      corners[3] - нижній лівий кут (bottom-left)
      
    Кут обчислюється за вектором верхньої грані (0 -> 1):
      dx = c1.x - c0.x
      dy = c1.y - c0.y
      кут = atan2(dy, dx)
    """
    c0 = corners[0]
    c1 = corners[1]

    dx = float(c1[0] - c0[0])
    dy = float(c1[1] - c0[1])

    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)

    # Нормалізація в діапазон [-180.0, +180.0]
    if angle_deg > 180.0:
        angle_deg -= 360.0
    elif angle_deg < -180.0:
        angle_deg += 360.0

    return round(angle_deg, 1)
