from machine import ADC, Pin
import utime

try:
    import ujson
except ImportError:
    import json as ujson

ADC_PIN = const(28)
VREF = 3.3
ADC_MAX = 65535
VOLTS_PER_ADC = VREF / ADC_MAX
LOAD_RESISTANCE = 40.0

SAMPLE_COUNT = const(16)
CALIBRATION_SECONDS = const(3)
CALIBRATION_SAMPLE_COUNT = const(500)
CALIBRATION_INTERVAL_MS = const(6)
BASELINE_MARGIN = const(100)
GROUND_ADC_LIMIT = const(2000)
CLASSIFY_INTERVAL_MS = const(1000)

adc = None
adc_zero = 0
baseline_range = 0
calibrated = False


def init_current_sensor():
    global adc, adc_zero, baseline_range, calibrated

    adc_pin = Pin(ADC_PIN, Pin.IN, Pin.PULL_DOWN)
    adc = ADC(adc_pin)

    print("Calibration: keep the load OFF for 3 seconds...")
    samples = []

    for sample in range(CALIBRATION_SAMPLE_COUNT):
        samples.append(adc.read_u16())
        utime.sleep_ms(CALIBRATION_INTERVAL_MS)

        if (sample + 1) % 100 == 0:
            remaining = CALIBRATION_SECONDS - (
                ((sample + 1) * CALIBRATION_INTERVAL_MS) // 1000
            )
            print("Calibrating... {}s remaining".format(max(0, remaining)))

    samples.sort()
    adc_zero = samples[len(samples) // 2]

    deviations = []
    for reading in samples:
        deviations.append(abs(reading - adc_zero))
    deviations.sort()
    baseline_range = deviations[len(deviations) // 2] + BASELINE_MARGIN
    calibrated = True

    print(
        "Calibration complete | ADC zero:",
        adc_zero,
        "| Baseline range:",
        baseline_range,
    )


def read_current():
    if adc is None:
        raise RuntimeError("Call init_current_sensor() before read_current()")

    total = 0
    for _ in range(SAMPLE_COUNT):
        total += adc.read_u16()
    raw_adc = total // SAMPLE_COUNT

    if raw_adc >= adc_zero:
        calibrated_adc = raw_adc - adc_zero
    else:
        calibrated_adc = 0

    noise_limit = max(baseline_range, GROUND_ADC_LIMIT)
    if calibrated_adc <= noise_limit:
        calibrated_adc = 0

    voltage_v = calibrated_adc * VOLTS_PER_ADC
    current_ma = (voltage_v / LOAD_RESISTANCE) * 1000.0

    if current_ma < 0:
        current_ma = 0.0

    return {
        "voltage_v": round(voltage_v, 4),
        "current_ma": round(current_ma, 1),
    }


def print_current_text(payload=None):
    if payload is None:
        payload = read_current()
    print(
        "Vsense: {:.4f} V | Current: {:.1f} mA".format(
            payload["voltage_v"],
            payload["current_ma"],
        )
    )


def print_current_json(payload=None):
    if payload is None:
        payload = read_current()
    print(ujson.dumps(payload))


def main():
    init_current_sensor()

    last_print_tick = utime.ticks_ms()

    while True:
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_print_tick) >= CLASSIFY_INTERVAL_MS:
            payload = read_current()
            print_current_text(payload)
            print_current_json(payload)
            last_print_tick = now

        utime.sleep_ms(10)


if __name__ == "__main__":
    main()
