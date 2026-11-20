/**
 * MarkerAngleVisualizer
 * 
 * Модуль для візуалізації зеленої рамки по периметру баркод-маркерів
 * та відображення кута нахилу маркера відносно горизонтальної осі.
 * 
 * Особливості:
 * - 3D Three.js інтеграція: нульова затримка (zero-lag) рендерингу під час руху маркера.
 * - Рамка малюється по периметру маркера з гарантованою товщиною (4 прямокутні смуги + контур).
 * - Кут нахилу обчислюється у діапазоні [-180°, +180°], де 0° — нижня сторона маркера паралельна горизонту.
 * - Текстовий 3D-спрайт завжди повернений обличчям до камери (billboard) і розташований поруч із маркером.
 * - Оптимізація: оновлення текстури Canvas відбувається лише при зміні кута, що усуває зайві навантаження на GPU.
 */
(function (global) {
    'use strict';

    function MarkerAngleVisualizer(options) {
        options = options || {};
        this.camera = options.camera;
        this.markerSize = options.markerSize || 1.0;
        this.borderThickness = options.borderThickness || 0.04;
        this.borderColor = options.borderColor !== undefined ? options.borderColor : 0x00ff00;
        this.textColor = options.textColor || '#00ff44';
        this.bgColor = options.bgColor || 'rgba(0, 0, 0, 0.75)';
        
        // Зміщення бейджа з кутом відносно центру маркера (праворуч від маркера)
        this.labelOffset = options.labelOffset || new THREE.Vector3(0.85, 0.08, 0);

        this.markers = []; // { index, root, visualGroup, sprite, texture, canvas, ctx, lastAngleText, angle }
        
        // Тимчасові вектори для уникнення створення нових об'єктів у циклі анімації
        this._vBL = new THREE.Vector3();
        this._vBR = new THREE.Vector3();
    }

    /**
     * Створює 3D-рамку навколо маркера
     */
    MarkerAngleVisualizer.prototype._createBorderGroup = function () {
        var group = new THREE.Group();
        var s = this.markerSize;
        var hs = s / 2;
        var t = this.borderThickness;
        var yOffset = 0.005; // Злегка піднято над площиною маркера, щоб уникнути z-fighting

        var material = new THREE.MeshBasicMaterial({
            color: this.borderColor,
            side: THREE.DoubleSide,
            depthTest: false
        });

        // 4 смуги по периметру
        // Верхня сторона (уздовж осі X при z = -hs)
        var topGeo = new THREE.PlaneBufferGeometry(s, t);
        var topMesh = new THREE.Mesh(topGeo, material);
        topMesh.rotation.x = -Math.PI / 2;
        topMesh.position.set(0, yOffset, -hs + t / 2);
        topMesh.renderOrder = 998;
        group.add(topMesh);

        // Нижня сторона (уздовж осі X при z = +hs)
        var bottomGeo = new THREE.PlaneBufferGeometry(s, t);
        var bottomMesh = new THREE.Mesh(bottomGeo, material);
        bottomMesh.rotation.x = -Math.PI / 2;
        bottomMesh.position.set(0, yOffset, hs - t / 2);
        bottomMesh.renderOrder = 998;
        group.add(bottomMesh);

        // Ліва сторона (уздовж осі Z при x = -hs)
        var leftGeo = new THREE.PlaneBufferGeometry(t, s - 2 * t);
        var leftMesh = new THREE.Mesh(leftGeo, material);
        leftMesh.rotation.x = -Math.PI / 2;
        leftMesh.position.set(-hs + t / 2, yOffset, 0);
        leftMesh.renderOrder = 998;
        group.add(leftMesh);

        // Права сторона (уздовж осі Z при x = +hs)
        var rightGeo = new THREE.PlaneBufferGeometry(t, s - 2 * t);
        var rightMesh = new THREE.Mesh(rightGeo, material);
        rightMesh.rotation.x = -Math.PI / 2;
        rightMesh.position.set(hs - t / 2, yOffset, 0);
        rightMesh.renderOrder = 998;
        group.add(rightMesh);

        return group;
    };

    /**
     * Створює текстовий бейдж (Sprite) для відображення кута нахилу
     */
    MarkerAngleVisualizer.prototype._createSpriteBadge = function () {
        var canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 128;
        var ctx = canvas.getContext('2d');

        var texture = new THREE.CanvasTexture(canvas);
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;

        var spriteMaterial = new THREE.SpriteMaterial({
            map: texture,
            depthTest: false,
            depthWrite: false
        });

        var sprite = new THREE.Sprite(spriteMaterial);
        // Розмір бейджа у просторі AR
        sprite.scale.set(0.7, 0.35, 1.0);
        sprite.position.copy(this.labelOffset);
        sprite.renderOrder = 999;

        return {
            sprite: sprite,
            texture: texture,
            canvas: canvas,
            ctx: ctx
        };
    };

    /**
     * Оновлює полотно Canvas із новим значенням кута
     */
    MarkerAngleVisualizer.prototype._renderBadgeText = function (ctx, canvas, text) {
        var w = canvas.width;
        var h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Заокруглена плашка
        var r = 24;
        ctx.fillStyle = this.bgColor;
        ctx.beginPath();
        ctx.moveTo(r, 0);
        ctx.lineTo(w - r, 0);
        ctx.quadraticCurveTo(w, 0, w, r);
        ctx.lineTo(w, h - r);
        ctx.quadraticCurveTo(w, h, w - r, h);
        ctx.lineTo(r, h);
        ctx.quadraticCurveTo(0, h, 0, h - r);
        ctx.lineTo(0, r);
        ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.closePath();
        ctx.fill();

        // Тонка зелена рамка навколо бейджа
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 6;
        ctx.stroke();

        // Текст кута
        ctx.fillStyle = this.textColor;
        ctx.font = 'bold 50px Arial, Helvetica, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, w / 2, h / 2);
    };

    /**
     * Прив'язує візуалізатор до масиву кореневих об'єктів маркерів
     * @param {THREE.Group[]} markerRoots - масив markerRoots з Three.js
     * @param {number[]} barcodeIndices - індекси баркод-маркерів
     */
    MarkerAngleVisualizer.prototype.attachToMarkers = function (markerRoots, barcodeIndices) {
        var _this = this;

        barcodeIndices.forEach(function (idx) {
            var root = markerRoots[idx];
            if (!root) return;

            var visualGroup = new THREE.Group();
            var border = _this._createBorderGroup();
            var badge = _this._createSpriteBadge();

            visualGroup.add(border);
            visualGroup.add(badge.sprite);

            root.add(visualGroup);

            // Початкове малювання 0.0°
            _this._renderBadgeText(badge.ctx, badge.canvas, '0.0°');
            badge.texture.needsUpdate = true;

            _this.markers.push({
                index: idx,
                root: root,
                visualGroup: visualGroup,
                sprite: badge.sprite,
                texture: badge.texture,
                canvas: badge.canvas,
                ctx: badge.ctx,
                lastAngleText: '0.0°',
                angle: 0
            });
        });
    };

    /**
     * Визначає кут нахилу нижньої сторони маркера відносно горизонту
     * у діапазоні [-180°, +180°].
     * 0° — нижня сторона паралельна горизонтальній осі екрана.
     */
    MarkerAngleVisualizer.prototype.calculateMarkerAngle = function (markerRoot) {
        var hs = this.markerSize / 2;

        // Нижня сторона маркера в локальній системі координат X-Z:
        // Нижня ліва точка (BL): (-hs, 0, hs)
        // Нижня права точка (BR): (hs, 0, hs)
        this._vBL.set(-hs, 0, hs);
        this._vBR.set(hs, 0, hs);

        // Переконуємось, що matrixWorld маркера актуальна
        markerRoot.updateMatrixWorld(true);

        // Переводимо точки у глобальний простір
        this._vBL.applyMatrix4(markerRoot.matrixWorld);
        this._vBR.applyMatrix4(markerRoot.matrixWorld);

        // Проєктуємо на площину екрана камери
        if (this.camera) {
            this._vBL.project(this.camera);
            this._vBR.project(this.camera);
        }

        // Вектор нижньої сторони у проєкції на площину екрана (X - горизонталь, Y - вертикаль)
        var dx = this._vBR.x - this._vBL.x;
        var dy = this._vBR.y - this._vBL.y;

        // Розраховуємо кут у радіанах та переводимо в градуси
        var angleRad = Math.atan2(dy, dx);
        var angleDeg = angleRad * (180 / Math.PI);

        return angleDeg;
    };

    /**
     * Оновлення стану всіх маркерів на кожен кадр (викликається в animate/update)
     */
    MarkerAngleVisualizer.prototype.update = function () {
        var _this = this;

        for (var i = 0; i < this.markers.length; i++) {
            var item = this.markers[i];
            var root = item.root;

            if (root && root.visible) {
                item.visualGroup.visible = true;

                // Розраховуємо кут нахилу
                var angle = _this.calculateMarkerAngle(root);
                item.angle = angle;

                // Форматуємо значення (з точністю до одного десяткового знака)
                var angleText;
                if (Math.abs(angle) < 0.05) {
                    angleText = '0.0°';
                } else {
                    angleText = (angle > 0 ? '+' : '') + angle.toFixed(1) + '°';
                }

                // Оновлюємо текстуру тільки тоді, коли текст реально змінився
                if (angleText !== item.lastAngleText) {
                    item.lastAngleText = angleText;
                    _this._renderBadgeText(item.ctx, item.canvas, angleText);
                    item.texture.needsUpdate = true;
                }
            } else {
                item.visualGroup.visible = false;
            }
        }
    };

    /**
     * Повертає поточний кут для вказаного індексу маркера
     */
    MarkerAngleVisualizer.prototype.getAngle = function (markerIndex) {
        for (var i = 0; i < this.markers.length; i++) {
            if (this.markers[i].index === markerIndex) {
                return this.markers[i].angle;
            }
        }
        return null;
    };

    /**
     * Очищення ресурсів
     */
    MarkerAngleVisualizer.prototype.dispose = function () {
        for (var i = 0; i < this.markers.length; i++) {
            var item = this.markers[i];
            if (item.texture) item.texture.dispose();
            if (item.sprite && item.sprite.material) item.sprite.material.dispose();
            if (item.visualGroup && item.root) {
                item.root.remove(item.visualGroup);
            }
        }
        this.markers = [];
    };

    // Експорт у глобальну область видимості
    global.MarkerAngleVisualizer = MarkerAngleVisualizer;

})(typeof window !== 'undefined' ? window : this);
