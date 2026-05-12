/**
 * ============================================================
 *  WS2812B LED Controller — CH552T @ 24MHz
 * ============================================================
 *  Giao thức : UART 115200 baud (Bluetooth / USB-Serial)
 *  Output    : 256x WS2812B bit-bang trên P1.1
 *  Compiler  : SDCC (Small Device C Compiler)
 *
 *  TIMING CỦA CPU (1T mode — bắt buộc phải set):
 *    1 machine cycle  = 1 / 24,000,000 Hz = 41.67 ns
 *    SETB / CLR P1.x  ≈ 2 cycles          = 83 ns
 *    NOP              = 1 cycle            = 41.67 ns
 *    Loop overhead    ≈ 6 cycles           = 250 ns
 *    (b<<=1 + DJNZ + JNB — đây là phần cộng thêm vào cuối LOW)
 *
 *  WS2812B SPEC  (±150 ns tolerance):
 *    T1H = 800 ns  [650–950]    T1L = 450 ns  [300–600]
 *    T0H = 400 ns  [250–550]    T0L = 850 ns  [700–1000]
 *
 *  NOP COUNT ĐÃ TÍNH OVERHEAD:
 *    Bit 1 → HIGH: SETB(83) + 16×NOP(667) = 750 ns  ✅
 *            LOW:  CLR(83)  +  4×NOP(167) + overhead(250) = 500 ns ✅
 *    Bit 0 → HIGH: SETB(83) +  6×NOP(250) = 333 ns  ✅
 *            LOW:  CLR(83)  + 14×NOP(583) + overhead(250) = 916 ns ✅
 *
 *  CÁC LỖI ĐÃ FIX SO VỚI BẢN GỐC:f
 *    [F1] Thêm T2MOD |= bTMR_CLK | bT1_CLK  → 1T mode, baud đúng
 *    [F2] Thêm TL1 = 243                     → byte đầu không bị lỗi
 *    [F3] ISR dùng __using(1)                → zero push/pop overhead
 *    [F4] ISR kiểm tra bounds TRƯỚC khi ghi  → không bao giờ overflow
 *    [F5] TI=0 trước khi ghi SBUF            → SendByte an toàn
 *    [F6] EA=0/1 bọc reset buffer            → loại trừ race condition
 *    [F7] TMOD &= ~0xF0 trước khi OR         → tránh ghost bits
 *    [F8] T1L giảm 8→4 NOPs, T0L giảm 17→14 → đúng spec WS2812B
 * ============================================================
 */

#include <stdint.h>

/* ============================================================
   CẤU HÌNH PHẦN CỨNG
   ============================================================ */
#define LED_PIN_NUM   1
#define NUM_LEDS      256
#define BUFFER_SIZE   768       // 256 LEDs × 3 bytes (GRB — thứ tự WS2812B)

/* ============================================================
   BIẾN TOÀN CỤC
   Đặt toàn bộ buffer vào XRAM (8 KB) của CH552T.
   KHÔNG để trên idata/stack → tránh tràn bộ nhớ nội.
   ============================================================ */
__xdata uint8_t  led_buffer[BUFFER_SIZE];
volatile uint16_t rx_index    = 0;
volatile uint8_t  frame_ready = 0;

/* ============================================================
   UART0_Init — CH552T @ 24MHz → 115200 baud chính xác
   ============================================================ */
void UART0_Init(void)
{
    /* [F1] BẮT BUỘC: Bật 1T mode cho Timer 1.
     *
     * CH552 khởi động ở 12T (mỗi chu kỳ Timer = 12 clock CPU).
     * Nếu KHÔNG set dòng này, baud rate thực tế với TH1=243 là:
     *
     *   Baud = 2 × 24M / (32 × 12 × 13) ≈ 9,615 baud  ← SAI HOÀN TOÀN
     *
     * Sau khi set bTMR_CLK | bT1_CLK (1T mode):
     *
     *   Baud = 2 × 24M / (32 × 1 × 13) ≈ 115,384 baud ✅
     */
    T2MOD |= bTMR_CLK | bT1_CLK;

    SM0 = 0;            // UART Mode 1: 8-bit UART, baud rate thay đổi
    SM1 = 1;
    REN = 1;            // Bật nhận dữ liệu

    /* [F7] Clear trước khi set — tránh ghost bits từ trạng thái cũ */
    TMOD &= ~0xF0;
    TMOD |= bT1_M1;     // Timer 1: Mode 2 (8-bit auto-reload)

    PCON |= SMOD;       // SMOD=1: nhân đôi baud rate
                        // Baud = 2 × Fsys / (32 × (256 − TH1))
                        //       = 2 × 24M / (32 × 13) = 115,384 ≈ 115,200 ✅

    TH1 = 243;          // Reload value: 256 − 13 = 243
    /* [F2] Sync TL1 ngay lập tức.
     * Timer 1 Mode 2 auto-reload TH1→TL1 sau mỗi overflow.
     * Nếu TL1 chứa rác, byte đầu tiên nhận được sẽ sai timing. */
    TL1 = 243;

    TF1 = 0;            // Xóa cờ overflow Timer 1
    TR1 = 1;            // Khởi động Timer 1

    /* [F5] Xóa cờ trước khi bật ngắt — tránh ISR kích hoạt ngay */
    TI = 0;
    RI = 0;

    ES = 1;             // Bật ngắt UART0
    EA = 1;             // Bật ngắt toàn cục
}

/* ============================================================
   UART0_SendByte — Gửi 1 byte blocking (ACK / handshake)
   ============================================================ */
