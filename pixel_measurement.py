"""Interactive pixel-distance measurement tool for OpenCV images."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any

import cv2
import numpy as np


CAMERA_DISTANCE_CM = 30.0
REFERENCE_LENGTH_MM = 50.00
REFERENCE_DISTANCE_PX = 221.00
MM_PER_PIXEL = REFERENCE_LENGTH_MM / REFERENCE_DISTANCE_PX
WINDOW_NAME = "Pixel Measurement Tool"
SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")


class PixelMeasurementTool:
    """Calibrate an image and measure point-to-point distances."""

    def __init__(self) -> None:
        self.original_image: np.ndarray | None = None
        self.display_image: np.ndarray | None = None
        self.image_path: Path | None = None
        self.reference_distance_px: float | None = None
        self.mm_per_pixel: float | None = None
        self.reference_points: list[tuple[int, int]] = []
        self.display_scale = 1.0
        self.display_width = 0
        self.display_height = 0
        self.current_points: list[tuple[int, int]] = []
        self.measurements: list[dict[str, Any]] = []

    def _select_image(self) -> Path | None:
        """Open a file picker and return a supported image path."""
        root = tk.Tk()
        root.withdraw()
        try:
            selected = filedialog.askopenfilename(
                title="Select an image to measure",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.bmp"),
                    ("JPEG files", "*.jpg *.jpeg"),
                    ("PNG files", "*.png"),
                    ("Bitmap files", "*.bmp"),
                ],
            )
        finally:
            root.destroy()

        if not selected:
            return None

        path = Path(selected)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            self._show_error(f"Unsupported image type: {path.suffix or '(none)'}")
            return None
        return path

    def _show_error(self, message: str) -> None:
        """Report an error in the terminal and, when possible, in a dialog."""
        print(f"Error: {message}")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Pixel Measurement Tool", message, parent=root)
            root.destroy()
        except tk.TclError:
            # The terminal message remains available if a GUI dialog cannot open.
            pass

    def load_image(self) -> bool:
        """Select and load the image, returning whether loading succeeded."""
        self.image_path = self._select_image()
        if self.image_path is None:
            print("No image selected. Exiting.")
            return False

        self.original_image = cv2.imread(str(self.image_path), cv2.IMREAD_COLOR)
        if self.original_image is None or self.original_image.size == 0:
            self._show_error(f"Could not load image: {self.image_path}")
            return False

        return True

    def calculate_display_scale(self) -> float:
        """Calculate a screen-fitting scale while never enlarging the image."""
        if self.original_image is None:
            return 1.0

        image_height, image_width = self.original_image.shape[:2]
        root = tk.Tk()
        root.withdraw()
        try:
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
        finally:
            root.destroy()

        available_width = max(320, screen_width - 100)
        available_height = max(240, screen_height - 180)
        self.display_scale = min(
            1.0,
            available_width / image_width,
            available_height / image_height,
        )
        self.display_width = max(1, round(image_width * self.display_scale))
        self.display_height = max(1, round(image_height * self.display_scale))
        return self.display_scale

    def display_to_original(self, point: tuple[int, int]) -> tuple[int, int]:
        """Convert a display coordinate to a clamped original-image coordinate."""
        if self.original_image is None:
            raise RuntimeError("An image must be loaded before converting coordinates.")

        image_height, image_width = self.original_image.shape[:2]
        x = min(image_width - 1, max(0, round(point[0] / self.display_scale)))
        y = min(image_height - 1, max(0, round(point[1] / self.display_scale)))
        return x, y

    def original_to_display(self, point: tuple[int, int]) -> tuple[int, int]:
        """Convert an original-image coordinate to a display coordinate."""
        return round(point[0] * self.display_scale), round(point[1] * self.display_scale)

    @staticmethod
    def calculate_distance(
        point_1: tuple[int, int], point_2: tuple[int, int]
    ) -> float:
        """Return Euclidean distance between two points in pixels."""
        return math.hypot(point_2[0] - point_1[0], point_2[1] - point_1[1])

    def mouse_callback(
        self, event: int, x: int, y: int, flags: int, param: Any
    ) -> None:
        """Handle two-point measurement clicks in original coordinates."""
        del flags, param
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if len(self.current_points) == 2:
            self.current_points = []

        self.current_points.append(self.display_to_original((x, y)))
        if len(self.current_points) == 1:
            print(f"Point 1 selected: {self.current_points[0]}")
        else:
            point_1, point_2 = self.current_points
            distance = self.calculate_distance(point_1, point_2)
            measurement = {
                "id": len(self.measurements) + 1,
                "p1": point_1,
                "p2": point_2,
                "distance_px": distance,
                "distance_mm": MM_PER_PIXEL * distance,
            }
            self.measurements.append(measurement)
            print(f"\nMeasurement {measurement['id']}")
            print(f"Point 1: {point_1}")
            print(f"Point 2: {point_2}")
            print(f"Pixel distance: {distance:.2f} px")
            print(f"Physical distance: {measurement['distance_mm']:.2f} mm")

    def reset_current_measurement(self) -> None:
        """Discard only the currently unfinished point selection."""
        self.current_points = []

    def clear_measurements(self) -> None:
        """Clear all completed and unfinished measurements."""
        self.measurements.clear()
        self.reset_current_measurement()

    def _draw_label(
        self,
        image: np.ndarray,
        text: str,
        position: tuple[int, int],
        font_scale: float,
        thickness: int,
    ) -> None:
        """Draw readable text with a dark outline and a light foreground."""
        cv2.putText(
            image,
            text,
            position,
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 0, 0),
            thickness + 3,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            text,
            position,
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    def draw_measurements(
        self, image: np.ndarray, *, for_display: bool = False
    ) -> np.ndarray:
        """Return an annotated copy of an image without modifying the original."""
        if for_display:
            annotated = cv2.resize(
                image,
                (self.display_width, self.display_height),
                interpolation=cv2.INTER_AREA,
            )
            scale = self.display_scale
        else:
            annotated = image.copy()
            scale = 1.0
        min_dimension = min(annotated.shape[:2])
        radius = max(3, min(18, round(min_dimension * 0.006)))
        thickness = max(1, round(radius / 3))
        font_scale = max(0.35, min(1.2, min_dimension / 1200))

        def to_target(point: tuple[int, int]) -> tuple[int, int]:
            return (round(point[0] * scale), round(point[1] * scale))

        def draw_point(point: tuple[int, int], label: str) -> None:
            target = to_target(point)
            cv2.circle(annotated, target, radius, (0, 0, 255), -1, cv2.LINE_AA)
            self._draw_label(
                annotated,
                label,
                (target[0] + radius + 4, target[1] - radius - 4),
                font_scale,
                thickness,
            )

        for measurement in self.measurements:
            point_1 = measurement["p1"]
            point_2 = measurement["p2"]
            target_1 = to_target(point_1)
            target_2 = to_target(point_2)
            cv2.line(annotated, target_1, target_2, (0, 255, 255), thickness, cv2.LINE_AA)
            draw_point(point_1, "P1")
            draw_point(point_2, "P2")
            midpoint = (
                (target_1[0] + target_2[0]) // 2,
                (target_1[1] + target_2[1]) // 2,
            )
            self._draw_label(
                annotated,
                (
                    f"{measurement['distance_px']:.2f} px / "
                    f"{measurement['distance_mm']:.2f} mm"
                ),
                (midpoint[0] + 6, midpoint[1] - 8),
                font_scale,
                thickness,
            )

        if self.current_points:
            draw_point(self.current_points[0], "P1")

        return annotated

    def _add_controls(self, image: np.ndarray) -> None:
        """Add keyboard instructions to the display image."""
        lines = [
            "Left Click: Select Point",
            "R: Reset   C: Clear   S: Save   ESC: Exit",
        ]
        padding = 10
        line_height = 25
        overlay_height = padding * 2 + line_height * len(lines)
        overlay = image.copy()
        cv2.rectangle(
            overlay,
            (0, 0),
            (image.shape[1], overlay_height),
            (0, 0, 0),
            -1,
        )
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)
        for index, line in enumerate(lines):
            self._draw_label(
                image,
                line,
                (padding, padding + line_height * (index + 1) - 5),
                0.55,
                1,
            )

    def save_annotated_image(self) -> None:
        """Save all current annotations at the original image resolution."""
        if self.original_image is None:
            return
        output_path = Path.cwd() / (
            f"pixel_measurement_result_{datetime.now():%Y%m%d_%H%M%S}.png"
        )
        annotated = self.draw_measurements(self.original_image)
        if not cv2.imwrite(str(output_path), annotated):
            self._show_error(f"Could not save annotated image: {output_path}")
            return
        print(f"Annotated image saved to: {output_path}")

    def run(self) -> None:
        """Run the image window until the user presses ESC."""
        if not self.load_image() or self.original_image is None:
            return

        self.calculate_display_scale()
        image_height, image_width = self.original_image.shape[:2]
        print(f"Original resolution: {image_width} x {image_height}")
        print(f"Display resolution: {self.display_width} x {self.display_height}")
        print(f"Display scale: {self.display_scale:.6f}")
        print(f"Camera distance: {CAMERA_DISTANCE_CM:.1f} cm")
        print(f"Reference length: {REFERENCE_LENGTH_MM:.2f} mm")
        print(f"Reference distance: {REFERENCE_DISTANCE_PX:.2f} px")
        print(f"Conversion factor: {MM_PER_PIXEL:.6f} mm/px")
        print("Click two points to measure their distance in pixels.")

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(WINDOW_NAME, self.mouse_callback)
        try:
            while True:
                annotated = self.draw_measurements(self.original_image, for_display=True)
                self._add_controls(annotated)
                self.display_image = annotated
                cv2.imshow(WINDOW_NAME, self.display_image)
                key = cv2.waitKey(20) & 0xFF
                if key == 27:
                    break
                if key in (ord("r"), ord("R")):
                    self.reset_current_measurement()
                elif key in (ord("c"), ord("C")):
                    self.clear_measurements()
                elif key in (ord("s"), ord("S")):
                    self.save_annotated_image()
        finally:
            cv2.destroyAllWindows()


def main() -> None:
    """Start the pixel measurement application."""
    PixelMeasurementTool().run()


if __name__ == "__main__":
    main()
