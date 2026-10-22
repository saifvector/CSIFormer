import serial
import time

def read_serial_boot(port='COM5', baud=115200, duration=8):
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        print(f"Failed to open {port} at {baud}: {e}")
        return

    print(f"Resetting {port} and capturing logs at {baud} baud for {duration} seconds...")
    ser.dtr = False
    ser.rts = True
    time.sleep(0.1)
    ser.rts = False
    time.sleep(0.1)

    t_end = time.time() + duration
    output = []
    while time.time() < t_end:
        line = ser.readline()
        if line:
            text = line.decode('utf-8', errors='replace')
            output.append(text)
            print(text, end='', flush=True)

    ser.close()
    return "".join(output)

if __name__ == '__main__':
    read_serial_boot('COM5', 115200, 8)
