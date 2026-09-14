"""Small cross-platform Tk GUI for a PDXC serial backend.

The GUI depends only on tkinter.  A backend is injected for tests or
``--simulate``; real serial discovery/control is deliberately delegated to a
backend implementing the documented methods.
"""
from __future__ import annotations
import argparse, queue, threading, time
from dataclasses import dataclass

@dataclass
class GuiConfig:
    a: float = 0.0; b: float = 120.0; speed: float = 20.0; repeats: int = 1
    bidirectional: bool = True

class SimBackend:
    def __init__(self): self.pos=0.0; self.disabled_state=1; self.moves=[]
    def list_ports(self): return ["SIMULATED"]
    def open(self, port): self.disabled_state=0
    def close(self): self.disabled_state=1
    def disable(self): self.disabled_state=1
    def enable(self): self.disabled_state=0
    def is_disabled(self): return self.disabled_state == 1
    def status(self): return {"model":"PDXR1","position":self.pos,"speed":20,"state":"ready"}
    def move(self, target, speed, cancel):
        if cancel.is_set(): return False
        self.moves.append(target); self.pos=target; return True
    def home(self, cancel): return not cancel.is_set()

class LiveBackend:
    """Adapter around PDXCSerial; connect/query is read-only until Play."""
    def __init__(self, port):
        from pdxc_serial import PDXCSerial, SerialConfig
        self.io=PDXCSerial(SerialConfig(port)); self.port=port
    def list_ports(self):
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    def open(self, port=None):
        if port: self.io.config.port=port
        self.io.open()
    def close(self): self.io.close()
    def enable(self): self.io.set_disabled(0)
    def disable(self): self.io.set_disabled(1)
    def is_disabled(self): return self.io.get_disabled() == 1
    def status(self): return {"model":self.io.get_stage(),"position":self.io.get_position(),"speed":None,"state":self.io.get_status()}
    def move(self,target,speed,cancel):
        if cancel.is_set(): return False
        self.io.set_speed(speed); self.io.set_position(target); return True
    def position(self): return self.io.get_position()
    def error(self): return self.io.get_error()
    def home(self,cancel):
        self.io.home()
        while not cancel.is_set():
            if self.io.get_error()!=0: return False
            if self.io.get_calibration().upper().startswith("YES"): return True
            time.sleep(.5)
        return False

class SweepWorker:
    def __init__(self, backend, emit): self.backend=backend; self.emit=emit; self.cancel=threading.Event(); self.pause=threading.Event(); self.commands=queue.Queue(); self.current_target=None; self.current_speed=0; self.active_move=False
    def stop(self): self.cancel.set()
    def pause_run(self):
        self.commands.put("pause")
    def resume_run(self):
        self.commands.put("resume")
    def home_run(self):
        self.commands.put("home")
    def run_home(self):
        try:
            self._service_commands()
            self.emit(("state","homing"))
            if not self.backend.home(self.cancel): raise RuntimeError("home failed or cancelled")
            self.backend.disable()
            if not self.backend.is_disabled(): raise RuntimeError("home disable was not confirmed")
            self.emit(("state","home complete"))
        except Exception as exc: self.emit(("error",str(exc)))
        finally: self.backend.close()
    def _service_commands(self):
        while True:
            try: command=self.commands.get_nowait()
            except queue.Empty: return
            if command == "pause":
                self.backend.disable()
                if hasattr(self.backend,"is_disabled") and not self.backend.is_disabled(): raise RuntimeError("pause disable was not confirmed")
                self.pause.set(); self.emit(("state","paused"))
            elif command == "resume":
                self.backend.enable()
                if hasattr(self.backend,"is_disabled") and self.backend.is_disabled(): raise RuntimeError("resume enable was not confirmed")
                self.pause.clear()
                if self.active_move and self.current_target is not None and not self.backend.move(self.current_target,self.current_speed,self.cancel): raise RuntimeError("resume target command failed")
                self.emit(("state","running"))
            elif command == "home":
                self.emit(("state","homing"))
                if not self.backend.home(self.cancel): raise RuntimeError("home failed or cancelled")
                self.backend.disable()
                if not self.backend.is_disabled(): raise RuntimeError("home disable was not confirmed")
                self.emit(("state","home complete"))
    def run(self, cfg: GuiConfig):
        try:
            if not (-180 <= cfg.a <= 180 and -180 <= cfg.b <= 180): raise ValueError("angles must be -180..180")
            if not (10 <= cfg.speed <= 30): raise ValueError("speed must be 10..30 deg/s")
            self.emit(("state","running")); self.backend.enable()
            targets=[]
            if cfg.bidirectional:
                for _ in range(max(1,cfg.repeats)): targets += [cfg.a,cfg.b,cfg.a]
            else:
                # Single mode is explicitly one move from current position to B.
                targets = [cfg.b]
            for target in targets:
                self.current_target=target; self.current_speed=cfg.speed
                self._service_commands()
                while self.pause.is_set() and not self.cancel.is_set(): self._service_commands(); time.sleep(.05)
                if self.cancel.is_set(): break
                if not self.backend.move(target,cfg.speed,self.cancel):
                    if self.pause.is_set() and not self.cancel.is_set(): continue
                    break
                self.active_move=True
                if hasattr(self.backend,"position"):
                    deadline=time.monotonic()+30.0
                    while time.monotonic()<deadline and not self.cancel.is_set():
                        self._service_commands()
                        if self.pause.is_set(): time.sleep(.05); continue
                        if hasattr(self.backend,"error") and self.backend.error()!=0: raise RuntimeError("device error")
                        if abs(self.backend.position()-target)<0.05: break
                        time.sleep(.05)
                    else:
                        if self.cancel.is_set(): break
                        raise RuntimeError("move timeout")
                self.emit(("position",target))
                self.active_move=False
            self.emit(("state","paused" if self.pause.is_set() else "stopped" if self.cancel.is_set() else "complete"))
        except Exception as exc: self.emit(("error",str(exc)))
        finally:
            self.backend.disable(); self.backend.close(); self.emit(("disabled",True))

