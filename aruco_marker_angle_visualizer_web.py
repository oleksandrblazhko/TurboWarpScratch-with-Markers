#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArUco Marker Angle Visualizer & WebSocket Relay Server
======================================================

Цей модуль:
1. Запускає локальний HTTP-сервер для роздачі сторінки ArUco (ArUco/index.html).
2. Запускає WebSocket-сервер на порту 8767 для Scratch (4-Cat-Run-SmartPhone.sb3).
3. Дозволяє обирати веб-камеру через аргумент командного рядка: --camera=0 або --camera=1.
4. Дозволяє обирати словник ArUco: --dict=DICT_4X4_1000, DICT_4X4_50 тощо.
5. Автоматично відкриває браузер за замовчуванням із обраною камерою та словником.
6. Отримує дані оптичного кута нахилу від ArUco-детектора у браузері
   і безперервно транслює їх із частотою 20 Гц (50 мс) у форматі:
   {"accX": 0, "accY": 0, "angle_x": <кут>, "angle_y": 0, "marker_id": <id>}
   до всіх підключених зовнішніх клієнтів (Scratch, ігри, контролери).
"""

import sys
import os
import json
import asyncio
import threading
import webbrowser
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

try:
    import websockets
except ImportError:
    print("Помилка: бібліотека 'websockets' не встановлена. Встановіть її командою: pip install websockets")
    sys.exit(1)

# Множина всіх підключених WebSocket-клієнтів
CONNECTED_CLIENTS = set()

# Посилання на клієнт-джерело (браузер)
BROWSER_CLIENT = None

# Глобальний словник останніх даних сенсора (сумісний з http.py та marker_server.py)
SENSOR_DATA = {
    "accX": 0.0,
    "accY": 0.0,
    "angle_x": 0.0,
    "angle_y": 0.0,
    "marker_id": None
}

class QuietHTTPHandler(SimpleHTTPRequestHandler):
    """Тихий обробник HTTP-запитів без зайвого спаму в консоль."""
    def log_message(self, format, *args):
        pass

def start_http_server(host, port, root_dir):
    """Запускає локальний статичний HTTP-сервер у фоновому потоці."""
    os.chdir(root_dir)
    server = None
    actual_port = port

    for p in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((host, p), QuietHTTPHandler)
            actual_port = p
            break
        except OSError:
            continue

    if not server:
        print(f"Помилка: не вдалося запустити HTTP-сервер на портах {port}-{port+9}")
        return None, None

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port

async def broadcast_loop():
    """Безперервний цикл трансляції даних (20 Гц, 50 мс) до Scratch, як у http.py."""
    while True:
        try:
            if CONNECTED_CLIENTS:
                message = json.dumps({
                    "accX": SENSOR_DATA["accX"],
                    "accY": SENSOR_DATA["accY"],
                    "angle_x": SENSOR_DATA["angle_x"],
                    "angle_y": SENSOR_DATA["angle_y"],
                    "marker_id": SENSOR_DATA["marker_id"]
                })
                # Надсилаємо всім клієнтам-споживачам (наприклад, Scratch), крім браузера-джерела
                targets = [c for c in CONNECTED_CLIENTS if c != BROWSER_CLIENT]
                if targets:
                    await asyncio.gather(
                        *[client.send(message) for client in targets],
                        return_exceptions=True
                    )
        except Exception:
            pass
        await asyncio.sleep(0.05)  # 20 Гц (50 мс)

def create_ws_handler(camera_index):
    """Створює обробник WebSocket із прив'язкою до обраної камери."""
    async def ws_handler(websocket):
        global SENSOR_DATA, BROWSER_CLIENT
        CONNECTED_CLIENTS.add(websocket)
        total = len(CONNECTED_CLIENTS)
        print(f"\n[WS] Новий клієнт підключився. Всього підключено: {total}")

        # Миттєво надсилаємо початковий стан підключеному клієнту (Scratch)
        try:
            init_msg = json.dumps({
                "accX": SENSOR_DATA["accX"],
                "accY": SENSOR_DATA["accY"],
                "angle_x": SENSOR_DATA["angle_x"],
                "angle_y": SENSOR_DATA["angle_y"],
                "marker_id": SENSOR_DATA["marker_id"]
            })
            await websocket.send(init_msg)
        except Exception:
            pass

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("role") == "source" or "angle_x" in data:
                        BROWSER_CLIENT = websocket

                    if "angle_x" in data:
                        SENSOR_DATA["angle_x"] = float(data["angle_x"])
                        SENSOR_DATA["accX"] = float(data.get("accX", 0.0))
                        SENSOR_DATA["accY"] = float(data.get("accY", 0.0))
                        SENSOR_DATA["angle_y"] = float(data.get("angle_y", 0.0))
                        SENSOR_DATA["marker_id"] = data.get("marker_id")

                        # Динамічний рядок статусу в терміналі
                        marker_str = f"#{SENSOR_DATA['marker_id']}" if SENSOR_DATA['marker_id'] is not None else "N/A"
                        print(
                            f"\r[ArUco] Камера: #{camera_index} | Маркер: {marker_str:<4} | "
                            f"angle_x: {SENSOR_DATA['angle_x']:+6.1f}° | "
                            f"WS-клієнтів: {len(CONNECTED_CLIENTS)}   ",
                            end="",
                            flush=True
                        )
                except (json.JSONDecodeError, ValueError):
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            CONNECTED_CLIENTS.remove(websocket)
            if BROWSER_CLIENT == websocket:
                BROWSER_CLIENT = None
            print(f"\n[WS] Клієнт від'єднався. Залишилось клієнтів: {len(CONNECTED_CLIENTS)}")

    return ws_handler

