import { Marker } from "../models/Marker.js";
import { Point } from "../models/Point.js";
import { PerspectiveCorrector } from "./PerspectiveCorrector.js";
import { Config } from "../config/config.js";

export class OpenCvArucoDetector {
    constructor(cv) {
        this.cv = cv;

        const dictName = Config.dictionary || "DICT_4X4_1000";
        const dictConstant = (this.cv[dictName] !== undefined) ? this.cv[dictName] : this.cv.DICT_4X4_1000;
        const dictionary = this.cv.getPredefinedDictionary(dictConstant);
        const parameters = new this.cv.aruco_DetectorParameters();
        const refineParameters = new this.cv.aruco_RefineParameters(10.0, 3.0, false);

        this.detector = new this.cv.aruco_ArucoDetector(
            dictionary,
            parameters,
            refineParameters
        );
        
        this.perspectiveCorrector = new PerspectiveCorrector(cv);
    }

    detect(frame) {
        let gray = new this.cv.Mat();
        this.cv.cvtColor(frame, gray, this.cv.COLOR_RGBA2GRAY);

        const corners = new this.cv.MatVector();
        const ids = new this.cv.Mat();
        const rejected = new this.cv.MatVector();

        this.detector.detectMarkers(gray, corners, ids, rejected);

        const markerList = [];
        if (ids.rows > 0) {
            for (let i = 0; i < ids.rows; i++) {
                const id = ids.data32S ? ids.data32S[i] : ids.data[i];
                const marker = new Marker(id);
                const cornerMat = corners.get(i);
                
                marker.addCorner(cornerMat.data32F[0], cornerMat.data32F[1]);
                marker.addCorner(cornerMat.data32F[2], cornerMat.data32F[3]);
                marker.addCorner(cornerMat.data32F[4], cornerMat.data32F[5]);
                marker.addCorner(cornerMat.data32F[6], cornerMat.data32F[7]);
                
                // Розрахунок кута нахилу маркера до горизонту [-180..+180] градусів
                // За вектором верхньої грані: від corner 0 (top-left) до corner 1 (top-right)
                const dx = cornerMat.data32F[2] - cornerMat.data32F[0];
                const dy = cornerMat.data32F[3] - cornerMat.data32F[1];
                let angle = Math.atan2(dy, dx) * 180 / Math.PI;
                if (angle > 180) angle -= 360;
                if (angle < -180) angle += 360;
                marker.angle_x = parseFloat(angle.toFixed(1));

                // The center is calculated here in pixels for use when correction is not available
                marker.center = marker.calculateCenter();
                marker.correctedCorners = marker.corners.map(c => new Point(c.x, c.y));
                marker.correctedCenter = marker.center;
                markerList.push(marker);
            }
        }
        
        gray.delete();
        corners.delete();
        ids.delete();
        rejected.delete();

        return markerList;
    }

    correctMarkers(markers, calibration, objectsData) {
        if (!calibration || 
            !calibration.image_to_board_matrix || calibration.image_to_board_matrix.empty() ||
            !calibration.board_to_image_matrix || calibration.board_to_image_matrix.empty()
            ) {
            return; // No correction possible
        }
            
        const boardDimensions = Config.boardDimensions;
        const boardCenter = new Point(boardDimensions / 2, boardDimensions / 2);

        // Ensure matrices are 32F for the perspectiveTransform function
        const image_to_board_32f = new this.cv.Mat();
        const board_to_image_32f = new this.cv.Mat();
        calibration.image_to_board_matrix.convertTo(image_to_board_32f, this.cv.CV_32F);
        calibration.board_to_image_matrix.convertTo(board_to_image_32f, this.cv.CV_32F);

        // This method will now modify the markers in the list directly
        this.perspectiveCorrector.correct(
            markers,
            boardCenter,
            Config.cameraHeightCali,
            Config.markerSize,
            boardDimensions,
            image_to_board_32f,
            board_to_image_32f,
            objectsData
        );

        // Cleanup
        image_to_board_32f.delete();
        board_to_image_32f.delete();
    }
}
