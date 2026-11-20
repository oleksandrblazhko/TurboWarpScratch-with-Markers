import { Config } from "../config/config.js";
import { Logger } from "../utils/logger.js";

export class CameraManager {
    constructor(video) {
        this.video = video;
        this.videoDevices = [];
        this.activeCameraIndex = 0;
    }

    async getAvailableDevices() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
            return [];
        }
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            this.videoDevices = devices.filter(d => d.kind === 'videoinput');
            return this.videoDevices;
        } catch (e) {
            Logger.error("Failed to enumerate devices: " + e.message);
            return [];
        }
    }

    async start(targetIndex = 0) {
        this.activeCameraIndex = targetIndex;
        await this.getAvailableDevices();

        const chosenDevice = this.videoDevices[targetIndex] || this.videoDevices[0];
        const attempts = [];

        if (chosenDevice && chosenDevice.deviceId) {
            // Спроба 1: точний deviceId з бажаним розміром
            attempts.push({
                audio: false,
                video: {
                    deviceId: { exact: chosenDevice.deviceId },
                    width: { ideal: Config.cameraWidth || 640 },
                    height: { ideal: Config.cameraHeight || 480 }
                }
            });
            // Спроба 2: точний deviceId без вимог до розміру (для специфічних UVC драйверів)
            attempts.push({
                audio: false,
                video: {
                    deviceId: { exact: chosenDevice.deviceId }
                }
            });
            // Спроба 3: ideal deviceId
            attempts.push({
                audio: false,
                video: {
                    deviceId: { ideal: chosenDevice.deviceId }
                }
            });
        }

        // Резервна спроба за замовчуванням
        attempts.push({
            audio: false,
            video: {
                width: { ideal: Config.cameraWidth || 640 },
                height: { ideal: Config.cameraHeight || 480 },
                facingMode: "environment"
            }
        });

        let stream = null;
        let lastError = null;

        for (let i = 0; i < attempts.length; i++) {
            try {
                Logger.info(`CameraManager: спроба підключення #${i + 1}`);
                stream = await navigator.mediaDevices.getUserMedia(attempts[i]);
                break;
            } catch (err) {
                lastError = err;
                Logger.info(`CameraManager: спроба #${i + 1} не вдалася (${err.name}: ${err.message})`);
                await new Promise(r => setTimeout(r, 400));
            }
        }

        if (!stream) {
            throw lastError || new Error("Не вдалося відкрити вебкамеру");
        }

        this.video.srcObject = stream;
        this.video.muted = true;
        this.video.playsInline = true;

        await this.video.play();
        Logger.info(`CameraManager: камеру #${targetIndex} успішно запущено (${this.video.videoWidth}x${this.video.videoHeight})`);

        // Оновлюємо пристрої, якщо вони раніше не мали назв
        if (this.videoDevices.length === 0 || !this.videoDevices[0].label) {
            await this.getAvailableDevices();
        }

        return stream;
    }

    stop() {
        const stream = this.video.srcObject;
        if (stream) {
            for (const track of stream.getTracks()) {
                track.stop();
            }
        }
        this.video.pause();
        this.video.srcObject = null;
        Logger.info("Camera stopped");
    }
}
