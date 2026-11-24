import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from dwg_merger.pipeline import ConverterNotFoundError, merge_folder


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DWG Sheet Merger")
        self.geometry("560x420")
        self.resizable(False, False)

        self.input_folder = tk.StringVar()
        self.output_file = tk.StringVar()
        self.queue = queue.Queue()

        pad = {"padx": 12, "pady": 6}

        tk.Label(self, text="Folder with source DWGs:").grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.input_folder, width=52).grid(row=1, column=0, **pad)
        tk.Button(self, text="Browse...", command=self.pick_input_folder).grid(row=1, column=1, **pad)

        tk.Label(self, text="Save merged DWG as:").grid(row=2, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.output_file, width=52).grid(row=3, column=0, **pad)
        tk.Button(self, text="Browse...", command=self.pick_output_file).grid(row=3, column=1, **pad)

        self.run_button = tk.Button(self, text="Merge", command=self.start_merge, width=20)
        self.run_button.grid(row=4, column=0, columnspan=2, pady=14)

        self.progress = ttk.Progressbar(self, length=520, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=2, padx=12)

        self.log = tk.Text(self, width=68, height=13, state="disabled")
        self.log.grid(row=6, column=0, columnspan=2, padx=12, pady=10)

        self.after(150, self.poll_queue)

    def pick_input_folder(self):
        folder = filedialog.askdirectory(title="Select folder with source DWGs")
        if folder:
            self.input_folder.set(folder)

    def pick_output_file(self):
        path = filedialog.asksaveasfilename(
            title="Save merged DWG as",
            defaultextension=".dwg",
            filetypes=[("DWG files", "*.dwg")],
        )
        if path:
            self.output_file.set(path)

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_merge(self):
        input_folder = self.input_folder.get().strip()
        output_file = self.output_file.get().strip()
        if not input_folder or not output_file:
            messagebox.showwarning("Missing info", "Pick both a source folder and an output file.")
            return

        self.run_button.configure(state="disabled")
        self.progress["value"] = 0
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        thread = threading.Thread(
            target=self.run_merge, args=(input_folder, output_file), daemon=True
        )
        thread.start()

    def run_merge(self, input_folder, output_file):
        def progress_callback(index, total, filename):
            self.queue.put(("progress", index, total, filename))

        try:
            merge_folder(input_folder, output_file, progress_callback=progress_callback)
            self.queue.put(("done", output_file))
        except ConverterNotFoundError as e:
            self.queue.put(("error", str(e)))
        except FileNotFoundError as e:
            self.queue.put(("error", str(e)))
        except Exception as e:
            self.queue.put(("error", f"Unexpected error: {e}"))

    def poll_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, index, total, filename = item
                    self.progress["maximum"] = total
                    self.progress["value"] = index
                    self.write_log(f"[{index}/{total}] {filename}")
                elif kind == "done":
                    self.write_log(f"Done. Saved to {item[1]}")
                    self.run_button.configure(state="normal")
                    messagebox.showinfo("Merge complete", f"Saved to:\n{item[1]}")
                elif kind == "error":
                    self.write_log(f"Error: {item[1]}")
                    self.run_button.configure(state="normal")
                    messagebox.showerror("Merge failed", item[1])
        except queue.Empty:
            pass
        self.after(150, self.poll_queue)


if __name__ == "__main__":
    App().mainloop()
