import pytest
from pdxc_serial import PDXCSerial, SerialConfig

class FakeSerial:
    def __init__(self,*a,**kw): self.writes=[]; self.closed=False
    def reset_input_buffer(self): pass
    def write(self,b): self.writes.append(b)
    def flush(self): pass
    def read_until(self,_): return b'OK!\r\n'
    def close(self): self.closed=True

def test_query_is_cr_terminated_and_ascii():
    holder=[]
    def make(*a,**kw): x=FakeSerial(*a,**kw); holder.append(x); return x
    b=PDXCSerial(SerialConfig('FAKE_PORT'),make); b.open()
    holder[0].read_until=lambda _: b'12.5 deg>\r\n'
    assert b.get_position()==12.5
    assert holder[0].writes==[b'POS?\r']
    b.close(); assert holder[0].closed

def test_setter_is_rejected():
    b=PDXCSerial(SerialConfig('x'),lambda *a,**k: FakeSerial()); b.open()
    with pytest.raises(ValueError): b.query('POS=1')

def test_documented_setters_and_ranges():
    h=[]
    def make(*a,**k): x=FakeSerial(*a,**k); h.append(x); return x
    b=PDXCSerial(SerialConfig('x'),make); b.open(); b.set_speed(20); b.set_position(1); b.set_loop(0); b.set_disabled(1); b.home()
    assert h[0].writes == [b'SPD=20\r', b'POS=1.000000\r', b'LP=0\r', b'DIS=1\r', b'HOM=1\r']
    with pytest.raises(ValueError): b.set_speed(9)
    with pytest.raises(ValueError): b.set_position(181)

def test_setter_rejects_non_ack_without_retry():
    h=FakeSerial(); h.read_until=lambda _: b'TIME OUT!\r\n'
    b=PDXCSerial(SerialConfig('x'),lambda *a,**k:h); b.open()
    with pytest.raises(IOError): b.set_speed(20)
    assert h.writes == [b'SPD=20\r']
