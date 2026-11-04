"""Measure the pixel distance between two clicked points in an image.

Run with ``python click_pixel_distance.py [image_path]``. If no image path is
provided, an image picker opens.
"""

import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import cv2


WINDOW_NAME = "Click to Measure Pixel Distance"
SUPPORTED_IMAGE_TYPES = "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"


def choose_image() -> tuple[Path | None, int, int]:
    """Return the selected path and available screen dimensions."""
    root = tk.Tk()
    root.withdraw()
    try:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        selected = sys.argv[1] if len(sys.argv) > 1 else filedialog.askopenfilename(
            title="Choose an image to measure",
            filetypes=[("Image files", SUPPORTED_IMAGE_TYPES), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return (Path(selected) if selected else None, screen_width, screen_height)


def main() -> None:
    path, screen_width, screen_height = choose_image()
    if path is None:
        return

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        print(f"Could not load image: {path}")
        return

    image_height, image_width = image.shape[:2]
    scale = min(1.0, (screen_width - 100) / image_width,
                (screen_height - 180) / image_height)
    display_width = max(1, round(image_width * scale))
    display_height = max(1, round(image_height * scale))
    preview = cv2.resize(image, (display_width, display_height),
                         interpolation=cv2.INTER_AREA)
    points: list[tuple[int, int]] = []

    def on_click(event, x, y, _flags, _param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if len(points) == 2:
            points.clear()
        original_point = (
            min(image_width - 1, max(0, round(x / scale))),
            min(image_height - 1, max(0, round(y / scale))),
        )
        points.append(original_point)
        print(f"Point {len(points)}: {original_point}")
        if len(points) == 2:
            print(f"Distance: {math.dist(points[0], points[1]):.2f} px")

    print(f"Image: {path} ({image_width} x {image_height})")
    print("Click two endpoints. Click again to start another measurement.")
    print("R/C: clear points. Esc: exit.")
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW_NAME, on_click)
    try:
        while True:
            canvas = preview.copy()
            display_points = [
                (round(px * scale), round(py * scale)) for px, py in points
            ]
            if len(display_points) == 2:
                cv2.line(canvas, display_points[0], display_points[1],
                         (0, 255, 255), 2, cv2.LINE_AA)
            for index, point in enumerate(display_points, start=1):
                cv2.circle(canvas, point, 5, (0, 0, 255), -1, cv2.LINE_AA)
                cv2.putText(canvas, f"P{index}", (point[0] + 8, point[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2,
                            cv2.LINE_AA)
            distance_text = (
                f"Distance: {math.dist(points[0], points[1]):.2f} px"
                if len(points) == 2 else "Click two endpoints"
            )
            cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 34), (35, 35, 35), -1)
            cv2.putText(canvas, distance_text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow(WINDOW_NAME, canvas)
            key = cv2.waitKey(20) & 0xFF
            if key == 27 or cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key in (ord("r"), ord("R"), ord("c"), ord("C")):
                points.clear()
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
