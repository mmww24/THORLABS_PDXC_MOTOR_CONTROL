"""Safe PDXC angle sweep controller. Hardware access requires --execute."""
from __future__ import annotations
import argparse, ctypes, time, csv
from dataclasses import dataclass

class PDXCError(RuntimeError): pass

def calibration_ok(raw: str) -> bool:
    """Accept only the SDK's affirmative Yes response, with prompt suffixes."""
    token=raw.strip().split('!',1)[0].strip().upper()
    return token == "YES"

class Backend:
    def list_devices(self): raise NotImplementedError
    def open(self, serial, baud=115200, timeout=3): raise NotImplementedError
    def close(self): raise NotImplementedError

class FakeBackend(Backend):
    def __init__(self): self.position=0.0; self.moves=[]; self.opened=False; self._loop=0
    def list_devices(self): return [["FAKE", "COM0"]]
    def open(self, serial, baud=115200, timeout=3): self.opened=True; return 1
    def close(self): self.opened=False
    def stage(self): return "SN000000PDXR1/M"
    def stage_type(self): return 0
    def loop(self): return 0
    def disabled(self): return 0
    def set_loop(self, value): self._loop=value; return 0
    def manual_mode(self): return "ML"
    def trigger_mode(self): return self.manual_mode()
    def homed(self): return "YES"
    def home(self): return 0
    def set_disabled(self, value): self._disabled=value; return 0
    def position_now(self): return self.position
    def status(self): return "OK"
    def error(self): return 0
    def set_speed(self, value): self.speed=value
    def move(self, value): self.moves.append(value); self.position=value; return 0

