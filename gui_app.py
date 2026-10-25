import sys
import torch
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
import cv2
import numpy as np

from gen_cartondieline import DielineGeneratorApp
from object_detector import ObjectDetector
from segmentation_measurement import SegmentationMeasurement

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
# Fixed calibration measured at a camera distance of 30.0 cm.
REFERENCE_LENGTH_MM = 130.81
REFERENCE_DISTANCE_PX = 256.01
MM_PER_PIXEL = REFERENCE_LENGTH_MM / REFERENCE_DISTANCE_PX
DETECTION_CONFIDENCE = 0.50
MEASUREMENT_SAMPLE_COUNT = 7
BLOCKING_CLASSES = {'Not allowed', 'Undersize', 'Oversize'}


def resource_path(filename: str) -> Path:
    """Return the path to a bundled resource in source or PyInstaller mode."""
    if getattr(sys, 'frozen', False):
        bundle_dir = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    else:
        bundle_dir = Path(__file__).resolve().parent
    return bundle_dir / filename


def cv2_to_photoimage(frame: np.ndarray) -> tk.PhotoImage:
    """Convert an OpenCV BGR frame to a Tkinter PhotoImage."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    ppm_header = f'P6\n{width} {height}\n255\n'.encode('ascii')
    return tk.PhotoImage(data=ppm_header + rgb.tobytes(), format='PPM')


class DualCameraApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Cartoon')
        self.root.geometry('1000x650')
        self.root.minsize(860, 560)
        self.root.configure(bg='#f4f6f8')

        self.cap1 = None
        self.cap2 = None
        self.detector1 = None
        self.detector2 = None
        self.segmentation_measurement = SegmentationMeasurement(
            resource_path('camera1_segmodel.pt'),
            resource_path('camera2_segmodel.pt'),
            conf_threshold=DETECTION_CONFIDENCE,
        )
        self.photo1 = None
        self.photo2 = None
        self.measurements_window = None
        self.warning_window = None
        self.warning_message = None
        self.warning_shown = False

        self.width = None
        self.height = None
        self.length = None
        self.blocking_detection_active = False

        self._configure_styles()
        self._setup_ui()
        self._init_cameras()
        self._init_detectors()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self._update_frames()

    def _configure_styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('App.TFrame', background='#f4f6f8')
        style.configure('Title.TLabel', background='#f4f6f8', foreground='#18212f',
                        font=('Segoe UI', 20, 'bold'))
        style.configure('CameraTitle.TLabel', background='#ffffff', foreground='#263445',
                        font=('Segoe UI', 13, 'bold'))
        style.configure('Status.TLabel', background='#f4f6f8', foreground='#64748b',
                        font=('Segoe UI', 10))
        style.configure('Measurement.TFrame', background='#ffffff')
        style.configure('MeasurementTitle.TLabel', background='#ffffff', foreground='#18212f',
                font=('Segoe UI', 16, 'bold'))
        style.configure('Measurement.TLabel', background='#ffffff', foreground='#263445',
                font=('Segoe UI', 12))
        style.configure('Primary.TButton', font=('Segoe UI', 11, 'bold'), padding=(22, 12))
        style.configure('Secondary.TButton', font=('Segoe UI', 11, 'bold'), padding=(22, 12))

    def _setup_ui(self):
        outer = ttk.Frame(self.root, style='App.TFrame', padding=18)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        ttk.Label(outer, text='Cartoon', style='Title.TLabel').grid(
            row=0, column=0, pady=(0, 4)
        )
        ttk.Label(outer, text='Position the product at the bottom left corner',
                  style='Status.TLabel').grid(row=1, column=0, pady=(0, 14))

        camera_row = ttk.Frame(outer, style='App.TFrame')
        camera_row.grid(row=2, column=0, sticky='nsew')
        camera_row.columnconfigure(0, weight=1)
        camera_row.columnconfigure(1, weight=1)
        camera_row.rowconfigure(0, weight=1)

        self.camera1_view = self._create_camera_panel(camera_row, 'Camera 1', 'Length', 0)
        self.camera2_view = self._create_camera_panel(camera_row, 'Camera 2', 'Width & Height', 1)

        controls = ttk.Frame(outer, style='App.TFrame')
        controls.grid(row=3, column=0, pady=(18, 10))

        self.capture_btn = ttk.Button(
            controls, text='Capture Measurements', style='Primary.TButton',
            command=self.capture_measurements
        )
        self.capture_btn.grid(row=0, column=0, padx=8)

        self.generate_btn = ttk.Button(
            controls, text='Generate Dieline', style='Secondary.TButton',
            command=self.generate_dieline, state=tk.DISABLED
        )
        self.generate_btn.grid(row=0, column=1, padx=8)

        self.status_label = ttk.Label(
            outer, text='Ready - position the object 30.0 cm from both cameras, then capture',
            style='Status.TLabel', anchor=tk.CENTER
        )
        # Repaint the full row when a shorter status replaces the ready message.
        self.status_label.grid(row=4, column=0, sticky='ew', pady=(0, 2))

    def _create_camera_panel(self, parent, camera_name, measurement_name, column):
        panel = tk.Frame(parent, bg='#ffffff', highlightthickness=1,
                         highlightbackground='#d7dee7')
        panel.grid(row=0, column=column, sticky='nsew', padx=7)
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        ttk.Label(panel, text=f'{camera_name} - {measurement_name}',
                  style='CameraTitle.TLabel', anchor=tk.CENTER).grid(
                      row=0, column=0, sticky='ew', pady=(10, 8)
                  )

        view = tk.Label(panel, text=f'{camera_name}\nWaiting for camera...',
                        bg='#202936', fg='#d7dee7', font=('Segoe UI', 12), relief=tk.FLAT)
        view.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))
        return view

    def _init_cameras(self):
        profiles = [(cv2.CAP_ANY, False, 'automatic')]
        if sys.platform == 'win32':
            profiles += [
                (cv2.CAP_DSHOW, True, 'DirectShow / MJPEG / 15 FPS'),
                (cv2.CAP_DSHOW, False, 'DirectShow / default format'),
            ]

        for attempt, (backend, use_mjpeg, label) in enumerate(profiles):
            print(f'Trying both cameras: {label}')
            self.cap1 = self._open_camera(0, backend, use_mjpeg)
            self.cap2 = self._open_camera(1, backend, use_mjpeg)
            ready = [False, False]
            # Opening a device does not guarantee that it can deliver frames.
            for _ in range(3):
                for index, camera in enumerate((self.cap1, self.cap2)):
                    if camera.isOpened():
                        received, frame = camera.read()
                        ready[index] = bool(received and frame is not None and frame.size)
            for index, received in enumerate(ready):
                print(f'Camera {index + 1}: {"frames received" if received else "no frames received"}')
            if all(ready):
                return
            if attempt < len(profiles) - 1:
                # Release BOTH devices before trying another capture backend.
                self.cap1.release()
                self.cap2.release()

        print('Camera startup failed: check camera ownership, USB ports, and supported formats.')

    @staticmethod
    def _open_camera(index, backend=cv2.CAP_ANY, use_mjpeg=False):
        camera = cv2.VideoCapture(index, backend)
        if use_mjpeg:
            camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        if use_mjpeg:
            camera.set(cv2.CAP_PROP_FPS, 15)
        if camera.isOpened():
            print(f'Camera {index + 1}: opened device {index} using {camera.getBackendName()}')
        else:
            print(f'Camera {index + 1}: could not open device {index}')
        return camera

    def _init_detectors(self):
        self.detector1 = self._load_detector(resource_path('camera1_detectmodel.pt'))
        self.detector2 = self._load_detector(resource_path('camera2_detectmodel.pt'))

    @staticmethod
    def _load_detector(model_path):
        try:
            model_path = Path(model_path)
            if not model_path.is_file():
                print(f'Error: Model file not found at {model_path}')
                return None

            detector = ObjectDetector(
                model_path=str(model_path),
                conf_threshold=DETECTION_CONFIDENCE
            )
            return detector if detector.load_model() else None
        except Exception as exc:
            print(f'Error loading {model_path}: {exc}')
            return None

    def _update_frames(self):
        blocking_detection_classes = self._process_camera_frame(
            self.cap1, self.detector1, self.camera1_view, 1
        )
        blocking_detection_classes |= self._process_camera_frame(
            self.cap2, self.detector2, self.camera2_view, 2
        )
        self._update_safety_state(blocking_detection_classes)
        self.root.after(30, self._update_frames)

    def _process_camera_frame(self, camera, detector, view, camera_number):
        if camera is None or not camera.isOpened():
            view.configure(text=f'Camera {camera_number}\nUnavailable', image='')
            return set()

        received, frame = camera.read()
        if not received:
            view.configure(text=f'Camera {camera_number}\nNo frame received', image='')
            return set()

        blocking_detection_classes = set()
        if detector is not None:
            frame, detections = detector.detect(frame, draw_boxes=True)
            blocking_detection_classes = {
                detection['class_name']
                for detection in detections
                if detection['class_name'] in BLOCKING_CLASSES
            }

        photo = cv2_to_photoimage(frame)
        view.configure(image=photo, text='')
        if camera_number == 1:
            self.photo1 = photo
        else:
            self.photo2 = photo
        return blocking_detection_classes

    def _update_safety_state(self, blocking_detection_classes):
        blocking_detection_active = bool(blocking_detection_classes)
        if blocking_detection_active:
            self.capture_btn.configure(state=tk.DISABLED)
            self.generate_btn.configure(state=tk.DISABLED)
            self.status_label.configure(
                text='Capture and Generate Dieline is disabled due to not allowed, undersize, or oversize object',
                foreground='#c62828'
            )

            warning_class = (
                'Not allowed' if 'Not allowed' in blocking_detection_classes else
                'Undersize' if 'Undersize' in blocking_detection_classes else
                'Oversize'
            )
            warning_message = f'WARNING: {warning_class} object'
            if not self.warning_shown or warning_message != self.warning_message:
                self._show_warning_popup(warning_message)
                self.warning_message = warning_message
                self.warning_shown = True
        else:
            self.capture_btn.configure(state=tk.NORMAL)
            self.generate_btn.configure(
                state=tk.NORMAL if self._has_measurements() else tk.DISABLED
            )
            self.status_label.configure(
                text='Ready - position the object 30.0 cm from both cameras, then capture',
                foreground='#64748b'
            )
            if self.warning_window is not None and self.warning_window.winfo_exists():
                self.warning_window.destroy()
            self.warning_window = None
            self.warning_message = None
            self.warning_shown = False
        self.blocking_detection_active = blocking_detection_active

    def _show_warning_popup(self, warning_message):
        if self.warning_window is not None and self.warning_window.winfo_exists():
            self.warning_window.destroy()

        window = tk.Toplevel(self.root)
        self.warning_window = window
        window.title('Warning')
        window.resizable(False, False)
        window.transient(self.root)
        window.configure(bg='#fff4f4')

        content = tk.Frame(window, bg='#fff4f4', padx=18, pady=14)
        content.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            content, text=warning_message, bg='#fff4f4', fg='#c62828',
            font=('Segoe UI', 13, 'bold')
        ).pack()

        window.update_idletasks()
        window_width = window.winfo_reqwidth()
        window_height = window.winfo_reqheight()
        position_x = (window.winfo_screenwidth() - window_width) // 2
        position_y = (window.winfo_screenheight() - window_height) // 2
        window.geometry(f'{window_width}x{window_height}+{position_x}+{position_y}')

    def _has_measurements(self):
        return all(value is not None for value in (self.width, self.height, self.length))

    def capture_measurements(self):
        if self.blocking_detection_active:
            return
        if self.cap1 is None or not self.cap1.isOpened():
            messagebox.showwarning('Camera unavailable', 'Camera 1 is not available', parent=self.root)
            return
        if self.cap2 is None or not self.cap2.isOpened():
            messagebox.showwarning('Camera unavailable', 'Camera 2 is not available', parent=self.root)
            return

        if self.detector1 is None or self.detector2 is None:
            messagebox.showwarning('Detector unavailable', 'One or more object detectors could not be loaded.', parent=self.root)
            return

        measurements = []
        self.capture_btn.configure(state=tk.DISABLED)
        self.status_label.configure(text='Running measurements...')
        self.root.update_idletasks()
        try:
            self.segmentation_measurement.load_models()
            for _ in range(MEASUREMENT_SAMPLE_COUNT):
                ret1, frame1 = self.cap1.read()
                ret2, frame2 = self.cap2.read()
                if not ret1 or not ret2 or frame1 is None or frame2 is None:
                    continue

                _, detections1 = self.detector1.detect(frame1, draw_boxes=False)
                _, detections2 = self.detector2.detect(frame2, draw_boxes=False)
                blocking_classes = {
                    detection['class_name']
                    for detection in detections1 + detections2
                    if detection['class_name'] in BLOCKING_CLASSES
                }
                if blocking_classes:
                    self._update_safety_state(blocking_classes)
                    return

                sample = self.segmentation_measurement.measure(
                    frame1, frame2, MM_PER_PIXEL
                )
                if sample is not None:
                    measurements.append(sample)
        except Exception as exc:
            self.status_label.configure(text='Segmentation measurement failed', foreground='#c62828')
            messagebox.showerror('Capture failed', str(exc), parent=self.root)
            return
        finally:
            if not self.blocking_detection_active:
                self.capture_btn.configure(state=tk.NORMAL)

        if not measurements:
            self.status_label.configure(text='No valid segmentation measurements', foreground='#c62828')
            messagebox.showwarning(
                'Capture failed',
                'Could not collect a valid measurement sample. Keep the object visible in both cameras at a distance of 30.0 cm.',
                parent=self.root,
            )
            return

        median_measurement = np.median(np.asarray(measurements), axis=0)
        self.length, self.width, self.height = median_measurement.tolist()

        self._show_measurements_popup()
        self.status_label.configure(text='Measurements captured successfully', foreground='#176b3a')
        self.generate_btn.configure(state=tk.NORMAL)

    def _show_measurements_popup(self):
        if self.measurements_window is not None and self.measurements_window.winfo_exists():
            self.measurements_window.destroy()

        window = tk.Toplevel(self.root)
        self.measurements_window = window
        window.title('Generated Measurements')
        window.geometry('400x280')
        window.resizable(False, False)
        window.transient(self.root)
        window.configure(bg='#ffffff')

        content = ttk.Frame(window, style='Measurement.TFrame', padding=28)
        content.pack(fill=tk.BOTH, expand=True)
        ttk.Label(content, text='Generated Measurements', style='MeasurementTitle.TLabel').pack(pady=(0, 20))
        ttk.Label(content, text=f'Length:  {self.length:.2f} mm', style='Measurement.TLabel').pack(anchor=tk.W, pady=4)
        ttk.Label(content, text=f'Width:   {self.width:.2f} mm', style='Measurement.TLabel').pack(anchor=tk.W, pady=4)
        ttk.Label(content, text=f'Height:  {self.height:.2f} mm', style='Measurement.TLabel').pack(anchor=tk.W, pady=4)
        ttk.Button(content, text='Close', command=window.destroy).pack(pady=(22, 0))

    def generate_dieline(self):
        if not self._has_measurements():
            messagebox.showwarning('Missing measurements', 'Please capture measurements first.', parent=self.root)
            return

        generator_window = tk.Toplevel(self.root)
        DielineGeneratorApp(
            generator_window,
            initial_length=self.length,
            initial_width=self.width,
            initial_height=self.height,
        )

    def close(self):
        if self.cap1 is not None:
            self.cap1.release()
        if self.cap2 is not None:
            self.cap2.release()
        self.root.destroy()


def main():
    root = tk.Tk()
    DualCameraApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
