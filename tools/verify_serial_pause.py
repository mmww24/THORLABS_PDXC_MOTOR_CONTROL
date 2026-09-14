import argparse,csv,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pdxc_serial import PDXCSerial,SerialConfig

def main():
 p=argparse.ArgumentParser(); p.add_argument('--execute',action='store_true'); p.add_argument('--port',required=True, help='COM port or /dev/ttyUSB device'); p.add_argument('--csv',default='artifacts/serial_pause.csv'); a=p.parse_args()
 if not a.execute: print('dry-run; pass --execute'); return
 b=PDXCSerial(SerialConfig(a.port,timeout=1)); rows=[]
 try:
  b.open(); assert 'PDXR1' in b.get_stage(); assert b.get_loop()==0; assert b.get_trigger_mode().startswith('ML'); assert b.get_error()==0; assert b.get_disabled()==1; assert b.get_calibration().upper().startswith('YES')
  b.set_disabled(0); assert b.get_disabled()==0; b.set_speed(20); b.set_position(0)
  deadline=time.time()+15
  while time.time()<deadline:
   pos=b.get_position(); rows.append((time.time(),'to0',pos,b.get_status(),b.get_error()))
   if abs(pos)<.05: break
   time.sleep(.1)
  b.set_position(120); time.sleep(1); b.set_disabled(1); assert b.get_disabled()==1
  stable=[]; end=time.time()+2
  while time.time()<end:
   pos=b.get_position(); stable.append(pos); rows.append((time.time(),'pause',pos,b.get_status(),b.get_error())); time.sleep(.2)
  if max(stable)-min(stable)>.05: raise RuntimeError('pause did not stabilize')
  b.set_disabled(0); b.set_position(120); deadline=time.time()+15
  while time.time()<deadline:
   pos=b.get_position(); rows.append((time.time(),'resume120',pos,b.get_status(),b.get_error()))
   if abs(pos-120)<.05: break
   time.sleep(.1)
  b.set_position(0); deadline=time.time()+15
  while time.time()<deadline:
   pos=b.get_position(); rows.append((time.time(),'to0',pos,b.get_status(),b.get_error()))
   if abs(pos)<.05: break
   time.sleep(.1)
 finally:
  try: b.set_disabled(1)
  except Exception: pass
  with open(a.csv,'w',newline='') as f: csv.writer(f).writerows([('timestamp','stage','position','status','error')]+rows)
  b.close()
if __name__=='__main__': main()
