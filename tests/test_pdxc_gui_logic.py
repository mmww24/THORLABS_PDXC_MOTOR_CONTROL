import threading
import time
from pdxc_gui import GuiConfig, SimBackend, SweepWorker

def test_simulated_bidirectional_worker_disables_on_completion():
    b=SimBackend(); events=[]; w=SweepWorker(b, events.append)
    w.run(GuiConfig(0,2,20,1,True))
    assert b.moves == [0,2,0]
    assert b.disabled_state == 1
    assert ("state","complete") in events

def test_cancel_disables_and_stops_followup_targets():
    b=SimBackend(); events=[]; w=SweepWorker(b,events.append); w.cancel.set()
    w.run(GuiConfig(0,2,20,2,True))
    assert b.disabled_state == 1
    assert b.moves == []

def test_pause_holds_targets_then_resume_preserves_order():
    b=SimBackend(); events=[]; w=SweepWorker(b,events.append); w.pause_run()
    t=threading.Thread(target=w.run,args=(GuiConfig(0,1,20,1,True),)); t.start()
    time.sleep(.03)
    assert b.moves == []
    w.resume_run(); t.join(1)
    assert b.moves == [0,1,0]
    assert b.disabled_state == 1

def test_single_direction_is_one_move_to_b():
    b=SimBackend(); w=SweepWorker(b,lambda _: None)
    w.run(GuiConfig(10,20,20,5,False))
    assert b.moves == [20]
