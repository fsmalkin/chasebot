"""Laptop-side ArUco delivery-target detection and monocular pose estimation."""
import math


CALIBRATION_WIDTH_PX = 320.0


class ArucoTargetDetector:
    """Detect one configured delivery marker and estimate its camera-frame pose.

    The metric estimate uses the empirical focal value from the 320x240
    golf-ball bench calibration and assumes a flat marker with a known printed
    size. The payload carries those limits so downstream planning can keep this
    bounded estimate distinct from a calibrated camera model.
    """

    def __init__(self, cv2_module, np_module, dictionary_name="DICT_4X4_50",
                 marker_id=0, marker_size_m=0.10, focal_px=225.317):
        self.cv2 = cv2_module
        self.np = np_module
        self.dictionary_name = str(dictionary_name)
        self.marker_id = int(marker_id)
        self.marker_size_m = float(marker_size_m)
        self.focal_px = float(focal_px)
        if self.marker_id < 0:
            raise ValueError("ArUco marker id must be non-negative")
        if self.marker_size_m <= 0.0:
            raise ValueError("ArUco marker size must be positive")
        if self.focal_px <= 0.0:
            raise ValueError("ArUco focal length must be positive")
        aruco = getattr(self.cv2, "aruco", None)
        if aruco is None:
            raise RuntimeError("OpenCV ArUco module is unavailable")
        dictionary_id = getattr(aruco, self.dictionary_name, None)
        if dictionary_id is None:
            raise ValueError("unknown ArUco dictionary: %s" % self.dictionary_name)
        self.aruco = aruco
        self.dictionary = aruco.getPredefinedDictionary(dictionary_id)
        if hasattr(aruco, "DetectorParameters"):
            parameters = aruco.DetectorParameters()
        else:
            parameters = aruco.DetectorParameters_create()
        if hasattr(aruco, "ArucoDetector"):
            self.detector = aruco.ArucoDetector(self.dictionary, parameters)
            self.parameters = None
        else:
            self.detector = None
            self.parameters = parameters

    @staticmethod
    def _quad_area(points):
        total = 0.0
        for i in range(4):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % 4]
            total += (x0 * y1) - (x1 * y0)
        return abs(total) / 2.0

    def _detect_markers(self, gray):
        if self.detector is not None:
            return self.detector.detectMarkers(gray)
        return self.aruco.detectMarkers(
            gray,
            self.dictionary,
            parameters=self.parameters,
        )

    def _estimate_pose(self, points, width, height):
        scale = float(width) / CALIBRATION_WIDTH_PX
        focal = self.focal_px * scale
        cx = float(width) / 2.0
        cy = float(height) / 2.0
        half = self.marker_size_m / 2.0
        object_points = self.np.array([
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=self.np.float64)
        camera_matrix = self.np.array([
            [focal, 0.0, cx],
            [0.0, focal, cy],
            [0.0, 0.0, 1.0],
        ], dtype=self.np.float64)
        distortion = self.np.zeros((5, 1), dtype=self.np.float64)
        flag = getattr(self.cv2, "SOLVEPNP_IPPE_SQUARE", self.cv2.SOLVEPNP_ITERATIVE)
        ok, rvec, tvec = self.cv2.solvePnP(
            object_points,
            self.np.asarray(points, dtype=self.np.float64),
            camera_matrix,
            distortion,
            flags=flag,
        )
        if not ok:
            return None, focal, cx, cy
        rv = [float(v) for v in rvec.reshape(-1)]
        tv = [float(v) for v in tvec.reshape(-1)]
        if len(tv) != 3 or tv[2] <= 0.0:
            return None, focal, cx, cy
        return {"rvec": rv, "tvec": tv}, focal, cx, cy

    def detect(self, image_rgb):
        array = self.np.asarray(image_rgb)
        if array.ndim == 3:
            gray = self.cv2.cvtColor(array, self.cv2.COLOR_RGB2GRAY)
        elif array.ndim == 2:
            gray = array
        else:
            raise ValueError("expected a grayscale or RGB image")
        corners, ids, _rejected = self._detect_markers(gray)
        if ids is None:
            return None
        matches = []
        flat_ids = ids.reshape(-1)
        for i, found_id in enumerate(flat_ids):
            if int(found_id) != self.marker_id:
                continue
            points = self.np.asarray(corners[i], dtype=self.np.float64).reshape(4, 2)
            matches.append((self._quad_area(points), points))
        if not matches:
            return None
        _area, points = max(matches, key=lambda item: item[0])
        height, width = gray.shape[:2]
        pose, focal, cx, cy = self._estimate_pose(points, width, height)
        center_x = sum(float(p[0]) for p in points) / 4.0
        center_y = sum(float(p[1]) for p in points) / 4.0
        sides = []
        for i in range(4):
            dx = float(points[(i + 1) % 4][0] - points[i][0])
            dy = float(points[(i + 1) % 4][1] - points[i][1])
            sides.append(math.sqrt((dx * dx) + (dy * dy)))
        center_error = (center_x - cx) / cx if cx > 0.0 else 0.0
        result = {
            "id": self.marker_id,
            "dictionary": self.dictionary_name,
            "marker_size_m": round(self.marker_size_m, 4),
            "corners_px": [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in points],
            "center_px": [round(center_x, 2), round(center_y, 2)],
            "center_error": round(center_error, 6),
            "side_px": round(sum(sides) / len(sides), 2),
            "calibration": {
                "source": "mono_distance_calibration_bench01",
                "reference_width_px": int(CALIBRATION_WIDTH_PX),
                "focal_px": round(focal, 3),
                "cx_px": round(cx, 3),
                "cy_px": round(cy, 3),
                "distortion": "assumed_zero",
            },
            "limits": [
                "empirical focal estimate; camera intrinsics and lens distortion are not fully calibrated",
                "metric pose assumes a flat marker printed at the configured size",
            ],
        }
        if pose is None:
            bearing = math.atan2(center_x - cx, focal)
            result.update({
                "pose_status": "bearing_only",
                "pose_method": "marker_center_ray",
                "bearing_rad": round(bearing, 6),
                "bearing_deg": round(math.degrees(bearing), 3),
                "x_m": None,
                "y_m": None,
                "z_m": None,
                "distance_m": None,
                "rvec_rad": None,
            })
            return result
        rvec = pose["rvec"]
        x_m, y_m, z_m = pose["tvec"]
        bearing = math.atan2(x_m, z_m)
        distance = math.sqrt((x_m * x_m) + (y_m * y_m) + (z_m * z_m))
        result.update({
            "pose_status": "metric",
            "pose_method": "aruco_ippe_square_empirical_intrinsics",
            "bearing_rad": round(bearing, 6),
            "bearing_deg": round(math.degrees(bearing), 3),
            "x_m": round(x_m, 4),
            "y_m": round(y_m, 4),
            "z_m": round(z_m, 4),
            "distance_m": round(distance, 4),
            "rvec_rad": [round(v, 6) for v in rvec],
        })
        return result