def build_app(backend):
    import tkinter as tk
    from tkinter import ttk
    root=tk.Tk(); root.title("PDXC Angle Controller")
    port=tk.StringVar(value=""); a=tk.StringVar(value="0"); b=tk.StringVar(value="120"); speed=tk.StringVar(value="20"); repeats=tk.StringVar(value="1"); bi=tk.BooleanVar(value=True); status=tk.StringVar(value="Disconnected")
    ttk.Label(root,text="Port").grid(row=0,column=0); ports=ttk.Combobox(root,textvariable=port,values=backend.list_ports()); ports.grid(row=0,column=1); ttk.Button(root,text="Refresh",command=lambda: ports.configure(values=backend.list_ports())).grid(row=0,column=2)
    ttk.Button(root,text="Connect",command=lambda: (backend.open(port.get()),status.set("Connected"))).grid(row=1,column=0); ttk.Label(root,textvariable=status).grid(row=1,column=1,columnspan=2)
    for i,(label,var) in enumerate((("A deg",a),("B deg",b),("Speed deg/s",speed),("Repeats",repeats)),2): ttk.Label(root,text=label).grid(row=i,column=0); ttk.Entry(root,textvariable=var,width=12).grid(row=i,column=1)
    ttk.Checkbutton(root,text="Bidirectional return",variable=bi).grid(row=6,column=0,columnspan=2)
    worker=[None]
    def on_worker_event(event):
        # Tk callbacks only update widgets; all serial I/O remains in the worker.
        def apply_event():
            status.set(str(event[1]))
            if event[0] == "disabled":
                worker[0] = None
        root.after(0, apply_event)
    def start():
        if worker[0] is not None and getattr(worker[0], "thread", None) is not None and worker[0].thread.is_alive():
            status.set("Busy"); return
        try:
            cfg=GuiConfig(float(a.get()),float(b.get()),float(speed.get()),int(repeats.get()),bi.get())
            if hasattr(backend, "io") and backend.io.ser is None:
                backend.open(port.get())
            worker[0]=SweepWorker(backend,on_worker_event)
            worker[0].thread=threading.Thread(target=worker[0].run,args=(cfg,),daemon=True)
            worker[0].thread.start()
        except Exception as exc:
            status.set(f"error: {exc}")
    def stop():
        if worker[0]: worker[0].stop(); status.set("Stopping")
    def pause_resume():
        if not worker[0]: return
        if worker[0].pause.is_set(): worker[0].resume_run()
        else: worker[0].pause_run()
    ttk.Button(root,text="Play",command=start).grid(row=7,column=0); ttk.Button(root,text="Pause/Resume",command=pause_resume).grid(row=7,column=1); ttk.Button(root,text="Cancel",command=stop).grid(row=7,column=2)
    def home():
        if worker[0] is not None and getattr(worker[0], "thread", None) is not None and worker[0].thread.is_alive(): return
        worker[0]=SweepWorker(backend,on_worker_event)
        worker[0].thread=threading.Thread(target=worker[0].run_home,daemon=True)
        worker[0].thread.start(); status.set("Homing")
    ttk.Button(root,text="Home",command=home).grid(row=8,column=0)
    root.protocol("WM_DELETE_WINDOW",lambda: (stop(),root.destroy())); return root

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--simulate",action="store_true"); p.add_argument("--port"); args=p.parse_args(argv)
    backend=SimBackend() if args.simulate else LiveBackend(args.port or "")
    build_app(backend).mainloop()

if __name__ == "__main__":
    main()