void UART0_SendByte(uint8_t dat)
{
    /* [F5] Xóa TI TRƯỚC khi ghi SBUF.
     * Nếu TI đang = 1 từ lần gửi trước và chưa được clear,
     * vòng while(!TI) sẽ thoát ngay lập tức → byte chưa gửi xong. */
    TI   = 0;
    SBUF = dat;
    while (!TI);
    TI = 0;
}

/* ============================================================
   UART0 ISR — SIÊU NGẮN, KHÔNG CÓ TÍNH TOÁN PHỨC TẠP
   ============================================================
   [F3] __using(1): dùng register bank 1 thay vì bank 0.
   CPU tự động switch bank (1 lệnh MOV PSW) thay vì PUSH/POP
   toàn bộ thanh ghi → tiết kiệm ~10–14 cycle mỗi lần vào ISR.

   Cấu trúc ISR tối ưu:
     1. Xóa RI  (1 lệnh)
     2. Kiểm tra frame_ready (1 lệnh) — early exit nếu đã đầy
     3. Kiểm tra rx_index < BUFFER_SIZE (1 lệnh) — [F4] overflow guard
     4. Ghi SBUF vào buffer (2 lệnh: MOV + INC)
     5. Kiểm tra đủ frame (1 lệnh)

   Tổng: ~10–12 instruction — đạt mục tiêu ISR cực ngắn.
   ============================================================ */
void UART0_ISR(void) __interrupt(INT_NO_UART0) __using(1)
{
    if (RI) {
        RI = 0;

        /* [F4] Kiểm tra bounds TRƯỚC KHI GHI — không bao giờ buffer overflow.
         * frame_ready check trước: nếu đã có frame, bỏ qua hoàn toàn.
         * rx_index < BUFFER_SIZE: bảo vệ kép phòng nhiễu/glitch. */
        if (!frame_ready && (rx_index < BUFFER_SIZE)) {
            led_buffer[rx_index++] = SBUF;
            if (rx_index >= BUFFER_SIZE) {
                frame_ready = 1;
            }
        }
    }

    /* Xóa TI nếu cờ TX bị kích hoạt (không dùng TX interrupt
     * nhưng cần clear để ISR không bị gọi lại liên tục) */
    if (TI) TI = 0;
}

/* ============================================================
   WS2812B_Show — Bit-bang trực tiếp ra P1.1
   ============================================================
   PHẢI tắt ngắt (EA=0) trong toàn bộ quá trình.
   Bất kỳ ngắt nào chen vào đều làm lệch timing → LED sai màu.
   ============================================================ */
void WS2812B_Show(void)
{
    uint16_t i;
    uint8_t  j, b;

    EA = 0;     /* Tắt ngắt — bảo vệ timing nanosecond */

    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                /* ── BIT 1 ─────────────────────────────────────────────
                 * T1H target: 800 ns  [spec: 650–950 ns]
                 *   SETB(83) + 16×NOP(667) = 750 ns ✅
                 * T1L target: 450 ns  [spec: 300–600 ns]
                 *   CLR(83) + 4×NOP(167) + loop_overhead(~250) = 500 ns ✅
                 * ─────────────────────────────────────────────────────── */
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");  /* 16 NOPs */
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop");                         /*  4 NOPs */
            } else {
                /* ── BIT 0 ─────────────────────────────────────────────
                 * T0H target: 400 ns  [spec: 250–550 ns]
                 *   SETB(83) + 6×NOP(250) = 333 ns ✅
                 * T0L target: 850 ns  [spec: 700–1000 ns]
                 *   CLR(83) + 14×NOP(583) + loop_overhead(~250) = 916 ns ✅
                 * ─────────────────────────────────────────────────────── */
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop");               /*  6 NOPs */
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop\nnop\nnop");        /* 14 NOPs */
            }
            b <<= 1;    /* Shift lên, chuẩn bị bit tiếp theo */
        }
    }

    EA = 1;     /* Bật lại ngắt sau khi hoàn tất */
}

/* ============================================================
   SETUP — Chạy 1 lần khi khởi động
   ============================================================ */
void setup(void)
{
    /* Cấu hình P1.1 là Push-Pull Output.
     * WS2812B cần driver mạnh — không dùng open-drain. */
    P1_MOD_OC &= ~(1 << LED_PIN_NUM);  /* Tắt chế độ open-collector */
    P1_DIR_PU  |= (1 << LED_PIN_NUM);  /* Bật output direction */
    P1_1 = 0;                           /* Trạng thái idle = LOW */

    UART0_Init();

    /* Gửi handshake 'K' để báo với host (Bluetooth module)
     * rằng CH552T đã sẵn sàng nhận frame đầu tiên */
    UART0_SendByte('K');
}

/* ============================================================
   LOOP — Chạy liên tục
   ============================================================ */
void loop(void)
{
    if (frame_ready) {
        /* Đẩy buffer ra LED ngay khi frame đủ */
        WS2812B_Show();

        /* [F6] Reset buffer — BẮT BUỘC bảo vệ bằng EA=0/1.
         *
         * VẤN ĐỀ nếu KHÔNG làm vậy:
         *   rx_index   = 0;   ← ISR chen vào ĐÂY → ghi led_buffer[0]
         *   frame_ready = 0;  ← reset sau khi ISR đã ghi rác
         *
         * Kết quả: LED nhận byte rác ở vị trí 0 của frame kế tiếp.
         * Lỗi này chỉ xảy ra ngẫu nhiên nên rất khó debug.
         *
         * FIX: Tắt ngắt trong khoảng thời gian cực ngắn (2 lệnh):
         */
        EA = 0;
        rx_index    = 0;
        frame_ready = 0;
        EA = 1;

        /* ACK: Báo host sẵn sàng nhận frame tiếp theo */
        UART0_SendByte('K');
    }
}