async def run_server(http_port=8000, ws_port=8767, camera_index=0, dictionary="DICT_4X4_1000", open_browser=True):
    """Головна асинхронна функція запуску HTTP та WebSocket серверів."""
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Запуск HTTP-сервера
    http_server, actual_http_port = start_http_server("localhost", http_port, current_dir)
    if not http_server:
        return

    url = f"http://localhost:{actual_http_port}/ArUco/index.html?camera={camera_index}&dict={dictionary}"

    print("=" * 74)
    print("        ArUco Marker Angle Visualizer & WebSocket Relay Server")
    print("=" * 74)
    print(f"HTTP Вебсервер:      http://localhost:{actual_http_port}")
    print(f"Головна сторінка:    {url}")
    print(f"Маркери для тесту:   http://localhost:{actual_http_port}/ArUco/markers.html")
    print(f"WebSocket сервер:    ws://localhost:{ws_port} (для Scratch)")
    print(f"Активна камера:      #{camera_index} (змініть через --camera={camera_index})")
    print(f"Словник ArUco:       {dictionary} (змініть через --dict={dictionary})")
    print("-" * 74)

    # 2. Запуск WebSocket-сервера
    try:
        handler = create_ws_handler(camera_index)
        ws_server = await websockets.serve(handler, "0.0.0.0", ws_port)
        # Запуск фонового безперервного циклу трансляції 20 Гц
        broadcast_task = asyncio.create_task(broadcast_loop())
    except OSError as e:
        print(f"Помилка: не вдалося відкрити WebSocket на порту {ws_port}: {e}")
        return

    # 3. Автоматичне відкриття у браузері
    if open_browser:
        print(f"Відкриття браузера з камерою #{camera_index}...")
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    print("Сервери успішно працюють. Натисніть Ctrl+C для завершення роботи.\n")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        if http_server:
            http_server.shutdown()

def main():
    parser = argparse.ArgumentParser(
        description="ArUco Marker Angle Visualizer & WebSocket Relay Server for Scratch"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Номер камери (0 - зовнішня/Logi C310, 1 - вбудована). За замовчуванням: 0"
    )
    parser.add_argument(
        "--dict",
        type=str,
        default="DICT_4X4_1000",
        help="Словник ArUco (наприклад, DICT_4X4_1000, DICT_4X4_50, DICT_6X6_250). За замовчуванням: DICT_4X4_1000"
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8000,
        help="Порт HTTP-сервера. За замовчуванням: 8000"
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=8767,
        help="Порт WebSocket-сервера для Scratch. За замовчуванням: 8767"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Не відкривати браузер автоматично"
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            run_server(
                http_port=args.http_port,
                ws_port=args.ws_port,
                camera_index=args.camera,
                dictionary=args.dict,
                open_browser=not args.no_browser
            )
        )
    except KeyboardInterrupt:
        print("\n\nЗупинка сервера за запитом користувача. До побачення!")

if __name__ == "__main__":
    main()
