import time
import serial

port = "COM5"

for baud in [921600, 115200]:
    print(f"\n--- Testing COM5 @ {baud} baud ---")
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=1.0)
        # Avoid DTR/RTS auto-reset
        ser.dtr = False
        ser.rts = False
        time.sleep(0.5)
        
        # Read available bytes for 2.0 seconds
        start = time.time()
        lines = []
        raw_bytes_count = 0
        buf = ""
        while time.time() - start < 2.5:
            in_w = ser.in_waiting
            if in_w > 0:
                data = ser.read(in_w)
                raw_bytes_count += len(data)
                buf += data.decode("ascii", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        lines.append(line)
            time.sleep(0.05)
            
        ser.close()
        print(f"Baud {baud}: Cleanly opened and closed. Bytes received: {raw_bytes_count}, Complete lines: {len(lines)}")
        if lines:
            print("First 5 lines:")
            for l in lines[:5]:
                print(f"  {l[:100]}...")
    except Exception as e:
        print(f"Baud {baud} failed: {e}")
