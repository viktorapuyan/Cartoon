# Cartoon — Computer Vision-Based Product Measurement

CartonIQ is a real-time computer vision system that automatically measures the dimensions of carton boxes and generates production-ready dieline patterns. It uses a dual-camera setup with YOLOv11 segmentation models and ArUco marker detection to accurately measure a box's width, height, and length, then instantly produces an RSC (Regular Slotted Container) dieline in SVG format.

## Features

- **Dual-Camera Detection** — Two camera feeds processed simultaneously; Camera 1 captures the top-down view and Camera 2 captures the side profile.
- **Automatic Dieline Generation** — Measured dimensions are used to auto-generate a flat RSC carton dieline with proper clearance, ready for die-cutting and folding.
- **Tkinter GUI** — A clean side-by-side dual-camera interface with Capture and Generate Dieline controls. Dieline generation opens the Tkinter-based generator with the captured dimensions prefilled.


## Tech Stack

- Python
- Tkinter (GUI)
- OpenCV (camera capture)
- PyTorch
- SVGWrite (SVG export)

## How It Works

1. Place an object in view of both cameras with an ArUco reference marker visible.
2. Click **Capture Measurements** in the GUI to run detection and extract measurements.
3. Click **Generate Dieline** to produce and preview the SVG flat-pattern dieline based on the measured dimensions.
