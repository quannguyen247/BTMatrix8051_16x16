import socket
import time
import sys

# ── Cấu hình ──
HC05_MAC = "00:25:11:02:85:B9"
BT_PORT = 1
BUFFER_SIZE = 768
CHUNK_SIZE = 64
TIMEOUT_SEC = 5.0

def wait_for_ack(sock, label):
	"""Hàm chờ tín hiệu 'K' từ vi điều khiển"""
	print(f"[*] Đang chờ ACK ({label})... ", end="", flush=True)
	start = time.time()
	while True:
		try:
			if sock.recv(1) == b'K':
				print("OK!")
				return True
		except socket.timeout:
			pass
		if time.time() - start > TIMEOUT_SEC:
			print("TIMEOUT!")
			return False

def send_frame_precise(sock, frame_bytes):
	"""Hàm gửi data băm nhỏ 64 byte + delay 2ms (Timing cực chuẩn)"""
	sent = 0
	while sent < BUFFER_SIZE:
		end = min(sent + CHUNK_SIZE, BUFFER_SIZE)
		sock.send(frame_bytes[sent:end])
		sent = end
		time.sleep(0.002) # Bí quyết chống tràn buffer HC-05

def main():
	# Tạo socket native kết nối thẳng vào MAC
	print(f"[*] Đang kết nối Bluetooth tới {HC05_MAC}...")
	sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
	sock.settimeout(TIMEOUT_SEC)
	
	try:
		sock.connect((HC05_MAC, BT_PORT))
		print("[+] Kết nối phần cứng thành công!")
	except Exception as e:
		sys.exit(f"[-] Lỗi kết nối: {e}")

	# Chờ MCU báo cáo khởi động xong
	if not wait_for_ack(sock, "Boot Ready"):
		sock.close()
		return

	# Tạo sẵn 3 mảng byte màu (Định dạng WS2812B là G-R-B, độ sáng 15/255 để tránh sụt nguồn)
	frame_red = bytes([0, 15, 0] * 256)   # Đỏ
	frame_green = bytes([15, 0, 0] * 256) # Xanh lá
	frame_blue = bytes([0, 0, 15] * 256)  # Xanh dương

	test_colors = [
		("ĐỎ", frame_red),
		("XANH LÁ", frame_green),
		("XANH DƯƠNG", frame_blue)
	]

	idx = 0
	print("\n[*] BẮT ĐẦU STREAM DATA...")
	try:
		while True:
            # Lấy màu hiện tại
			color_name, frame_data = test_colors[idx % 3]
			print(f"[>] Đang gửi mã màu: {color_name}...")
			
			# Bắn data xuống
			send_frame_precise(sock, frame_data)
			
			# Chờ MCU xuất LED xong rồi vẫy cờ 'K'
			if not wait_for_ack(sock, "Display Done"):
				print("[-] Mất đồng bộ, đang thử lại...")
			
			idx += 1
			time.sleep(1) # Delay 1s để mắt người kịp nhìn thấy đổi màu

	except KeyboardInterrupt:
		print("\n[*] Đã dừng test.")
	finally:
		sock.close()
		print("[*] Đóng socket an toàn.")

if __name__ == "__main__":
	main()