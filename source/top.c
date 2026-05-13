#include <stdint.h>

#define LED_PIN 1
#define NUM_LEDS 256
#define BUFFER_SIZE 768

__xdata uint8_t led_buffer[BUFFER_SIZE];
__data uint16_t i;
__data uint8_t b, j;

void delay_ms(uint16_t ms) {
	uint16_t x, y;
	for (x = 0; x < ms; x++)
		for (y = 0; y < 2000; y++) __asm__("nop");
}

void UART0_Init(void) {
	T2MOD |= bTMR_CLK | bT1_CLK;
	TMOD &= ~0xF0;
	TMOD |= bT1_M1;
	PCON |= SMOD;
	TH1 = 243; TL1 = 243;
	TF1 = 0; TR1 = 1;

	SM0 = 0; SM1 = 1;
	REN = 1;
	TI = 0; RI = 0;

	// Cấu hình IO: P3.1 (TXD0) là Output, P3.0 (RXD0) là Input
	P3_MOD_OC &= ~(1 << 1);
	P3_DIR_PU |= (1 << 1);
	P3_MOD_OC |= (1 << 0);
	P3_DIR_PU &= ~(1 << 0);

	ES = 0; // Pure polling, cấm ngắt UART
	EA = 1;
}

void UART0_SendByte(uint8_t dat) {
	TI = 0;
	SBUF = dat;
	while (!TI);
	TI = 0;
}

// ─── Pure Polling HC-05 ──────────────────────────────────────────────────────
uint16_t receiveBluetoothFrame(void) {
	uint16_t rx_k = 0;
	uint32_t guard = 0;

	// Xóa cờ rác trước khi nhận frame mới
	RI = 0; 

	// 1. Chờ byte đầu tiên (Blocking vô hạn tới khi PC bắt đầu stream)
	while (!RI);
	RI = 0;
	led_buffer[rx_k++] = SBUF;

	// 2. Kéo liên tục 767 bytes còn lại
	while (rx_k < BUFFER_SIZE) {
		if (RI) {
			RI = 0;
			led_buffer[rx_k++] = SBUF;
			guard = 0; // Reset timeout khi có data
		} else {
			// Timeout guard: HC-05 có thể bị khựng nhẹ giữa các packet Bluetooth.
			// 1 byte @ 115200 mất ~87us. Đặt timeout ~20ms để tránh đứt gãy oan.
			if (++guard > 200000U) break; 
		}
	}
	return rx_k;
}

void WS2812B_Show(void) {
	EA = 0;
	for (i = 0; i < BUFFER_SIZE; i++) {
		b = led_buffer[i];
		for (j = 0; j < 8; j++) {
			if (b & 0x80) {
				P1_1 = 1;
				__asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
				P1_1 = 0;
				__asm__("nop\nnop");
			} else {
				P1_1 = 1;
				__asm__("nop\nnop\nnop\nnop\nnop");
				P1_1 = 0;
				__asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
			}
			b <<= 1;
		}
	}
	P1_1 = 0;
	delay_ms(1); // Tránh glitch latch tín hiệu
	EA = 1;
}

void setup() {
	SAFE_MOD = 0x55;
	SAFE_MOD = 0xAA;
	CLOCK_CFG = 0x06;
	SAFE_MOD = 0x00;

	P1_MOD_OC &= ~(1 << LED_PIN);
	P1_DIR_PU |= (1 << LED_PIN);
	P1_1 = 0;
	delay_ms(50);

	UART0_Init();
	
	// Gửi tín hiệu báo cho PC biết MCU đã sẵn sàng nhận frame đầu tiên
	UART0_SendByte('K');
}

void loop() {
	// Hàm này sẽ block cho tới khi nhận được ít nhất 1 byte
	uint16_t received = receiveBluetoothFrame();

	if (received == BUFFER_SIZE) {
		// ✅ Nhận trọn vẹn 1 Frame (768 bytes) từ HC-05
		WS2812B_Show();
		
		// Gửi mã 'K' (Acknowledge) về cho PC để PC xả Frame tiếp theo (Handshake)
		UART0_SendByte('K');

	} else {
		// ❌ Frame bị đứt gãy hoặc timeout. 
		// Không gọi hàm show để tránh nháy màn hình, gửi 'E' yêu cầu PC gửi lại
		UART0_SendByte('E');
	}
}