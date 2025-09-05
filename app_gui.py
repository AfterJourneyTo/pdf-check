# app_gui.py
import tkinter as tk
from tkinter import filedialog, messagebox
from keep_first_pages import keep_first_pages_auto

def run():
    in_path = filedialog.askopenfilename(title="选择合并后的报账单PDF", filetypes=[("PDF files","*.pdf")])
    if not in_path: return
    out_path = filedialog.asksaveasfilename(title="保存仅首页PDF为", defaultextension=".pdf",
                                            filetypes=[("PDF files","*.pdf")])
    if not out_path: return
    try:
        count, idxs = keep_first_pages_auto(
            input_pdf=in_path, output_pdf=out_path,
            allowed_gaps=range(2, 21), min_gap=1, top_ratio=0.35
        )
        messagebox.showinfo("完成", f"输出：{out_path}\n保留 {count} 页\n首页索引：{idxs}")
    except Exception as e:
        messagebox.showerror("失败", str(e))

if __name__ == "__main__":
    root = tk.Tk(); root.withdraw()
    run()
