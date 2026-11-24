from machine import Pin
import time
import Current

TIMEOUT_SECONDS = 1
EMPTY_ALERT_SECONDS = 30
DEBOUNCE_MS = 50
EVENT_COOLDOWN_MS = 500

# Hardware Setup (kept from project.py: A=14, B=15)
sensor_a = Pin(14, Pin.IN, Pin.PULL_UP)
sensor_b = Pin(15, Pin.IN, Pin.PULL_UP)
led = Pin("LED", Pin.OUT)

state = {
    'first_sensor': None,
    'start_tick': 0,
    'last_a_tick': 0,
    'last_b_tick': 0,
    'timeout_ms': TIMEOUT_SECONDS * 1000,
    'people_count': 0,
    'empty_since_tick': None,
    'alert_count': 0,
    'last_print_tick': 0,
    'event': None,
    'last_event_tick': 0,
    'timer_active': False,
    'timer_print_step': 10,
    'timer_completed': False
}

def keep_led_off(led_pin):
    led_pin.value(0)

def handle_sensor_interrupt(pin):
    now = time.ticks_ms()

    if state['first_sensor'] is not None:
        if time.ticks_diff(now, state['start_tick']) > state['timeout_ms']:
            state['first_sensor'] = None

    if pin is sensor_a:
        sensor_name = 'A'
        last_tick_name = 'last_a_tick'
    else:
        sensor_name = 'B'
        last_tick_name = 'last_b_tick'

    if time.ticks_diff(now, state[last_tick_name]) < DEBOUNCE_MS:
        return
    state[last_tick_name] = now

    first_sensor = state['first_sensor']
    if first_sensor is None:
        state['first_sensor'] = sensor_name
        state['start_tick'] = now
        return

    if first_sensor == sensor_name:
        return

    if state['event'] is None:
        if time.ticks_diff(now, state['last_event_tick']) >= EVENT_COOLDOWN_MS:
            if first_sensor == 'A' and sensor_name == 'B':
                state['event'] = "ENTERING"
                state['last_event_tick'] = now
            elif first_sensor == 'B' and sensor_name == 'A':
                state['event'] = "LEAVING"
                state['last_event_tick'] = now

    state['first_sensor'] = None

sensor_a.irq(trigger=Pin.IRQ_FALLING, handler=handle_sensor_interrupt)
sensor_b.irq(trigger=Pin.IRQ_FALLING, handler=handle_sensor_interrupt)

def process_event(direction):
    if direction == "ENTERING":
        state['people_count'] += 1
        print("Entering - People inside:", state['people_count'])
        state['empty_since_tick'] = None
        state['alert_count'] = 0
        state['timer_active'] = False
        state['timer_print_step'] = 10
        state['timer_completed'] = False
    elif direction == "LEAVING":
        if state['people_count'] > 0:
            state['people_count'] -= 1
            print("Leaving - People inside:", state['people_count'])
            if state['people_count'] == 0:
                print("Room is empty")
                state['empty_since_tick'] = time.ticks_ms()
                state['alert_count'] = 0
                state['timer_active'] = True
                state['timer_print_step'] = 10
                state['timer_completed'] = False
        else:
            print("Ignoring exit: room is already empty")

def update_empty_timer(now):
    if state['people_count'] != 0:
        state['empty_since_tick'] = None
        state['alert_count'] = 0
        state['timer_active'] = False
        state['timer_print_step'] = 10
        return

    if state['timer_completed']:
        return

    if state['empty_since_tick'] is None:
        state['empty_since_tick'] = now
        state['timer_active'] = True

    if not state['timer_active']:
        return

    elapsed_ms = time.ticks_diff(now, state['empty_since_tick'])
    elapsed_sec = elapsed_ms // 1000
    print_step = state['timer_print_step']

    if elapsed_sec >= print_step and print_step < EMPTY_ALERT_SECONDS:
        print(f"Room empty timer: {print_step}s")
        state['timer_print_step'] += 10

    if elapsed_ms >= EMPTY_ALERT_SECONDS * 1000:
        print("\aALERT: Room has been empty for 30 seconds")
        state['timer_active'] = False
        state['empty_since_tick'] = None
        state['timer_completed'] = True

print("Door Monitor Started...")

def main():
    Current.init_current_sensor()
    last_current_send_tick = time.ticks_ms()

    while True:
        keep_led_off(led)
        now = time.ticks_ms()

        if state['event'] is not None:
            direction = state['event']
            state['event'] = None
            process_event(direction)

        update_empty_timer(now)

        if time.ticks_diff(now, last_current_send_tick) >= 1000:
            payload = Current.read_current()
            Current.print_current_text(payload)
            Current.print_current_json(payload)
            last_current_send_tick = now

        time.sleep_ms(10)

if __name__ == "__main__":
    main()