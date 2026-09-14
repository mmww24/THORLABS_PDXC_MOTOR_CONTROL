"""Simulator-only Tk smoke test; never constructs LiveBackend."""
import tkinter as tk, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pdxc_gui import SimBackend, build_app

def walk(w):
    out=[]
    for c in w.winfo_children(): out.append(c); out += walk(c)
    return out

root=build_app(SimBackend()); root.deiconify(); root.update_idletasks()
assert root.winfo_ismapped()
widgets=walk(root); assert all(w.winfo_width()>=0 and w.winfo_height()>=0 for w in widgets)
geometry=root.winfo_geometry()
buttons=[w for w in widgets if w.winfo_class()=='TButton']
assert {b.cget('text') for b in buttons} >= {'Play','Pause/Resume','Cancel','Home'}
[b for b in buttons if b.cget('text')=='Play'][0].invoke(); root.update(); root.after(100,[b for b in buttons if b.cget('text')=='Pause/Resume'][0].invoke); root.after(250,root.destroy); root.after(500,root.quit); root.mainloop()
print('simulate_gui_smoke=ok',len(widgets),geometry)