class NativeBackend(Backend):
    def __init__(self, dll):
        self.lib=ctypes.WinDLL(dll); self.hdl=-1
        self.lib.List.argtypes=[ctypes.c_char_p,ctypes.c_int]; self.lib.List.restype=ctypes.c_int
        self.lib.Open.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.c_int]; self.lib.Open.restype=ctypes.c_int
        self.lib.Close.argtypes=[ctypes.c_int]; self.lib.Close.restype=ctypes.c_int
        self.lib.Get_SN2.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_char_p]
        self.lib.Get_CurrentPosition.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_double)]
        self.lib.Get_CurrentStatus.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_char_p]
        self.lib.Get_ErrorMessage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
        self.lib.Get_ErrorMessage.restype=ctypes.c_int
        self.lib.Get_SpeedStageType.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
        self.lib.Get_SpeedStageType.restype=ctypes.c_int
        self.lib.Get_LoopStatus.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
        self.lib.Get_LoopStatus.restype=ctypes.c_int
        self.lib.Get_Disabled.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
        self.lib.Get_Disabled.restype=ctypes.c_int
        self.lib.Get_CalibrationIsCompleted.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_char_p]
        self.lib.Get_CalibrationIsCompleted.restype=ctypes.c_int
        self.lib.Set_PositionCalibration.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_int]; self.lib.Set_PositionCalibration.restype=ctypes.c_int
        self.lib.Set_TargetSpeed.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_int]
        self.lib.Set_TargetPosition.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_double]
        self.lib.Set_Loop.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_int]; self.lib.Set_Loop.restype=ctypes.c_int
        self.lib.Get_CurrentStatusInExternalTrigger.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_char_p]
        self.lib.Get_CurrentStatusInExternalTrigger.restype=ctypes.c_int
        self.lib.Set_TargetSpeed.restype=ctypes.c_int
        self.lib.Set_TargetPosition.restype=ctypes.c_int
    def list_devices(self):
        b=ctypes.create_string_buffer(10240); self.lib.List(b,10240)
        a=b.value.decode(errors="ignore").split(','); return [a[i:i+2] for i in range(0,len(a)-1,2) if a[i]]
    def open(self, serial, baud=115200, timeout=3):
        self.hdl=self.lib.Open(serial.encode(),baud,timeout)
        if self.hdl<0: raise PDXCError(f"Open failed: {self.hdl}")
        return self.hdl
    def close(self):
        if self.hdl>=0: self.lib.Close(self.hdl); self.hdl=-1
    def stage(self):
        b=ctypes.create_string_buffer(1024); rc=self.lib.Get_SN2(self.hdl,0,b)
        if rc < 0: raise PDXCError(f"stage query failed: {rc}")
        return b.value.decode(errors='ignore').strip()
    def stage_type(self):
        x=ctypes.c_int(); rc=self.lib.Get_SpeedStageType(self.hdl,0,ctypes.byref(x))
        if rc < 0: raise PDXCError(f"stage type query failed: {rc}")
        return x.value
    def loop(self):
        x=ctypes.c_int(); rc=self.lib.Get_LoopStatus(self.hdl,0,ctypes.byref(x))
        if rc < 0: raise PDXCError(f"loop query failed: {rc}")
        return x.value
    def disabled(self):
        x=ctypes.c_int(); rc=self.lib.Get_Disabled(self.hdl,0,ctypes.byref(x))
        if rc < 0: raise PDXCError(f"disabled query failed: {rc}")
        return x.value
    def homed(self):
        b=ctypes.create_string_buffer(32); rc=self.lib.Get_CalibrationIsCompleted(self.hdl,0,b)
        if rc < 0: raise PDXCError(f"calibration query failed: {rc}")
        return b.value.decode(errors='ignore').strip()
    def position_now(self):
        x=ctypes.c_double(); rc=self.lib.Get_CurrentPosition(self.hdl,0,ctypes.byref(x))
        if rc < 0: raise PDXCError(f"position query failed: {rc}")
        return x.value
    def status(self):
        b=ctypes.create_string_buffer(1024); rc=self.lib.Get_CurrentStatus(self.hdl,0,b)
        if rc < 0: raise PDXCError(f"status query failed: {rc}")
        return b.value.decode(errors='ignore').strip()
    def error(self):
        x=ctypes.c_int(); rc=self.lib.Get_ErrorMessage(self.hdl,0,ctypes.byref(x))
        if rc < 0: raise PDXCError(f"error query failed: {rc}")
        return x.value
    def set_speed(self, value): return self.lib.Set_TargetSpeed(self.hdl,0,value)
    def set_loop(self, value): return self.lib.Set_Loop(self.hdl,0,value)
    def home(self): return self.lib.Set_PositionCalibration(self.hdl,0,1)
    def set_disabled(self, value): return self.lib.Set_Disabled(self.hdl,0,value)
    def manual_mode(self):
        b=ctypes.create_string_buffer(64); rc=self.lib.Get_CurrentStatusInExternalTrigger(self.hdl,0,b)
        if rc<0: raise PDXCError(f"trigger mode query failed: {rc}")
        return b.value.decode(errors='ignore').strip().rstrip('>')
    def trigger_mode(self): return self.manual_mode()
    def move(self, value): return self.lib.Set_TargetPosition(self.hdl,0,value)

@dataclass
class Sweep:
    a: float; b: float; speed: int; cycles: int
    def validate(self):
        if not (-180<=self.a<=180 and -180<=self.b<=180): raise ValueError("PDXR angles must be -180..180 deg")
        if not (10<=self.speed<=30): raise ValueError("PDXR nominal speed must be 10..30 deg/s")
        if self.cycles<1: raise ValueError("cycles must be >=1")
    def plan(self): return [x for _ in range(self.cycles) for x in (self.a,self.b,self.a)]

