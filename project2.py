from machine import Pin
import time

TIMEOUT_SECONDS = 1
EMPTY_ALERT_SECONDS = 30
DEBOUNCE_MS = 50  # Ignore rapid re-triggers on the same sensor within 50ms

# Hardware Setup (kept from project.py: A=14, B=15)
sensor_a = Pin(14, Pin.IN, Pin.PULL_UP)
sensor_b = Pin(15, Pin.IN, Pin.PULL_UP)
led = Pin("LED", Pin.OUT)

# State Variables
state = {
    'first_sensor': None,
    'start_tick': 0,
    'prev_a': sensor_a.value(),
    'prev_b': sensor_b.value(),
    'last_a_tick': 0,
    'last_b_tick': 0,
    'timeout_ms': TIMEOUT_SECONDS * 1000,
    'people_count': 0,
    'empty_since_tick': None,
    'alert_count': 0,
    'last_print_tick': 0
}

def keep_led_off(led_pin):
    led_pin.value(0)

def check_edge_transition(curr, prev):
    return (prev == 1 and curr == 0)

def check_timeout(first_sens, start, timeout):
    if first_sens is not None:
        if time.ticks_diff(time.ticks_ms(), start) > timeout:
            return None
    return first_sens

def evaluate_sensors(s_a, s_b, current_state):
    curr_a = s_a.value()
    curr_b = s_b.value()
    now = time.ticks_ms()

    current_state['first_sensor'] = check_timeout(
        current_state['first_sensor'],
        current_state['start_tick'],
        current_state['timeout_ms']
    )

    a_triggered = check_edge_transition(curr_a, current_state['prev_a'])
    b_triggered = check_edge_transition(curr_b, current_state['prev_b'])

    # Debounce filter (kept from project.py)
    if a_triggered:
        if time.ticks_diff(now, current_state['last_a_tick']) < DEBOUNCE_MS:
            a_triggered = False
        else:
            current_state['last_a_tick'] = now

    if b_triggered:
        if time.ticks_diff(now, current_state['last_b_tick']) < DEBOUNCE_MS:
            b_triggered = False
        else:
            current_state['last_b_tick'] = now

    # Detect Sensor A Trigger (1 -> 0)
    if a_triggered:
        if current_state['first_sensor'] == 'B':
            current_state['prev_a'] = curr_a
            current_state['prev_b'] = curr_b
            return "LEAVING"
        elif current_state['first_sensor'] is None:
            current_state['first_sensor'] = 'A'
            current_state['start_tick'] = now

    # Detect Sensor B Trigger (1 -> 0)
    if b_triggered:
        if current_state['first_sensor'] == 'A':
            current_state['prev_a'] = curr_a
            current_state['prev_b'] = curr_b
            return "ENTERING"
        elif current_state['first_sensor'] is None:
            current_state['first_sensor'] = 'B'
            current_state['start_tick'] = now

    current_state['prev_a'] = curr_a
    current_state['prev_b'] = curr_b
    return None

print("Door Monitor Started...")

# Main Loop
while True:
    keep_led_off(led)
    now = time.ticks_ms()

    direction = evaluate_sensors(sensor_a, sensor_b, state)

    if direction == "ENTERING":
        state['people_count'] += 1
        print("Entering - People inside:", state['people_count'])
        state['empty_since_tick'] = None
        state['alert_count'] = 0
        state['first_sensor'] = None
    elif direction == "LEAVING":
        if state['people_count'] > 0:
            state['people_count'] -= 1
            print("Leaving - People inside:", state['people_count'])
            if state['people_count'] == 0:
                print("Room is empty")
                state['empty_since_tick'] = now
                state['alert_count'] = 0
        state['first_sensor'] = None

    # Empty room tracking & terminal timer output
    if state['people_count'] == 0:
        if state['empty_since_tick'] is None:
            state['empty_since_tick'] = now
            state['alert_count'] = 0
        else:
            elapsed_ms = time.ticks_diff(now, state['empty_since_tick'])
            elapsed_sec = elapsed_ms // 1000
            remaining_sec = EMPTY_ALERT_SECONDS - (elapsed_sec % EMPTY_ALERT_SECONDS)

            if time.ticks_diff(now, state['last_print_tick']) >= 1000:
                if remaining_sec > 0:
                    print(f"Room empty timer: {remaining_sec}s remaining...")
                state['last_print_tick'] = now

            if elapsed_ms >= EMPTY_ALERT_SECONDS * 1000:
                state['alert_count'] += 1
                total_empty_sec = state['alert_count'] * EMPTY_ALERT_SECONDS
                print(f"\aALERT: Room has been empty for {total_empty_sec} seconds")
                state['empty_since_tick'] += EMPTY_ALERT_SECONDS * 1000
    else:
        state['empty_since_tick'] = None
        state['alert_count'] = 0

    time.sleep_ms(10)