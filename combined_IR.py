from machine import Pin
import time

# Hardware Setup
sensor_a = Pin(11, Pin.IN, Pin.PULL_UP)
sensor_b = Pin(10, Pin.IN, Pin.PULL_UP)
led = Pin("LED", Pin.OUT)

# State Variables
state = {
    'first_sensor': None,
    'start_tick': 0,
    'prev_a': sensor_a.value(),
    'prev_b': sensor_b.value(),
    'timeout_ms': 1000
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
    
    current_state['first_sensor'] = check_timeout(
        current_state['first_sensor'], 
        current_state['start_tick'], 
        current_state['timeout_ms']
    )
    
    # Detect Sensor A Trigger (1 -> 0)
    if check_edge_transition(curr_a, current_state['prev_a']):
        if current_state['first_sensor'] == 'B':
            current_state['prev_a'] = curr_a
            current_state['prev_b'] = curr_b
            return "LEAVING"
        elif current_state['first_sensor'] is None:
            current_state['first_sensor'] = 'A'
            current_state['start_tick'] = time.ticks_ms()

    # Detect Sensor B Trigger (1 -> 0)
    if check_edge_transition(curr_b, current_state['prev_b']):
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
        print("Entering")
        state['first_sensor'] = None  # Reset sequence
    elif direction == "LEAVING":
        print("Leaving")
        state['first_sensor'] = None  # Reset sequence