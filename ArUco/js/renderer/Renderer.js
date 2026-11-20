import { Point } from "../models/Point.js";

export class Renderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext("2d");
    }

    resize(width, height) {
        this.canvas.width = width;
        this.canvas.height = height;
    }

    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    drawVideo(video) {
        if (!video || !video.videoWidth) return;
        this.ctx.drawImage(video, 0, 0, this.canvas.width, this.canvas.height);
    }

    drawMarkers(markers) {
        if (!markers || markers.length === 0) return;

        const ctx = this.ctx;

        for (const marker of markers) {
            if (!marker.corners || marker.corners.length < 4) continue;

            ctx.save();

            // 1. Зелений контур навколо ArUco-маркера
            ctx.strokeStyle = "#00ff66";
            ctx.lineWidth = 3;
            ctx.lineJoin = "round";
            ctx.beginPath();
            ctx.moveTo(marker.corners[0].x, marker.corners[0].y);
            for (let j = 1; j < 4; j++) {
                ctx.lineTo(marker.corners[j].x, marker.corners[j].y);
            }
            ctx.closePath();
            ctx.stroke();

            // 2. Виділення верхньої грані (0 -> 1) для візуалізації орієнтації
            ctx.strokeStyle = "#38bdf8";
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(marker.corners[0].x, marker.corners[0].y);
            ctx.lineTo(marker.corners[1].x, marker.corners[1].y);
            ctx.stroke();

            // 3. Вектор напрямку від центру до верхньої грані
            const center = marker.center || marker.calculateCenter();
            const topMidX = (marker.corners[0].x + marker.corners[1].x) / 2;
            const topMidY = (marker.corners[0].y + marker.corners[1].y) / 2;

            ctx.strokeStyle = "#38bdf8";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(center.x, center.y);
            ctx.lineTo(topMidX, topMidY);
            ctx.stroke();

            // Центральна точка
            ctx.fillStyle = "#ffffff";
            ctx.beginPath();
            ctx.arc(center.x, center.y, 3, 0, Math.PI * 2);
            ctx.fill();

            // 4. Плашка (бейдж) з номером маркера та кутом нахилу до горизонту
            let minX = Infinity;
            let minY = Infinity;
            for (const corner of marker.corners) {
                if (corner.x < minX) minX = corner.x;
                if (corner.y < minY) minY = corner.y;
            }

            const angleStr = (marker.angle_x !== undefined && marker.angle_x !== null)
                ? `${marker.angle_x > 0 ? '+' : ''}${marker.angle_x.toFixed(1)}°`
                : '0.0°';

            const badgeText = `ArUco #${marker.id} | ${angleStr}`;

            ctx.font = "bold 13px -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif";
            const textMetrics = ctx.measureText(badgeText);
            const badgeW = textMetrics.width + 16;
            const badgeH = 26;

            const badgeX = Math.max(10, minX);
            const badgeY = Math.max(badgeH + 8, minY - 10);

            // Тінь та фон плашки
            ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
            if (ctx.roundRect) {
                ctx.beginPath();
                ctx.roundRect(badgeX, badgeY - badgeH + 6, badgeW, badgeH, 6);
                ctx.fill();
                ctx.strokeStyle = "#00ff66";
                ctx.lineWidth = 1.5;
                ctx.stroke();
            } else {
                ctx.fillRect(badgeX, badgeY - badgeH + 6, badgeW, badgeH);
                ctx.strokeStyle = "#00ff66";
                ctx.lineWidth = 1.5;
                ctx.strokeRect(badgeX, badgeY - badgeH + 6, badgeW, badgeH);
            }

            // Текст на плашці
            ctx.fillStyle = "#00ff66";
            ctx.fillText(badgeText, badgeX + 8, badgeY + 1);

            ctx.restore();
        }
    }
}
