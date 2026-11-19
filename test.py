from machine import Pin
import time

TIMEOUT_SECONDS = 1
EMPTY_ALERT_SECONDS = 45

# Hardware Setup
sensor_a = Pin(14, Pin.IN, Pin.PULL_UP)
sensor_b = Pin(15, Pin.IN, Pin.PULL_UP)
led = Pin("LED", Pin.OUT)

# State Variables
state = {
    'first_sensor': None,
    'start_tick': 0,
    'prev_a': sensor_a.value(),
    'prev_b': sensor_b.value(),
    'timeout_ms': TIMEOUT_SECONDS * 1000,
    'people_count': 0,
    'empty_since_tick': None
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
    a_triggered = check_edge_transition(curr_a, current_state['prev_a'])
    b_triggered = check_edge_transition(curr_b, current_state['prev_b'])
    
    current_state['first_sensor'] = check_timeout(
        current_state['first_sensor'], 
        current_state['start_tick'], 
        current_state['timeout_ms']
    )

    # Ignore simultaneous sensor triggers; a valid crossing must be sequential.
    if a_triggered and b_triggered:
        current_state['first_sensor'] = None
        current_state['prev_a'] = curr_a
        current_state['prev_b'] = curr_b
        return None
    
    # Detect Sensor A Trigger (1 -> 0)
    if a_triggered:
        if current_state['first_sensor'] == 'B':
            current_state['prev_a'] = curr_a
            current_state['prev_b'] = curr_b
            return "LEAVING"
        elif current_state['first_sensor'] is None:
            current_state['first_sensor'] = 'A'
            current_state['start_tick'] = time.ticks_ms()

    # Detect Sensor B Trigger (1 -> 0)
    if b_triggered:
        if current_state['first_sensor'] == 'A':
            current_state['prev_a'] = curr_a
            current_state['prev_b'] = curr_b
            return "ENTERING"
        elif current_state['first_sensor'] is None:
            current_state['first_sensor'] = 'B'
            current_state['start_tick'] = time.ticks_ms()

    current_state['prev_a'] = curr_a
    current_state['prev_b'] = curr_b
    return None

print("Clean Function-Based Door Monitor Started...")

# Main Loop containing only conditionals
while True:
    keep_led_off(led)
    
    direction = evaluate_sensors(sensor_a, sensor_b, state)
    
    if direction == "ENTERING":
        state['people_count'] += 1
        print("Entering - People inside:", state['people_count'])
        state['empty_since_tick'] = None
        state['first_sensor'] = None  # Reset sequence
    elif direction == "LEAVING":
        if state['people_count'] > 0:
            state['people_count'] -= 1
            print("Leaving - People inside:", state['people_count'])
            if state['people_count'] == 0:
                print("Room is empty")
                state['empty_since_tick'] = time.ticks_ms()
        state['first_sensor'] = None  # Reset sequence

    if state['people_count'] == 0:
        if state['empty_since_tick'] is None:
            state['empty_since_tick'] = time.ticks_ms()
        elif time.ticks_diff(
            time.ticks_ms(), state['empty_since_tick']
        ) >= EMPTY_ALERT_SECONDS * 1000:
            print("\aALERT: Room has been empty for 45 seconds")
            state['empty_since_tick'] = time.ticks_ms()
    else:
        state['empty_since_tick'] = None