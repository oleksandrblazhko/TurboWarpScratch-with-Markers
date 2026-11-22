# -*- coding: utf-8 -*-
"""
ArUcoNative: Модуль трекінгу та обчислення швидкості переміщення маркера у площині X-Y.
"""

import math
import numpy as np

class MarkerSpeedTracker:
    def __init__(self, marker_size_cm=3.0, alpha=0.30, deadband_px=1.5, max_dt=0.35, warmup_frames=3, max_missing_frames=2):
        """
        :param marker_size_cm: Фізичний розмір сторони маркера в сантиметрах (None якщо вимкнено).
        :param alpha: Коефіцієнт EMA згладжування швидкості (0.1 - сильне згладжування, 0.9 - слабке).
        :param deadband_px: Поріг мертвої зони (у пікселях) для усунення шуму нерухомої камери.
        :param max_dt: Максимальний допустимий інтервал часу (секунди) між детекціями.
        :param warmup_frames: Кількість початкових кадрів для стабілізації трекера без фіксації max_speed.
        :param max_missing_frames: Допустима кількість пропущених кадрів (інерційний буфер при Motion Blur).
        """
        self.marker_size_cm = marker_size_cm
        self.alpha = alpha
        self.deadband_px = deadband_px
        self.max_dt = max_dt
        self.warmup_frames = warmup_frames
        self.max_missing_frames = max_missing_frames

        self.prev_center = None
        self.prev_time = None
        self.consecutive_frames = 0
        self.missing_frames = 0

        self.filtered_speed_px = 0.0
        self.filtered_speed_cm = 0.0
        self.filtered_vx_px = 0.0
        self.filtered_vy_px = 0.0

        # Максимальна зафіксована швидкість
        self.max_speed_px = 0.0
        self.max_speed_cm = 0.0

    def calculate_scale_cm_per_px(self, corners):
        """
        Обчислює динамічний масштабний коефіцієнт (см/піксель) на основі довжини сторін маркера в кадрі.
        """
        if self.marker_size_cm is None or self.marker_size_cm <= 0:
            return None

        # Розрахунок середньої довжини 4 сторін маркера в пікселях
        side_lengths = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            side_lengths.append(dist)

        avg_side_px = sum(side_lengths) / 4.0
        if avg_side_px < 1.0:
            return None

        return self.marker_size_cm / avg_side_px

    def update(self, corners, current_time):
        """
        Оновлює положення маркера та обчислює швидкості.
        :param corners: np.ndarray розмірності (4, 2) з піксельними координатами кутів.
        :param current_time: Часова мітка поточного кадру (time.time()).
        :return: dict з метриками швидкості та положення.
        """
        cx = float(np.mean(corners[:, 0]))
        cy = float(np.mean(corners[:, 1]))

        scale_cm_per_px = self.calculate_scale_cm_per_px(corners)
        self.missing_frames = 0

        # Перше виявлення або розрив після паузи
        if self.prev_center is None or self.prev_time is None:
            self.prev_center = (cx, cy)
            self.prev_time = current_time
            self.consecutive_frames = 1
            self.filtered_speed_px = 0.0
            self.filtered_speed_cm = 0.0
            self.filtered_vx_px = 0.0
            self.filtered_vy_px = 0.0
            return self._build_result(cx, cy, scale_cm_per_px, is_detected=True)

        dt = current_time - self.prev_time
        if dt > self.max_dt or dt <= 0:
            # Розрив за часом (маркер на мить зникав або завис потік)
            self.prev_center = (cx, cy)
            self.prev_time = current_time
            self.consecutive_frames = 1
            self.filtered_speed_px = 0.0
            self.filtered_speed_cm = 0.0
            self.filtered_vx_px = 0.0
            self.filtered_vy_px = 0.0
            return self._build_result(cx, cy, scale_cm_per_px, is_detected=True)

        # Захист від занадто малих dt (буферизація драйвера камери < 10 мс)
        if dt < 0.010:
            return self._build_result(cx, cy, scale_cm_per_px, is_detected=True)

        self.consecutive_frames += 1

        # Період прогріву (перші N кадрів після появи маркера не фіксують швидкість)
        if self.consecutive_frames <= self.warmup_frames:
            self.prev_center = (cx, cy)
            self.prev_time = current_time
            self.filtered_speed_px = 0.0
            self.filtered_speed_cm = 0.0
            self.filtered_vx_px = 0.0
            self.filtered_vy_px = 0.0
            return self._build_result(cx, cy, scale_cm_per_px, is_detected=True)

        # Розрахунок переміщення
        dx = cx - self.prev_center[0]
        dy = cy - self.prev_center[1]
        dist = math.hypot(dx, dy)

        # Мертва зона для усунення субпіксельного шуму
        if dist < self.deadband_px:
            dx = 0.0
            dy = 0.0
            dist = 0.0

        # Миттєва швидкість
        raw_vx = dx / dt
        raw_vy = dy / dt
        raw_speed = dist / dt

        # Захист від нереалістичних викидів (наприклад, хибне розпізнавання кутів > 2500 px/s)
        if raw_speed > 2500.0:
            raw_speed = self.filtered_speed_px
            raw_vx = self.filtered_vx_px
            raw_vy = self.filtered_vy_px

        # EMA-згладжування
        self.filtered_vx_px = self.alpha * raw_vx + (1.0 - self.alpha) * self.filtered_vx_px
        self.filtered_vy_px = self.alpha * raw_vy + (1.0 - self.alpha) * self.filtered_vy_px
        self.filtered_speed_px = self.alpha * raw_speed + (1.0 - self.alpha) * self.filtered_speed_px

        # Метрична швидкість у см/с
        if scale_cm_per_px is not None:
            self.filtered_speed_cm = self.filtered_speed_px * scale_cm_per_px
        else:
            self.filtered_speed_cm = None

        # Оновлення пікової швидкості (Speed-max) ТІЛЬКИ після повного прогріву
        if self.filtered_speed_cm is not None:
            if self.filtered_speed_cm > self.max_speed_cm:
                self.max_speed_cm = self.filtered_speed_cm
                self.max_speed_px = self.filtered_speed_px
        else:
            if self.filtered_speed_px > self.max_speed_px:
                self.max_speed_px = self.filtered_speed_px

        self.prev_center = (cx, cy)
        self.prev_time = current_time

        return self._build_result(cx, cy, scale_cm_per_px, is_detected=True)

    def _build_result(self, cx, cy, scale_cm_per_px, is_detected=True):
        return {
            "speed_px": round(self.filtered_speed_px, 1),
            "speed_cm": round(self.filtered_speed_cm, 1) if self.filtered_speed_cm is not None else None,
            "max_speed_px": round(self.max_speed_px, 1),
            "max_speed_cm": round(self.max_speed_cm, 1) if self.max_speed_cm is not None else None,
            "vx_px": round(self.filtered_vx_px, 1),
            "vy_px": round(self.filtered_vy_px, 1),
            "center_x": round(cx, 1) if cx is not None else 0.0,
            "center_y": round(cy, 1) if cy is not None else 0.0,
            "scale_cm_per_px": scale_cm_per_px,
            "is_detected": is_detected
        }

    def on_frame_missing(self, current_time):
        """
        Обробка пропуску детекції кадру (короткочасне змазування Motion Blur або перекриття).
        Якщо пропущено не більше max_missing_frames кадрів (до ~66 мс), вмикається інерційне
        утримання швидкості (coasting) з плавним згасанням, що запобігає ривкам та розривам трекінгу.
        """
        self.missing_frames += 1
        if self.missing_frames <= self.max_missing_frames and self.consecutive_frames > self.warmup_frames and self.prev_center is not None:
            # Інерційне утримання (coasting) зі згасанням на 20% за кожен пропущений кадр
            self.filtered_speed_px *= 0.80
            self.filtered_vx_px *= 0.80
            self.filtered_vy_px *= 0.80
            if self.filtered_speed_cm is not None:
                self.filtered_speed_cm *= 0.80

            return self._build_result(
                self.prev_center[0],
                self.prev_center[1],
                None,
                is_detected=False
            )
        else:
            # Повна втрата контролю (> max_missing_frames)
            self.reset()
            return self.get_current_data()

    def get_current_data(self):
        """
        Повертає поточний стан трекера (коли маркер не виявлено).
        """
        return self._build_result(
            self.prev_center[0] if self.prev_center else 0.0,
            self.prev_center[1] if self.prev_center else 0.0,
            None,
            is_detected=False
        )

    def reset(self):
        """
        Скидає поточний трекінг (при втраті маркера), але ЗБЕРІГАЄ зафіксований max_speed.
        """
        self.prev_center = None
        self.prev_time = None
        self.consecutive_frames = 0
        self.missing_frames = 0
        self.filtered_speed_px = 0.0
        self.filtered_speed_cm = 0.0
        self.filtered_vx_px = 0.0
        self.filtered_vy_px = 0.0

    def reset_max(self):
        """
        Повне скидання зафіксованої максимальної швидкості.
        """
        self.max_speed_px = 0.0
        self.max_speed_cm = 0.0
