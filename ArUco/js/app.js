import { CameraManager } from "./camera/CameraManager.js";
import { Renderer } from "./renderer/Renderer.js";
import { DetectorFactory } from "./detector/DetectorFactory.js";
import { OpenCvLoader } from "./opencv/OpenCvLoader.js";
import { OpenCvFrameConverter } from "./opencv/OpenCvFrameConverter.js";
import { Config } from "./config/config.js";

console.log("ArUco Angle Visualizer starting...");

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const hudStatus = document.getElementById("hud-status");
const hudWs = document.getElementById("hud-ws");
const cameraSelect = document.getElementById("camera-select");
const loadingOverlay = document.getElementById("loading-overlay");
const loadingText = document.getElementById("loading-text");

// Читання параметрів з URL (?camera=0, ?dict=DICT_4X4_1000)
const urlParams = new URLSearchParams(window.location.search);
const cameraParam = urlParams.get("camera");
const targetCameraIndex = cameraParam !== null ? parseInt(cameraParam, 10) : 0;
const dictParam = urlParams.get("dict");
if (dictParam) {
    Config.dictionary = dictParam;
}

// --- WebSocket Клієнт для передачі кута у Scratch (20 Гц) ---
const WS_PORT = 8767;
const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + (location.hostname || "localhost") + ":" + WS_PORT;
let ws = null;
let wsConnected = false;
let lastSendTime = 0;
const SEND_INTERVAL_MS = 50; // 20 Гц

let lastDetectedAngle = 0.0;
let lastDetectedMarkerId = null;

function updateWsStatus(connected, message) {
    if (!hudWs) return;
    if (connected) {
        hudWs.textContent = message || "🟢 WS: 8767";
        hudWs.style.color = "#00ff66";
    } else {
        hudWs.textContent = message || "🔴 WS: Пошук...";
        hudWs.style.color = "#ffaa44";
    }
}

function connectWebSocket() {
    try {
        ws = new WebSocket(WS_URL);
        ws.onopen = function () {
            wsConnected = true;
            updateWsStatus(true);
            console.log("WebSocket підключено до " + WS_URL);
            ws.send(JSON.stringify({ role: "source", angle_x: 0, marker_id: null }));
        };
        ws.onclose = function () {
            wsConnected = false;
            updateWsStatus(false);
            setTimeout(connectWebSocket, 2000);
        };
        ws.onerror = function () {
            wsConnected = false;
            updateWsStatus(false);
        };
    } catch (e) {
        wsConnected = false;
        updateWsStatus(false);
        setTimeout(connectWebSocket, 2000);
    }
}

function transmitAngleData(primaryMarker) {
    if (!wsConnected || !ws || ws.readyState !== WebSocket.OPEN) return;

    const now = performance.now();
    if (now - lastSendTime < SEND_INTERVAL_MS) return;

    if (primaryMarker && primaryMarker.angle_x !== undefined) {
        lastDetectedAngle = primaryMarker.angle_x;
        lastDetectedMarkerId = primaryMarker.id;
    }

    const payload = JSON.stringify({
        "role": "source",
        "accX": 0,
        "accY": 0,
        "angle_x": lastDetectedAngle,
        "angle_y": 0,
        "marker_id": primaryMarker ? primaryMarker.id : null
    });

    ws.send(payload);
    lastSendTime = now;
}

// Завантаження конфігурації
async function loadConfig() {
    try {
        const res = await fetch(`config.json?t=${Date.now()}`);
        const data = await res.json();
        Object.assign(Config, data);
        if (dictParam) {
            Config.dictionary = dictParam; // пріоритет URL
        }
    } catch (e) {
        console.warn("Using default config:", e);
    }
}

function populateCameraSelect(cameraManager) {
    if (!cameraSelect) return;
    cameraSelect.innerHTML = "";
    const devices = cameraManager.videoDevices || [];
    if (devices.length === 0) {
        const opt = document.createElement("option");
        opt.value = targetCameraIndex;
        opt.textContent = "Камера #" + targetCameraIndex;
        cameraSelect.appendChild(opt);
        return;
    }

    devices.forEach((dev, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        const label = dev.label ? dev.label.replace(/\([0-9a-fA-F:]+\)/, "").trim() : ("Камера #" + idx);
        opt.textContent = "#" + idx + ": " + (label.length > 25 ? label.substring(0, 25) + "..." : label);
        if (idx === targetCameraIndex) {
            opt.selected = true;
        }
        cameraSelect.appendChild(opt);
    });

    cameraSelect.onchange = (e) => {
        const newParams = new URLSearchParams(window.location.search);
        newParams.set("camera", e.target.value);
        window.location.href = window.location.pathname + "?" + newParams.toString();
    };
}

async function main() {
    await loadConfig();

    if (loadingText) loadingText.textContent = "Завантаження OpenCV.js WebAssembly...";
    const cv = await OpenCvLoader.waitForOpenCV();

    if (loadingText) loadingText.textContent = "Запуск відеокамери...";
    const cameraManager = new CameraManager(video);
    const renderer = new Renderer(canvas);
    const frameConverter = new OpenCvFrameConverter(cv);
    const detector = DetectorFactory.create(cv);

    await cameraManager.start(targetCameraIndex);
    populateCameraSelect(cameraManager);

    // Встановлюємо розмір полотна за розмірами відео
    const w = video.videoWidth || Config.cameraWidth || 640;
    const h = video.videoHeight || Config.cameraHeight || 480;
    renderer.resize(w, h);

    // Підключаємо WebSocket
    connectWebSocket();

    // Приховуємо завантажувач
    if (loadingOverlay) {
        loadingOverlay.style.display = "none";
    }

    // Головний цикл обробки кадрів
    function processFrame() {
        if (video.readyState >= 2) {
            // 1. Малюємо поточний кадр з камери на canvas
            renderer.drawVideo(video);

            // 2. Зчитуємо зображення з canvas у Mat OpenCV
            const src = frameConverter.convert(canvas);

            // 3. Виявляємо ArUco-маркери
            const markers = detector.detect(src);
            src.delete();

            // 4. Візуалізуємо рамки та кути на canvas
            renderer.drawMarkers(markers);

            // 5. Оновлюємо статус та транслюємо дані
            if (markers.length > 0) {
                const primary = markers[0];
                if (hudStatus) {
                    const sign = primary.angle_x > 0 ? "+" : "";
                    hudStatus.textContent = `ArUco #${primary.id}: кут ${sign}${primary.angle_x}°`;
                }
                transmitAngleData(primary);
            } else {
                if (hudStatus) {
                    hudStatus.textContent = "Маркер не виявлено (піднесіть ArUco)";
                }
                transmitAngleData(null);
            }
        }

        requestAnimationFrame(processFrame);
    }

    requestAnimationFrame(processFrame);
}

main().catch(err => {
    console.error("Помилка ініціалізації:", err);
    if (loadingText) {
        loadingText.innerHTML = `<span style="color: #ef4444;">Помилка: ${err.message}</span>`;
    }
});
