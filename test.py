import socket
import wave

def get_local_ip():
    """
    Returns the local IP address of the machine.
    Uses a UDP socket to "connect" to an external host (Google DNS)
    to determine the correct local interface.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # This connection doesn't send data; it simply forces the OS
            # to select an outbound interface.
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
    except Exception as e:
        print("Could not determine IP address:", e)
        ip_address = "127.0.0.1"
    return ip_address

# Server settings
HOST = ''  # Listen on all interfaces
PORT = 5000  # Must match the port set in the ESP32 code

# WAV file settings (must match the ESP32 output)
CHANNELS = 1       # Mono audio
SAMPLE_WIDTH = 2   # 16-bit PCM (2 bytes)
FRAME_RATE = 44100

def main():
    # Print the local IP address so you know where to connect the ESP32.
    local_ip = get_local_ip()
    print("Server local IP address is:", local_ip)
    print(f"Starting server on port {PORT}...\n")

    # Create a TCP socket and bind to the desired port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"Server listening on port {PORT}...")

        # Wait for the ESP32 to connect.
        conn, addr = s.accept()
        with conn:
            print(f"\nConnection accepted from {addr}")
            data_bytes = bytearray()
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data_bytes.extend(chunk)
                print(f"Received chunk of {len(chunk)} bytes (total so far: {len(data_bytes)} bytes)")
            print(f"\nTotal received audio data: {len(data_bytes)} bytes")

    # Write the received data into a WAV file.
    wav_filename = "recording.wav"
    with wave.open(wav_filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(FRAME_RATE)
        wf.writeframes(data_bytes)

    print(f"\nWAV file saved as '{wav_filename}'.")

if __name__ == "__main__":
    main()
