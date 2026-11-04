"""Select two points and measure their distance in original-image pixels."""

import math
import sys
import tkinter as tk
from tkinter import filedialog

import cv2


WINDOW_NAME = "Pixel Distance Only"


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        path = sys.argv[1] if len(sys.argv) > 1 else filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                       ("All files", "*.*")],
        )
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
    finally:
        root.destroy()
    if not path:
        return

    original = cv2.imread(path)
    if original is None:
        print(f"Could not load image: {path}")
        return

    height, width = original.shape[:2]
    scale = min(1.0, max(1, screen_width - 100) / width,
                max(1, screen_height - 180) / height)
    display_width = max(1, round(width * scale))
    display_height = max(1, round(height * scale))
    preview = cv2.resize(original, (display_width, display_height),
                         interpolation=cv2.INTER_AREA)
    points = []

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if len(points) == 2:
            points.clear()
        # Map display coordinates back to the original image dimensions.
        point = (min(width - 1, max(0, round(x * width / display_width))),
                 min(height - 1, max(0, round(y * height / display_height))))
        points.append(point)
        print(f"Point {len(points)}: {point}")
        if len(points) == 2:
            distance = math.dist(*points)
            print(f"Distance: {distance:.2f} px")

    print(f"Image resolution: {width} x {height}")
    print("Click two points. R/C: clear points. Esc: exit.")
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW_NAME, on_click)
    try:
        while True:
            canvas = preview.copy()
            targets = [(round(x * display_width / width),
                        round(y * display_height / height)) for x, y in points]
            if len(targets) == 2:
                cv2.line(canvas, targets[0], targets[1], (0, 255, 255), 2)
            for index, target in enumerate(targets, start=1):
                cv2.circle(canvas, target, 4, (0, 0, 255), -1)
                cv2.putText(canvas, f"P{index}", (target[0] + 7, target[1] - 7),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1,
                            cv2.LINE_AA)
            lines = ["Click two points | R/C: Clear | Esc: Exit",
                     f"Image: {width} x {height}"]
            if len(points) == 2:
                lines.append(f"Distance: {math.dist(*points):.2f} px")
            for index, text in enumerate(lines):
                position = (10, 25 + index * 25)
                for color, thickness in [((0, 0, 0), 4), ((255, 255, 255), 1)]:
                    cv2.putText(canvas, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, color, thickness, cv2.LINE_AA)
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
