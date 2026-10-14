import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import svgwrite


ALLOWANCE_MM = 10.0


class DielineGeneratorApp:
    def __init__(self, root, initial_length=None, initial_width=None, initial_height=None):
        self.root = root
        self.root.title("Carton Dieline Pattern Generator")
        self.root.geometry("1100x700")
        self.root.configure(bg="#f4f5f7")
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background="#f4f5f7")
        self.style.configure('TLabel', background="#f4f5f7", font=("Segoe UI", 10))
        self.style.configure('Header.TLabel', font=("Segoe UI", 14, "bold"))
        self.style.configure('TButton', font=("Segoe UI", 10), padding=6)
        self.style.configure('TEntry', padding=5)

        # Main layout panels
        self.left_panel = ttk.Frame(self.root, padding="20 20 20 20", width=300)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        self.right_panel = ttk.Frame(self.root, padding="20 20 20 20")
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # store initial measurements so setup_ui can access them
        self.initial_length = initial_length
        self.initial_width = initial_width
        self.initial_height = initial_height

        self.current_scale = None  # Holds steady zoom level
        self.setup_ui()
        self.update_preview()

    @staticmethod
    def _format_dimension_value(value):
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    def setup_ui(self):
        # --- Left Panel: Inputs ---
        ttk.Label(self.left_panel, text="Custom Size (mm)", style='Header.TLabel').pack(anchor=tk.W, pady=(0, 20))

        # Variables set to match the user's reference image (overridable)
        self.var_length = tk.StringVar(value=self._format_dimension_value(self.initial_length) if self.initial_length is not None else "238.00")
        self.var_width = tk.StringVar(value=self._format_dimension_value(self.initial_width) if self.initial_width is not None else "180.00")
        self.var_height = tk.StringVar(value=self._format_dimension_value(self.initial_height) if self.initial_height is not None else "80.00")
        # Trace variables for real-time dynamic updates
        self._updating_dimensions = False
        self.base_dimensions = None
        self.var_length.trace_add("write", lambda *args: self._dimensions_changed())
        self.var_width.trace_add("write", lambda *args: self._dimensions_changed())
        self.var_height.trace_add("write", lambda *args: self._dimensions_changed())

        self.create_input_row("Length (L):", self.var_length)
        self.create_input_row("Width (W):", self.var_width)
        self.create_input_row("Height (H):", self.var_height)

        self.allowance_mode = tk.StringVar(value="with")
        self._previous_allowance_mode = "with"
        self.allowance_mode.trace_add("write", lambda *args: self._allowance_changed())
        allowance_frame = ttk.Frame(self.left_panel)
        allowance_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(allowance_frame, text="Allowance:").pack(anchor=tk.W)
        ttk.Radiobutton(
            allowance_frame,
            text="Without allowance",
            variable=self.allowance_mode,
            value="before",
        ).pack(anchor=tk.W, pady=(4, 0))
        ttk.Radiobutton(
            allowance_frame,
            text="With allowance",
            variable=self.allowance_mode,
            value="with",
        ).pack(anchor=tk.W)

        self.base_dimensions = self.get_dimensions()
        self._set_display_dimensions(self.base_dimensions, with_allowance=True)
        

        # Save Button
        self.save_svg_button = ttk.Button(self.left_panel, text="Save as SVG", command=self.save_svg)
        self._update_save_button_visibility()

        # --- Right Panel: Preview Canvas ---
        ttk.Label(self.right_panel, text="Layout Preview", style='Header.TLabel').pack(anchor=tk.W, pady=(0, 10))
        
        self.canvas = tk.Canvas(self.right_panel, bg="#ffffff", highlightthickness=1, highlightbackground="#d1d5db")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Configure>", lambda e: self.update_preview(window_resize=True))

    def create_input_row(self, label_text, variable):
        frame = ttk.Frame(self.left_panel)
        frame.pack(fill=tk.X, pady=5)
        ttk.Label(frame, text=label_text, width=12).pack(side=tk.LEFT)
        entry = ttk.Entry(frame, textvariable=variable, width=10, state="readonly")
        entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)

    def get_dimensions(self):
        try:
            L = float(self.var_length.get() or 0)
            W = float(self.var_width.get() or 0)
            H = float(self.var_height.get() or 0)
            if L <= 0 or W <= 0 or H <= 0: return None
            return L, W, H
        except ValueError:
            return None

    def reset_scale(self):
        self.current_scale = None
        self.update_preview()

    def _set_display_dimensions(self, dimensions, with_allowance):
        if dimensions is None:
            return
        amount = ALLOWANCE_MM if with_allowance else 0
        self._updating_dimensions = True
        try:
            self.var_length.set(self._format_dimension_value(dimensions[0] + amount))
            self.var_width.set(self._format_dimension_value(dimensions[1] + amount))
            self.var_height.set(self._format_dimension_value(dimensions[2] + amount))
        finally:
            self._updating_dimensions = False

    def _dimensions_changed(self):
        if self._updating_dimensions:
            return
        dimensions = self.get_dimensions()
        if dimensions is not None:
            amount = ALLOWANCE_MM if self.allowance_mode.get() == "with" else 0
            self.base_dimensions = tuple(value - amount for value in dimensions)
            self._updating_dimensions = True
            try:
                self.var_length.set(self._format_dimension_value(dimensions[0]))
                self.var_width.set(self._format_dimension_value(dimensions[1]))
                self.var_height.set(self._format_dimension_value(dimensions[2]))
            finally:
                self._updating_dimensions = False
        self.update_preview()

    def _update_save_button_visibility(self):
        if self.allowance_mode.get() == "with":
            self.save_svg_button.pack(fill=tk.X, pady=(10, 5))
        else:
            self.save_svg_button.pack_forget()

    def _allowance_changed(self):
        self._update_save_button_visibility()
        dimensions = self.get_dimensions()
        if dimensions is not None:
            previous_amount = ALLOWANCE_MM if self._previous_allowance_mode == "with" else 0
            self.base_dimensions = tuple(value - previous_amount for value in dimensions)
            self._set_display_dimensions(
                self.base_dimensions,
                with_allowance=self.allowance_mode.get() == "with",
            )
        self._previous_allowance_mode = self.allowance_mode.get()
        self.current_scale = None
        self.update_preview()

    def generate_paths(self, L, W, H, with_allowance=None):
        """Generates the exact mathematical line segments for cuts and creases"""
        if with_allowance is None:
            with_allowance = self.allowance_mode.get() == "with"
        if with_allowance:
            L += ALLOWANCE_MM
            W += ALLOWANCE_MM
            H += ALLOWANCE_MM

        S = 3  # Slot width (gap between flaps) in mm
        taper = 5  # Glue flap taper in mm
        # No user-configurable glue flap width — use zero inset
        G = 0

        x1 = G
        x2 = G + L
        x3 = G + L + W
        x4 = G + L + W + L
        x5 = G + L + W + L + W

        FH = W / 2 # Flap height
        y0 = 0
        y1 = FH
        y2 = FH + H
        y3 = FH * 2 + H

        cuts = []     # Solid Black lines
        creases = []  # Dashed Red lines

        # --- CUTS (Outer Boundaries & Slots) ---
        # Glue flap
        cuts.extend([(x1, y1, 0, y1 + taper), (0, y1 + taper, 0, y2 - taper), (0, y2 - taper, x1, y2)])
        
        # Top boundary left-to-right (incorporating slots)
        cuts.extend([
            (x1, y1, x1, y0), (x1, y0, x2 - S/2, y0),                        
            (x2 - S/2, y0, x2 - S/2, y1), (x2 - S/2, y1, x2 + S/2, y1), (x2 + S/2, y1, x2 + S/2, y0), 
            (x2 + S/2, y0, x3 - S/2, y0),                                    
            (x3 - S/2, y0, x3 - S/2, y1), (x3 - S/2, y1, x3 + S/2, y1), (x3 + S/2, y1, x3 + S/2, y0), 
            (x3 + S/2, y0, x4 - S/2, y0),                                    
            (x4 - S/2, y0, x4 - S/2, y1), (x4 - S/2, y1, x4 + S/2, y1), (x4 + S/2, y1, x4 + S/2, y0), 
            (x4 + S/2, y0, x5, y0), (x5, y0, x5, y1)                         
        ])

        # Rightmost body edge
        cuts.append((x5, y1, x5, y2))

        # Bottom boundary right-to-left (incorporating slots)
        cuts.extend([
            (x5, y2, x5, y3), (x5, y3, x4 + S/2, y3),                        
            (x4 + S/2, y3, x4 + S/2, y2), (x4 + S/2, y2, x4 - S/2, y2), (x4 - S/2, y2, x4 - S/2, y3), 
            (x4 - S/2, y3, x3 + S/2, y3),                                    
            (x3 + S/2, y3, x3 + S/2, y2), (x3 + S/2, y2, x3 - S/2, y2), (x3 - S/2, y2, x3 - S/2, y3), 
            (x3 - S/2, y3, x2 + S/2, y3),                                    
            (x2 + S/2, y3, x2 + S/2, y2), (x2 + S/2, y2, x2 - S/2, y2), (x2 - S/2, y2, x2 - S/2, y3), 
            (x2 - S/2, y3, x1, y3), (x1, y3, x1, y2)                         
        ])

        # --- CREASES (Inner Folds) ---
        # Horizontal top and bottom body creases
        creases.extend([
            (x1, y1, x2 - S/2, y1), (x2 + S/2, y1, x3 - S/2, y1), (x3 + S/2, y1, x4 - S/2, y1), (x4 + S/2, y1, x5, y1), 
            (x1, y2, x2 - S/2, y2), (x2 + S/2, y2, x3 - S/2, y2), (x3 + S/2, y2, x4 - S/2, y2), (x4 + S/2, y2, x5, y2)  
        ])
        
        # Vertical creases; x1 is the outer glue-flap cut, not an interior fold.
        creases.extend([(x2, y1, x2, y2), (x3, y1, x3, y2), (x4, y1, x4, y2)])

        return cuts, creases, x5, y3 

    def update_preview(self, window_resize=False):
        self.canvas.delete("all")
        dims = self.get_dimensions()
        if not dims: return
        L, W, H = dims
        
        c_width = self.canvas.winfo_width()
        c_height = self.canvas.winfo_height()
        if c_width <= 1 or c_height <= 1: return

        cuts, creases, total_width, total_height = self.generate_paths(L, W, H, with_allowance=False)

        # --- Dynamic Scaling Logic ---
        padding = 40
        label_space = 64  # Preview-only dimension labels below the layout.
        available_w = max(1, c_width - padding * 2)
        available_h = max(1, c_height - padding * 2 - label_space)
        fit_scale = min(available_w / total_width, available_h / total_height)

        if self.current_scale is None or window_resize:
            self.current_scale = fit_scale
        else:
            if (total_width * self.current_scale > available_w) or (total_height * self.current_scale > available_h):
                self.current_scale = fit_scale
            elif (total_width * self.current_scale < available_w * 0.4) and (total_height * self.current_scale < available_h * 0.4):
                self.current_scale = fit_scale

        scale = self.current_scale
        offset_x = (c_width - (total_width * scale)) / 2
        offset_y = (c_height - label_space - (total_height * scale)) / 2

        def render_line(x1, y1, x2, y2, is_cut):
            sx1, sy1 = offset_x + (x1 * scale), offset_y + (y1 * scale)
            sx2, sy2 = offset_x + (x2 * scale), offset_y + (y2 * scale)
            
            # STYLING UPDATE: Thicker lines and longer dash patterns
            color = "black" if is_cut else "#ef4444"
            dash = None if is_cut else (12, 8)  # 12px line, 8px gap for a proper dashed look
            line_width = 2 if is_cut else 3     # Thicker crease lines for the UI
            
            self.canvas.create_line(sx1, sy1, sx2, sy2, fill=color, dash=dash, width=line_width)

        # Draw to canvas
        for x1, y1, x2, y2 in cuts:
            render_line(x1, y1, x2, y2, is_cut=True)
        for x1, y1, x2, y2 in creases:
            render_line(x1, y1, x2, y2, is_cut=False)

        self._draw_preview_dimensions(L, W, H, scale, offset_x, offset_y)

    def _draw_preview_dimensions(self, L, W, H, scale, offset_x, offset_y):
        """Draw dimension arrows on the canvas only; SVG exports use paths only."""
        top = offset_y + (W / 2) * scale
        bottom = top + H * scale
        layout_bottom = offset_y + (W + H) * scale
        label_y = layout_bottom + 36
        inset = min(12, H * scale / 4)
        color = "#1f2937"
        arrow_style = dict(
            fill=color, width=5, arrow=tk.BOTH,
            arrowshape=(12, 15, 6), tags="dimensions",
        )

        # Length across the first body panel, width across the second.
        for start, end, arrow_y, name, value in (
            (0, L, top + inset, "L", L),
            (L, L + W, bottom - inset, "W", W),
        ):
            left = offset_x + start * scale
            right = offset_x + end * scale
            center = (left + right) / 2
            self.canvas.create_line(left, arrow_y, right, arrow_y, **arrow_style)
            self.canvas.create_line(
                center, arrow_y + 6, center, label_y - 14,
                fill=color, dash=(5, 5), tags="dimensions",
            )
            self.canvas.create_text(
                center, label_y, text=f"{name}: {value:.2f} mm",
                fill=color, font=("Segoe UI", 11, "bold"), tags="dimensions",
            )

        # Height between the body folds in the last panel.
        center = offset_x + (2 * L + 1.5 * W) * scale
        self.canvas.create_line(center, top, center, bottom, **arrow_style)
        self.canvas.create_line(
            center, bottom + 6, center, label_y - 14,
            fill=color, dash=(5, 5), tags="dimensions",
        )
        self.canvas.create_text(
            center, label_y, text=f"H: {H:.2f} mm",
            fill=color, font=("Segoe UI", 11, "bold"), tags="dimensions",
        )

    def save_svg(self):
        if self.allowance_mode.get() != "with":
            return
        dims = self.get_dimensions()
        if not dims: 
            messagebox.showwarning("Warning", "Invalid dimensions.")
            return
        L, W, H = dims

        file_path = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg")],
            title="Save Dieline as SVG"
        )
        if not file_path: return

        cuts, creases, total_w, total_h = self.generate_paths(L, W, H, with_allowance=False)
        
        dwg = svgwrite.Drawing(file_path, size=(f"{total_w}mm", f"{total_h}mm"), viewBox=f"0 0 {total_w} {total_h}")

        # STYLING UPDATE: Thicker lines and longer dash arrays in the exported SVG
        cut_style = {"stroke": "black", "stroke_width": 1.5, "fill": "none"}
        crease_style = {"stroke": "red", "stroke_width": 2.5, "fill": "none", "stroke_dasharray": "12,8"}

        for x1, y1, x2, y2 in cuts:
            dwg.add(dwg.line((x1, y1), (x2, y2), **cut_style))
        for x1, y1, x2, y2 in creases:
            dwg.add(dwg.line((x1, y1), (x2, y2), **crease_style))

        dwg.save()
        # Print the physical dieline size (width x height in mm) to stdout
        print(f"Generated dieline size: {total_w:.2f}mm x {total_h:.2f}mm")
        # Also include size in the success dialog for quick confirmation
        messagebox.showinfo("Success", f"Dieline saved successfully to:\n{file_path}\n\nSize: {total_w:.2f}mm x {total_h:.2f}mm")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Open Dieline generator GUI with optional initial measurements (mm).')
    parser.add_argument('--length', type=float, help='Initial length in mm')
    parser.add_argument('--width', type=float, help='Initial width in mm')
    parser.add_argument('--height', type=float, help='Initial height in mm')
    args = parser.parse_args()

    root = tk.Tk()
    app = DielineGeneratorApp(
        root,
        initial_length=args.length,
        initial_width=args.width,
        initial_height=args.height,
    )
    root.mainloop()