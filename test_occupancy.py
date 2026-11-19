"""
test_occupancy.py - breadboard tests for the two IR sensors and occupancy.py.

Run this file from Thonny (or save it as main.py temporarily). Pick a stage below.

  STAGE 1: raw sensor check, ONE sensor at a time. No counting logic involved.
           Wave your hand in front of A, then B, and watch the console.
           Checks: wiring, polarity (detect = 0), pot range, sensors stuck at 0.
  STAGE 2: the real occupancy counter with verbose output.
           Move your hand past A then B (ENTER), then B then A (LEAVE).

Breadboard: sensor VCC -> 3V3, GND -> GND, OUT_A -> GP14, OUT_B -> GP15.
"""
import time
import machine
from machine import Pin
import occupancy

STAGE = 1
PIN_A = 14
PIN_B = 15
STUCK_MS = 3000       # a sensor reading 0 for this long is probably stuck


# ================= stage 1: raw sensor check =================
def sensor_check():
    names = ["A", "B"]
    pins = [Pin(PIN_A, Pin.IN, Pin.PULL_UP), Pin(PIN_B, Pin.IN, Pin.PULL_UP)]
    now = time.ticks_ms()
    last = [pins[0].value(), pins[1].value()]    # last seen state
    since = [now, now]                            # when that state began
    warned = [False, False]

    print("Sensor check. Detect = 0, clear = 1.")
    print("Start state: A =", last[0], " B =", last[1])
    if last[0] == 0 or last[1] == 0:
        print("WARNING: a sensor already reads 0 with nothing in front of it.")
        print("         Turn its pot down, or aim it away from walls and objects.")

    while True:
        now = time.ticks_ms()
        for i in range(2):
            v = pins[i].value()
            if v != last[i]:
                held = time.ticks_diff(now, since[i])
                if v == 0:
                    print(names[i], "DETECTED  (was clear for", held, "ms)")
                else:
                    print(names[i], "clear     (was blocked for", held, "ms)")
                last[i] = v
                since[i] = now
                warned[i] = False
            elif v == 0 and not warned[i] and time.ticks_diff(now, since[i]) > STUCK_MS:
                print(names[i], "has read 0 for", STUCK_MS, "ms: stuck low. Pot too",
                      "sensitive, or it sees something nearby?")
                warned[i] = True


# ================= stage 2: the real counter =================
def room_changed(count):
    print("   -> people in room:", count)


def counter_demo():
    occupancy.start(pin_a=PIN_A, pin_b=PIN_B, led_pin="LED",
                    on_change=room_changed, verbose=True)
    print("Counter running (WINDOW_MS =", occupancy.WINDOW_MS, "ms).")
    print("A then B quickly = ENTER, B then A = LEAVE.")
    print("Expect: lone trigger ignored, holding a beam does not double-count.")
    while True:
        machine.idle()      # the timer and pin interrupts do all the work


if __name__ == "__main__":
    if STAGE == 1:
        sensor_check()
    else:
        counter_demo()
