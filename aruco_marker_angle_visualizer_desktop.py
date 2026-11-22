#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArUco Marker Native Server (Pure Python OpenCV + WebSocket)
===========================================================

Цей модуль:
1. Захоплює відео з вебкамери напряму через OpenCV (без участі браузера).
2. Детектує ArUco-маркери за допомогою нативної бібліотеки cv2.aruco.
3. Обчислює кут нахилу маркера до горизонту [-180.0, +180.0] градусів.
4. Відображає високопродуктивне нативне вікно з рамкою, осями та кутом.
5. Транслює дані у Scratch (4-Cat-Run-SmartPhone.sb3) через WebSocket на порту 8767
   із фіксованою частотою 20 Гц (кожні 50 мс) у форматі:
   {"accX": 0, "accY": 0, "angle_x": <кут>, "angle_y": 0, "marker_id": <id>}
"""

import sys
import time
import json
import asyncio
import threading
import argparse
import cv2

try:
    import websockets
except ImportError:
    print("Помилка: бібліотека 'websockets' не встановлена. Встановіть її командою: pip install websockets")
    sys.exit(1)

from ArUcoNative.camera import create_camera
from ArUcoNative.detector import NativeArucoDetector
from ArUcoNative.angle import calculate_tilt_angle
from ArUcoNative.filters.ema_filter import AngleEmaFilter
from ArUcoNative.speed import MarkerSpeedTracker
from ArUcoNative.visualization import draw_marker_info, draw_hud, draw_bottom_hud

# Глобальний стан для трансляції
STATE_LOCK = threading.Lock()
CONNECTED_CLIENTS = set()

SENSOR_DATA = {
    "accX": 0.0,
    "accY": 0.0,
    "angle_x": 0.0,
    "angle_y": 0.0,
    "marker_id": None,
    "speed_px": 0.0,
    "speed_cm": 0.0,
    "max_speed_px": 0.0,
    "max_speed_cm": 0.0,
    "vel_x": 0.0,
    "vel_y": 0.0,
    "pos_x": 0.0,
    "pos_y": 0.0
}

IS_RUNNING = True

async def broadcast_loop():
    """Безперервна трансляція стану сенсора з частотою 20 Гц (50 мс) для Scratch."""
    while IS_RUNNING:
        try:
            with STATE_LOCK:
                if CONNECTED_CLIENTS:
                    payload = json.dumps({
                        "accX": SENSOR_DATA["accX"],
                        "accY": SENSOR_DATA["accY"],
                        "angle_x": SENSOR_DATA["angle_x"],
                        "angle_y": SENSOR_DATA["angle_y"],
                        "marker_id": SENSOR_DATA["marker_id"],
                        "speed_px": SENSOR_DATA["speed_px"],
                        "speed_cm": SENSOR_DATA["speed_cm"],
                        "max_speed_px": SENSOR_DATA["max_speed_px"],
                        "max_speed_cm": SENSOR_DATA["max_speed_cm"],
                        "vel_x": SENSOR_DATA["vel_x"],
                        "vel_y": SENSOR_DATA["vel_y"],
                        "pos_x": SENSOR_DATA["pos_x"],
                        "pos_y": SENSOR_DATA["pos_y"]
                    })
                    clients = list(CONNECTED_CLIENTS)
                else:
                    clients = []

            if clients:
                await asyncio.gather(
                    *[client.send(payload) for client in clients],
                    return_exceptions=True
                )
        except Exception:
            pass

        await asyncio.sleep(0.05)  # 20 Гц

async def ws_handler(websocket):
    """Обробник підключення нових клієнтів (Scratch тощо)."""
    with STATE_LOCK:
        CONNECTED_CLIENTS.add(websocket)
        total = len(CONNECTED_CLIENTS)
        init_payload = json.dumps(SENSOR_DATA)

    print(f"\n[WS] Новий клієнт підключився до порту 8767. Всього клієнтів: {total}")

    # Відразу надсилаємо поточний стан
    try:
        await websocket.send(init_payload)
    except Exception:
        pass

    try:
        # Очікуємо закриття клієнтом з'єднання
        await websocket.wait_closed()
    finally:
        with STATE_LOCK:
            CONNECTED_CLIENTS.discard(websocket)
            total = len(CONNECTED_CLIENTS)
        print(f"\n[WS] Клієнт від'єднався. Залишилось клієнтів: {total}")

def start_websocket_thread(ws_port):
    """Запускає WebSocket-сервер в окремому фоновому потоці."""
    async def run_server():
        try:
            async with websockets.serve(ws_handler, "0.0.0.0", ws_port):
                print(f"[WS] WebSocket-сервер успішно запущено на ws://localhost:{ws_port}")
                broadcast_task = asyncio.create_task(broadcast_loop())
                while IS_RUNNING:
                    await asyncio.sleep(0.2)
        except Exception as e:
            print(f"\n[WS Error] Помилка WebSocket сервера на порту {ws_port}: {e}")

    def thread_target():
        asyncio.run(run_server())

    ws_thread = threading.Thread(target=thread_target, daemon=True)
    ws_thread.start()
    return ws_thread

def main():
    global IS_RUNNING, SENSOR_DATA

    parser = argparse.ArgumentParser(
        description="ArUco Native Tracker & WebSocket Relay for Scratch (Pure Python OpenCV)"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Номер вебкамери (0 - зовнішня/Logi C310, 1 - вбудована). За замовчуванням: 0"
    )
    parser.add_argument(
        "--dict",
        type=str,
        default="DICT_4X4_1000",
        help="Словник ArUco (DICT_4X4_1000, DICT_4X4_50, DICT_6X6_250 тощо). За замовчуванням: DICT_4X4_1000"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8767,
        help="WebSocket-порт для Scratch. За замовчуванням: 8767"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=640,
        help="Ширина кадру камери. За замовчуванням: 640"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=480,
        help="Висота кадру камери. За замовчуванням: 480"
    )
    parser.add_argument(
        "--marker-size",
        type=float,
        default=3.0,
        help="Фізичний розмір сторони маркера в см для обчислення швидкості в см/с. За замовчуванням: 3.0"
    )
    parser.add_argument(
        "--fast-shutter",
        action="store_true",
        help="Увімкнути режим короткої витримки камери для зменшення Motion Blur (якщо підтримується драйвером)"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Вимкнути фільтр згладжування кута (EMA)"
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Вимкнути графічне вікно OpenCV (робота виключно у фоні)"
    )

    args = parser.parse_args()

    print("=" * 74)
    print("      ArUco Native Tracker (Pure Python OpenCV -> Scratch)")
    print("=" * 74)
    print(f"Активна камера:     #{args.camera} (змініть через --camera={args.camera})")
    print(f"Словник ArUco:      {args.dict}")
    print(f"WebSocket порт:     ws://localhost:{args.port} (для Scratch)")
    print(f"Роздільна здатність:{args.width}x{args.height}")
    print(f"Розмір маркера:     {args.marker_size} см (для см/с)")
    print(f"Згладжування (EMA): {'Вимкнено' if args.no_filter else 'Увімкнено (alpha=0.35)'}")
    print("-" * 74)

    # 1. Запуск WebSocket-сервера для Scratch
    start_websocket_thread(args.port)

    # 2. Ініціалізація детектора ArUco та трекера швидкості
    detector = NativeArucoDetector(args.dict)
    angle_filter = None if args.no_filter else AngleEmaFilter(alpha=0.35)
    speed_tracker = MarkerSpeedTracker(marker_size_cm=args.marker_size)

    # 3. Ініціалізація камери
    try:
        cap = create_camera(args.camera, args.width, args.height)
        if args.fast_shutter:
            try:
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                cap.set(cv2.CAP_PROP_EXPOSURE, -6)
                print("[Camera] Режим короткої витримки (--fast-shutter) активовано.")
            except Exception:
                pass
    except RuntimeError as e:
        print(f"\nПомилка: {e}")
        return

    window_name = "ArUco Native Tracker (for Scratch) [Press 'q' or 'Esc' to exit]"
    if not args.no_preview:
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    prev_time = time.time()
    fps = 30.0

    print("\n[OK] Трекер успішно запущено. Покажіть ArUco маркер камері.")
    print("     Для виходу натисніть клавішу 'q' або 'Esc' у вікні перегляду.\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            current_time = time.time()
            dt = current_time - prev_time
            prev_time = current_time
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            # Детекція маркерів
            corners_list, ids = detector.detect(frame)

            detected_marker_id = None
            detected_angle = None
            speed_data = None

            if ids is not None and len(ids) > 0:
                flat_ids = ids.flatten()
                for i in range(len(flat_ids)):
                    m_id = int(flat_ids[i])
                    m_corners = corners_list[i].reshape(-1, 2)

                    raw_angle = calculate_tilt_angle(m_corners)
                    smooth_angle = angle_filter.update(raw_angle) if angle_filter else raw_angle

                    if i == 0:
                        detected_marker_id = m_id
                        detected_angle = smooth_angle
                        speed_data = speed_tracker.update(m_corners, current_time)

                    if not args.no_preview:
                        draw_marker_info(frame, m_corners, m_id, smooth_angle)
            else:
                speed_data = speed_tracker.on_frame_missing(current_time)
                # Якщо маркер відсутній довше пільгового буфера coasting - скидаємо згладжування кута
                if speed_tracker.missing_frames > speed_tracker.max_missing_frames:
                    if angle_filter:
                        angle_filter.reset()

            # Оновлення стану для трансляції у Scratch
            with STATE_LOCK:
                if detected_angle is not None and speed_data is not None and speed_data.get("is_detected"):
                    SENSOR_DATA["angle_x"] = detected_angle
                    SENSOR_DATA["marker_id"] = detected_marker_id
                    SENSOR_DATA["speed_px"] = speed_data["speed_px"]
                    SENSOR_DATA["speed_cm"] = speed_data["speed_cm"] if speed_data["speed_cm"] is not None else 0.0
                    SENSOR_DATA["max_speed_px"] = speed_data["max_speed_px"]
                    SENSOR_DATA["max_speed_cm"] = speed_data["max_speed_cm"] if speed_data["max_speed_cm"] is not None else 0.0
                    SENSOR_DATA["vel_x"] = speed_data["vx_px"]
                    SENSOR_DATA["vel_y"] = speed_data["vy_px"]
                    SENSOR_DATA["pos_x"] = speed_data["center_x"]
                    SENSOR_DATA["pos_y"] = speed_data["center_y"]
                else:
                    SENSOR_DATA["marker_id"] = None
                    SENSOR_DATA["speed_px"] = 0.0
                    SENSOR_DATA["speed_cm"] = 0.0
                    SENSOR_DATA["max_speed_px"] = speed_data["max_speed_px"] if speed_data else 0.0
                    SENSOR_DATA["max_speed_cm"] = speed_data["max_speed_cm"] if speed_data and speed_data["max_speed_cm"] is not None else 0.0
                    SENSOR_DATA["vel_x"] = 0.0
                    SENSOR_DATA["vel_y"] = 0.0
                    SENSOR_DATA["pos_x"] = 0.0
                    SENSOR_DATA["pos_y"] = 0.0

                clients_cnt = len(CONNECTED_CLIENTS)

            # Консольний динамічний рядок
            marker_str = f"#{detected_marker_id}" if detected_marker_id is not None else "N/A"
            angle_str = f"{SENSOR_DATA['angle_x']:+6.1f}°" if detected_marker_id is not None else "  ---  "
            speed_str = (
                f"{SENSOR_DATA['speed_cm']:4.1f} cm/s"
                if detected_marker_id is not None else "   ---   "
            )
            max_str = f"{SENSOR_DATA['max_speed_cm']:4.1f} cm/s"
            print(
                f"\r[Native Tracker] FPS: {fps:4.1f} | Маркер: {marker_str:<4} | "
                f"angle_x: {angle_str} | Speed: {speed_str} | Max: {max_str} | WS: {clients_cnt}   ",
                end="",
                flush=True
            )

            # Візуалізація вікна OpenCV
            if not args.no_preview:
                draw_hud(frame, args.camera, fps, clients_cnt, detected_angle, detected_marker_id)
                draw_bottom_hud(frame, speed_data, args.marker_size)
                cv2.imshow(window_name, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # 'q' або Esc
                    break
                elif key == ord('r') or key == ord('R'):  # Скидання зафіксованої Speed-max
                    speed_tracker.reset_max()

    except KeyboardInterrupt:
        print("\n\nЗупинка за сигналом Ctrl+C...")
    finally:
        IS_RUNNING = False
        cap.release()
        if not args.no_preview:
            cv2.destroyAllWindows()
        print("\nКамеру закрито, роботу завершено.")

if __name__ == "__main__":
    main()
