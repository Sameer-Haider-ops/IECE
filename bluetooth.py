import bluetooth
import struct
import time
from machine import Pin
from micropython import const

# BLE IRQ event constants
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)

# GATT characteristic flags
_FLAG_READ = const(0x0002)
_FLAG_NOTIFY = const(0x0010)

# Advertising data types
_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x03)

# Custom UART-style service and TX characteristic UUIDs (16-bit for compact advertising)
_UART_SERVICE_UUID = bluetooth.UUID(0x181C)
_UART_TX_CHAR_UUID = bluetooth.UUID(0x2A56)

_UART_SERVICE = (
    _UART_SERVICE_UUID,
    ((_UART_TX_CHAR_UUID, _FLAG_READ | _FLAG_NOTIFY),),
)

DEVICE_NAME = "Pico-Msg"
led = Pin("LED", Pin.OUT)


def build_adv_payload(name, service_uuid_16):
    payload = bytearray()
    # Flags: LE General Discoverable Mode + BR/EDR Not Supported
    payload += struct.pack("BB", 2, _ADV_TYPE_FLAGS) + bytes([0x06])
    # Complete 16-bit Service UUID
    uuid_bytes = bytes(service_uuid_16)
    payload += struct.pack("BB", 1 + len(uuid_bytes), _ADV_TYPE_UUID16_COMPLETE) + uuid_bytes
    # Complete Local Name
    name_bytes = name.encode("utf-8")
    payload += struct.pack("BB", 1 + len(name_bytes), _ADV_TYPE_NAME) + name_bytes
    return payload


class BLEMessenger:
    def __init__(self, name=DEVICE_NAME):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        ((self._tx_handle,),) = self._ble.gatts_register_services((_UART_SERVICE,))
        self._connections = set()
        self._adv_payload = build_adv_payload(name, _UART_SERVICE_UUID)
        self._advertise()

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            led.on()
            print(f"Connected (handle={conn_handle}). Type a message and press Enter:")
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            led.off()
            print("Disconnected. Re-advertising...")
            self._advertise()

    def _advertise(self, interval_us=250000):
        self._ble.gap_advertise(None)
        self._ble.gap_advertise(interval_us, adv_data=self._adv_payload)

    @property
    def is_connected(self):
        return len(self._connections) > 0

    def send_message(self, text):
        # BLE ATT notifications are typically ~20 bytes default unless MTU is negotiated;
        # chunk long strings so nothing is silently truncated.
        raw = text.encode("utf-8")
        chunk_size = 20
        for i in range(0, len(raw), chunk_size):
            chunk = raw[i : i + chunk_size]
            for conn_handle in list(self._connections):
                self._ble.gatts_write(self._tx_handle, chunk)
                self._ble.gatts_notify(conn_handle, self._tx_handle)
        print(f"Sent over BLE: {text}")


def main():
    messenger = BLEMessenger(DEVICE_NAME)
    print(f"Advertising '{DEVICE_NAME}' over BLE... Connect with a BLE app (e.g., LightBlue or nRF Connect).")

    while True:
        if not messenger.is_connected:
            time.sleep_ms(200)
            continue

        try:
            user_text = input("> ")
        except EOFError:
            time.sleep_ms(100)
            continue

        cleaned = user_text.strip()
        if not cleaned:
            continue

        if cleaned.lower() == "quit":
            print("Stopping...")
            break

        messenger.send_message(user_text)


if __name__ == "__main__":
    main()