def run_sweep(backend, sweep, execute=False, csv_path=None, tolerance=1e-3, stage_model="PDXR1", closed_loop=False, leg_timeout=10.0):
    sweep.validate(); plan=sweep.plan(); rows=[]
    if not execute: return plan
    model=backend.stage();
    if stage_model not in model: raise PDXCError(f"stage model mismatch: {model}")
    if hasattr(backend,'stage_type') and backend.stage_type()!=0: raise PDXCError("not a D-Sub stage")
    if hasattr(backend,'loop') and backend.loop()!=0:
        if not closed_loop: raise PDXCError("closed-loop required; pass --closed-loop")
        rc=backend.set_loop(0)
        if rc<0: raise PDXCError("closed-loop transition failed")
        if backend.loop()!=0: raise PDXCError("closed-loop transition not confirmed")
        if backend.position_now() is None or backend.error()!=0: raise PDXCError("post-transition validation failed")
    if hasattr(backend,'disabled') and backend.disabled()!=0: raise PDXCError("stage is disabled")
    if hasattr(backend,'homed') and not calibration_ok(backend.homed()): raise PDXCError("stage is not calibrated/homed")
    mode = backend.trigger_mode() if hasattr(backend,'trigger_mode') else backend.manual_mode() if hasattr(backend,'manual_mode') else "ML"
    if mode != "ML": raise PDXCError("Manual mode required; external trigger mode is active")
    speed_rc=backend.set_speed(sweep.speed)
    if speed_rc is not None and speed_rc<0: raise PDXCError("speed command failed")
    out=open(csv_path,'w',newline='') if csv_path else None; writer=csv.writer(out) if out else None
    if writer: writer.writerow(['timestamp','target_deg','position_deg','status','error'])
    for target in plan:
        if backend.error() != 0: raise PDXCError("device error before move")
        if backend.move(target) < 0: raise PDXCError("target position command failed")
        deadline=time.monotonic()+leg_timeout
        while time.monotonic()<deadline:
            if backend.error()!=0: raise PDXCError("device error during move")
            pos=backend.position_now()
            if writer: writer.writerow([time.time(),target,pos,backend.status(),backend.error()]); out.flush()
            if abs(pos-target)<tolerance: break
            time.sleep(.1)
        else: raise PDXCError("move timeout; no further movement issued")
    if out: out.close()
    return plan

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('a',type=float); p.add_argument('b',type=float); p.add_argument('--speed',type=int,required=True); p.add_argument('--cycles',type=int,default=1); p.add_argument('--execute',action='store_true'); p.add_argument('--dll'); p.add_argument('--serial'); p.add_argument('--timeout',type=int,default=3); p.add_argument('--leg-timeout',type=float,default=30.0); p.add_argument('--stage-model',default='PDXR1'); p.add_argument('--tolerance',type=float,default=1e-3); p.add_argument('--csv'); p.add_argument('--closed-loop',action='store_true'); p.add_argument('--home',action='store_true'); p.add_argument('--keep-enabled',action='store_true'); p.add_argument('--enable',action='store_true')
    a=p.parse_args(argv)
    if a.execute and not a.dll: p.error("--dll is required with --execute")
    if a.execute and (not a.dll or not a.serial): p.error("--dll and --serial are required with --execute")
    s=Sweep(a.a,a.b,a.speed,a.cycles); backend=NativeBackend(a.dll) if a.execute else FakeBackend()
    try:
        if a.execute:
            devices=backend.list_devices()
            if not any(row and row[0] == a.serial for row in devices):
                raise PDXCError(f"serial not listed: {a.serial}; devices={devices}")
            backend.open(a.serial,115200,a.timeout)
            if backend.disabled() and not a.enable: raise PDXCError("stage disabled; pass --enable")
            if backend.disabled() and a.enable:
                if backend.set_disabled(0)<0 or backend.disabled()!=0: raise PDXCError("enable failed")
            if a.home:
                if backend.home()<0: raise PDXCError("home command failed")
                deadline=time.monotonic()+120
                while time.monotonic()<deadline and not calibration_ok(backend.homed()):
                    if backend.error()!=0: raise PDXCError("error during homing")
                    time.sleep(.5)
                if not calibration_ok(backend.homed()): raise PDXCError("home timeout")
        print(run_sweep(backend,s,a.execute,a.csv,a.tolerance,a.stage_model,a.closed_loop,a.leg_timeout))
    finally:
        if a.execute:
            try:
                if not a.keep_enabled and backend.hdl>=0:
                    if backend.set_disabled(1)<0 or backend.disabled()!=1: raise PDXCError("automatic disable failed")
            finally:
                backend.close()

if __name__ == "__main__":
    main()
