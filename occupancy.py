"""
occupancy.py - two-sensor directional room occupancy counter (MicroPython, Pico).

Use it from a bigger program:

    import occupancy
    occupancy.start(pin_a=14, pin_b=15)
    ...
    occupancy.get_count()      # people currently in the room
    occupancy.is_occupied()    # True if count > 0
    occupancy.stop()

Sensor A = outside side of the door, Sensor B = inside side.
A trips first, then B  -> someone ENTERED  (count + 1)
B trips first, then A  -> someone LEFT     (count - 1, never below 0)

Both sensors must read 0 when they detect something (YL-70 / FC-51 style modules,
or a pushbutton wired to GND in the Wokwi simulator).

It runs in the background (pin interrupts + one hardware timer), so your main
program is free to do other work. Names starting with _ are internal.
"""
import time
import machine
from machine import Pin, Timer

# ================= settings (change before calling start() if needed) =================
WINDOW_SECONDS = 0.6  # max gap between the two triggers, in seconds
WINDOW_MS = int(WINDOW_SECONDS * 1000)
                      # Use ~1000+ in the simulator (clicking two buttons by hand is slow)
                      # and raise it if slow walkers get ignored
CLEAR_MS = 100        # both beams must stay clear this long before re-arming
TICK_MS = 5           # timer tick period

# ================= state (internal) =================
_irA = None
_irB = None
_led = None
_timer = None
_on_change = None
_verbose = False

_pop = 0
_trigger_time = {"A": None, "B": None}   # ticks_ms of first falling edge, or None
_waiting_clear = False    # True after a count, until the doorway is empty again
_clear_since = None       # when both beams were first seen clear


# ================= outputs =================
def _update_led():
    if _led is not None:
        _led.value(1 if _pop > 0 else 0)


def _pop_changed():
    """Called whenever the count changes: LED, optional print, optional callback."""
    _update_led()
    if _verbose:
        print("pop =", _pop, "->", "OCCUPIED" if _pop > 0 else "EMPTY")
    if _on_change is not None:
        _on_change(_pop)


# ================= armed mode: _check_for_crossing() and what it calls =================
def _read_triggers():
    """1. Atomic copy of both timestamps so the interrupt can't change them mid-read."""
    state = machine.disable_irq()
    a, b = _trigger_time["A"], _trigger_time["B"]
    machine.enable_irq(state)
    return a, b


def _check_direction(a, b):
    """2. Both timestamps present: decide who came first and update the count."""
    global _pop
    gap = time.ticks_diff(b, a)          # >0: A first, <0: B first
    if abs(gap) > WINDOW_MS or gap == 0:
        if _verbose:
            print("ignored (gap", gap, "ms)")
        return
    if gap > 0:
        _pop += 1
        if _verbose:
            print("ENTER")
    else:
        if _pop > 0:
            _pop -= 1
        if _verbose:
            print("LEAVE")


def _drop_if_stale(key, stamp, now):
    """3. A lone trigger whose partner never came within WINDOW_MS is discarded."""
    if stamp is not None and time.ticks_diff(now, stamp) > WINDOW_MS:
        _trigger_time[key] = None


def _check_for_crossing(now):
    """Return True if both sensors fired (a full crossing, counted or ignored)."""
    a, b = _read_triggers()                      # 1
    if a is not None and b is not None:
        old = _pop
        _check_direction(a, b)                   # 2
        if _pop != old:
            _pop_changed()
        return True
    _drop_if_stale("A", a, now)                  # 3
    _drop_if_stale("B", b, now)
    return False


# ================= waiting mode: _beams_clear_long_enough() and _clear_triggers() =================
def _beams_clear_long_enough(now):
    """1. True once BOTH sensors have read 1 continuously for CLEAR_MS."""
    global _clear_since
    if _irA.value() == 1 and _irB.value() == 1:
        if _clear_since is None:
            _clear_since = now
        if time.ticks_diff(now, _clear_since) >= CLEAR_MS:
            _clear_since = None
            return True
    else:
        _clear_since = None         # someone is still there, restart the wait
    return False


def _clear_triggers():
    """2. Wipe both timestamps so the next person starts fresh."""
    state = machine.disable_irq()
    _trigger_time["A"] = None
    _trigger_time["B"] = None
    machine.enable_irq(state)


# ================= interrupt handlers + timer (the entry points) =================
def _handler_A(pin):
    """Pin interrupt: beam A broke. Tiny on purpose, just stamp the time once."""
    if _trigger_time["A"] is None:
        _trigger_time["A"] = time.ticks_ms()


def _handler_B(pin):
    """Pin interrupt: beam B broke."""
    if _trigger_time["B"] is None:
        _trigger_time["B"] = time.ticks_ms()


def _tick(timer):
    """Timer callback, every TICK_MS: one step of the state machine."""
    global _waiting_clear
    now = time.ticks_ms()

    if _waiting_clear:
        if _beams_clear_long_enough(now):
            _clear_triggers()
            _waiting_clear = False
    elif _check_for_crossing(now):
        _waiting_clear = True


# ================= public API =================
def start(pin_a=14, pin_b=15, led_pin=None, on_change=None, verbose=False):
    """
    Start counting in the background.
      pin_a, pin_b : GPIO numbers of sensor A (outside) and B (inside)
      led_pin      : optional LED pin (number, or "LED" for the Pico W onboard LED);
                     on while someone is in the room
      on_change    : optional function(count) called when the count changes.
                     Keep it short, it runs from the timer tick.
      verbose      : print ENTER / LEAVE / count messages
    """
    global _irA, _irB, _led, _timer, _on_change, _verbose
    global _pop, _waiting_clear, _clear_since

    if _timer is not None:
        stop()

    _on_change = on_change
    _verbose = verbose
    _led = Pin(led_pin, Pin.OUT) if led_pin is not None else None

    _pop = 0
    _waiting_clear = False
    _clear_since = None
    _clear_triggers()

    # Pull-ups so a pushbutton to GND works in the simulator. Harmless with real
    # modules because they drive the line themselves.
    _irA = Pin(pin_a, Pin.IN, Pin.PULL_UP)
    _irB = Pin(pin_b, Pin.IN, Pin.PULL_UP)
    _irA.irq(trigger=Pin.IRQ_FALLING, handler=_handler_A)
    _irB.irq(trigger=Pin.IRQ_FALLING, handler=_handler_B)

    _update_led()
    if _verbose:
        print("occupancy: started, count = 0")
    _timer = Timer(period=TICK_MS, mode=Timer.PERIODIC, callback=_tick)


def stop():
    """Stop the timer and the pin interrupts."""
    global _timer
    if _timer is not None:
        _timer.deinit()
        _timer = None
    if _irA is not None:
        _irA.irq(handler=None)
    if _irB is not None:
        _irB.irq(handler=None)


def get_count():
    """People currently in the room."""
    return _pop


def is_occupied():
    return _pop > 0


def reset(count=0):
    """Force the count (e.g. to correct drift when you know the room is empty)."""
    global _pop
    _pop = count
    _update_led()
