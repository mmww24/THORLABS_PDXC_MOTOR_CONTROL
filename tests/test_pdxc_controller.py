import pytest
from pdxc_controller import Sweep, FakeBackend, run_sweep, calibration_ok

def test_calibration_response_normalization():
    assert calibration_ok("Yes!>\r\n")
    assert calibration_ok("YES")
    assert not calibration_ok("No!>\r\n")
    assert not calibration_ok("YESISH")
from pdxc_controller import PDXCError
import pdxc_controller

def test_plan_is_a_b_a_per_cycle():
    assert Sweep(-10,20,10,2).plan()==[-10,20,-10,-10,20,-10]

def test_ranges():
    with pytest.raises(ValueError): Sweep(-181,0,10,1).validate()
    with pytest.raises(ValueError): Sweep(0,1,9,1).validate()

def test_dry_run_does_not_move():
    b=FakeBackend(); s=Sweep(0,10,10,1)
    assert run_sweep(b,s)==[0,10,0]; assert b.moves==[]

def test_execute_preflight_accepts_closed_loop_calibrated_pdxr():
    b=FakeBackend(); s=Sweep(0,10,10,1)
    b.loop=lambda: 0
    assert run_sweep(b,s,execute=True)==[0,10,0]
    assert b.moves==[0,10,0]

def test_open_loop_is_rejected_without_motion():
    b=FakeBackend(); b.loop=lambda: 1
    with pytest.raises(PDXCError, match="closed-loop"):
        run_sweep(b, Sweep(0,10,10,1), execute=True)
    assert b.moves==[]

def test_non_manual_trigger_is_rejected_without_motion():
    b=FakeBackend(); b.loop=lambda: 0; b.manual_mode=lambda: "AR"
    with pytest.raises(PDXCError, match="Manual"):
        run_sweep(b, Sweep(0,10,10,1), execute=True)
    assert b.moves==[]

def test_closed_loop_transition_failure_is_not_ignored():
    class B(FakeBackend):
        def loop(self): return 1
        def set_loop(self, value): return -1
    b=B()
    with pytest.raises(PDXCError, match="closed-loop"):
        run_sweep(b, Sweep(0,10,10,1), execute=True)
    assert b.moves==[]

def test_speed_failure_blocks_motion():
    class B(FakeBackend):
        def set_speed(self, value): return -1
    with pytest.raises(PDXCError): run_sweep(B(), Sweep(0,10,10,1), execute=True)

def test_preflight_error_blocks_motion():
    class B(FakeBackend):
        def error(self): return 5
    b=B()
    with pytest.raises(PDXCError): run_sweep(b, Sweep(0,10,10,1), execute=True)
    assert b.moves==[]

def test_disabled_or_uncalibrated_blocks_motion():
    class B(FakeBackend):
        def disabled(self): return 1
    with pytest.raises(PDXCError): run_sweep(B(), Sweep(0,10,10,1), execute=True)
    class C(FakeBackend):
        def homed(self): return "NO"
    with pytest.raises(PDXCError): run_sweep(C(), Sweep(0,10,10,1), execute=True)

def test_timeout_stops_without_issuing_followup_move(monkeypatch):
    class Stalled(FakeBackend):
        def move(self, value):
            self.moves.append(value)
            return 0
    now=[0.0]
    monkeypatch.setattr(pdxc_controller.time, "monotonic", lambda: (now.__setitem__(0, now[0]+11.0) or now[0]))
    monkeypatch.setattr(pdxc_controller.time, "sleep", lambda _: None)
    b=Stalled()
    with pytest.raises(PDXCError, match="move timeout"):
        run_sweep(b, Sweep(0,10,10,1), execute=True)
    assert b.moves == [0]
