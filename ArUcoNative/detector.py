# -*- coding: utf-8 -*-
"""
ArUcoNative: Модуль детектора ArUco-маркерів.
"""

import cv2

# Мапінг текстових назв словників до констант OpenCV
ARUCO_DICTIONARIES = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
    "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
    "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
    "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
    "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
    "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
    "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
}

class NativeArucoDetector:
    def __init__(self, dict_name="DICT_4X4_1000"):
        # Нормалізація імені словника (наприклад, 4X4_1000 -> DICT_4X4_1000)
        clean_name = dict_name.upper()
        if not clean_name.startswith("DICT_"):
            clean_name = "DICT_" + clean_name

        dict_const = ARUCO_DICTIONARIES.get(clean_name, cv2.aruco.DICT_4X4_1000)
        self.dictionary = cv2.aruco.getPredefinedDictionary(dict_const)
        self.dict_name = clean_name

        # Налаштування параметрів детектора для стабільності та стійкості до Motion Blur
        self.parameters = cv2.aruco.DetectorParameters()
        self.parameters.polygonalApproxAccuracyRate = 0.05
        self.parameters.minMarkerPerimeterRate = 0.04
        self.parameters.errorCorrectionRate = 0.8

        # Оптимізація під змазування (Motion Blur)
        self.parameters.perspectiveRemoveIgnoredMarginPerCell = 0.20  # Зчитування суворо з центру бітів
        self.parameters.adaptiveThreshWinSizeMin = 3
        self.parameters.adaptiveThreshWinSizeMax = 27
        self.parameters.adaptiveThreshWinSizeStep = 4                # Дрібніший крок адаптивного порогу
        self.parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX  # Субпіксельне уточнення кутів

        # Перевірка наявності нового класу ArucoDetector (OpenCV 4.7+)
        if hasattr(cv2.aruco, "ArucoDetector"):
            self.detector = cv2.aruco.ArucoDetector(self.dictionary, self.parameters)
            self._use_new_api = True
        else:
            self.detector = None
            self._use_new_api = False

        print(f"[Detector] Словник ArUco: {self.dict_name} | API: {'cv2.aruco.ArucoDetector' if self._use_new_api else 'legacy detectMarkers'}")

    def detect(self, frame):
        """
        Виявляє ArUco маркери у кадрі.
        Повертає corners (список масивів 4х2) та ids (список ідентифікаторів).
        """
        if len(frame.shape) == 3 and frame.shape[2] >= 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        if self._use_new_api:
            corners, ids, rejected = self.detector.detectMarkers(gray)
        else:
            corners, ids, rejected = cv2.aruco.detectMarkers(gray, self.dictionary, parameters=self.parameters)

        return corners, ids
