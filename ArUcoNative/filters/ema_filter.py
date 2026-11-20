# -*- coding: utf-8 -*-
"""
ArUcoNative: Фільтр експоненційного згладжування (EMA) для кута нахилу з коректною обробкою переходу через +-180 градусів.
"""

import math

class AngleEmaFilter:
    def __init__(self, alpha=0.35):
        """
        :param alpha: коефіцієнт згладжування (0.1 - сильне згладжування, 0.9 - майже без згладжування).
        """
        self.alpha = alpha
        self.filtered_angle = None

    def update(self, new_angle):
        if self.filtered_angle is None:
            self.filtered_angle = new_angle
            return new_angle

        # Обчислення мінімальної кутової різниці з урахуванням кола 360 градусів
        diff = (new_angle - self.filtered_angle + 180.0) % 360.0 - 180.0
        self.filtered_angle += self.alpha * diff

        # Нормалізація в діапазон [-180, +180]
        if self.filtered_angle > 180.0:
            self.filtered_angle -= 360.0
        elif self.filtered_angle < -180.0:
            self.filtered_angle += 360.0

        return round(self.filtered_angle, 1)

    def reset(self):
        self.filtered_angle = None
