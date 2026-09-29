#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>

/*
 * spitest.c: Low-level SPI-NAND hardware controller diagnostic
 * Directly interacts with the hardware SPI controller registers to
 * issue READID, page read, and cache read commands to verify on-die SPI-NAND
 * functionality independently of MTD kernel drivers.
 */

#define SPIFC_BASE 0x94406000
#define SPIFC_SIZE 0x1000

#define SPIFC_TRIGGER     0x04
#define SPIFC_ACK         0x08
#define SPIFC_XFER_CFG    0x0c
#define SPIFC_FMT0        0x10
#define SPIFC_FMT1        0x14
#define SPIFC_LEN         0x18
#define SPIFC_ADDR        0x1c
#define SPIFC_OPCODE      0x20
#define SPIFC_REG24       0x24
#define SPIFC_STATUS      0x2c
#define SPIFC_BURST       0x30
#define SPIFC_FIFO_STATUS 0x34
#define SPIFC_FIFO_DATA   0x38

static volatile uint32_t *base;

static inline uint32_t r32(uint32_t off) { return *(volatile uint32_t *)((char *)base + off); }
static inline void w32(uint32_t off, uint32_t val) { *(volatile uint32_t *)((char *)base + off) = val; }

static void controller_ack(void) {
    uint32_t a = r32(SPIFC_ACK);
    if (!(a & 2)) {
        w32(SPIFC_ACK, a | 1);
    }
}

static void ack_and_trigger(void) {
    controller_ack();
    w32(SPIFC_XFER_CFG, r32(SPIFC_XFER_CFG) | 0x1c440);
    w32(SPIFC_BURST, 0x3f);
    w32(SPIFC_TRIGGER, r32(SPIFC_TRIGGER) | 1);
}

static int wait_done(int timeout_us) {
    while (timeout_us > 0) {
        if (r32(SPIFC_STATUS) & 1) return 0;
        usleep(5);
        timeout_us -= 5;
    }
    return -1;
}

static void drain_fifo(uint32_t *buf, int words) {
    for (int i = 0; i < words; i++) {
        for (int p = 0; p < 20000; p++) {
            if (r32(SPIFC_FIFO_STATUS) & 0x1f00) break;
            usleep(1);
        }
        buf[i] = r32(SPIFC_FIFO_DATA);
    }
}

static void exec_cmd(uint8_t op, uint32_t fmt0, uint32_t fmt1, uint32_t len, uint32_t addr) {
    controller_ack();
    w32(SPIFC_OPCODE, op);
    w32(SPIFC_FMT0, fmt0);
    w32(SPIFC_FMT1, fmt1);
    w32(SPIFC_LEN, len);
    w32(SPIFC_ADDR, addr);
    ack_and_trigger();
}

static uint8_t get_feature(uint8_t reg) {
    exec_cmd(0x0f, 0x12, 0x0, 0, reg);
    wait_done(5000);
    uint32_t d = r32(SPIFC_FIFO_DATA);
    controller_ack();
    return d & 0xff;
}

static void wait_oip_clear(void) {
    for (int i = 0; i < 2000; i++) {
        uint8_t st = get_feature(0xc0);
        if (!(st & 1)) {
            return;
        }
        usleep(50);
    }
    printf("WARNING: wait_oip_clear timeout!\n");
}

static void print_hex(const char *label, uint8_t *b, int len) {
    printf("%s (%d bytes):\n", label, len);
    for (int i = 0; i < len; i += 16) {
        printf("%04x: ", i);
        for (int j = 0; j < 16; j++) {
            if (i + j < len) printf("%02x ", b[i + j]);
            else printf("   ");
        }
        printf(" ");
        for (int j = 0; j < 16; j++) {
            if (i + j < len) printf("%c", (b[i + j] >= 32 && b[i + j] < 127) ? b[i + j] : '.');
        }
        printf("\n");
    }
}

static void test_read(const char *name, uint8_t op, uint32_t fmt0, uint32_t fmt1, uint32_t page, int len) {
    printf("\n=== Testing %s (op=0x%02x, FMT0=0x%x, FMT1=0x%x, len=%d) ===\n", name, op, fmt0, fmt1, len);

    controller_ack();
    w32(SPIFC_OPCODE, 0x13);
    w32(SPIFC_FMT0, 0x10);
    w32(SPIFC_FMT1, 0x40);
    w32(SPIFC_LEN, 0);
    w32(SPIFC_ADDR, page);
    ack_and_trigger();
    int r = wait_done(10000);
    if (r < 0) printf("PAGE_READ wait_done failed!\n");
    controller_ack();
    wait_oip_clear();

    uint32_t words[128] = {0};
    int nwords = (len + 3) / 4;

    controller_ack();
    w32(SPIFC_OPCODE, op);
    w32(SPIFC_FMT0, fmt0);
    w32(SPIFC_FMT1, fmt1);
    w32(SPIFC_LEN, len - 1);
    w32(SPIFC_ADDR, 0);
    ack_and_trigger();

    drain_fifo(words, nwords);
    r = wait_done(10000);
    controller_ack();
    printf("READ wait_done=%d, status=0x%08x\n", r, r32(SPIFC_STATUS));

    print_hex(name, (uint8_t *)words, len);
}

int main(int argc, char **argv) {
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("open /dev/mem"); return 1; }
    base = mmap(NULL, SPIFC_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, SPIFC_BASE);
    if (base == MAP_FAILED) { perror("mmap"); return 1; }

    printf("SPIFC reg 0x24 before: 0x%08x\n", r32(SPIFC_REG24));
    w32(SPIFC_REG24, (r32(SPIFC_REG24) & ~0x30000) | 0x10000);
    printf("SPIFC reg 0x24 after:  0x%08x\n", r32(SPIFC_REG24));

    exec_cmd(0x9f, 0x12, 0x0, 4, 0);
    wait_done(5000);
    uint32_t id0 = r32(SPIFC_FIFO_DATA);
    uint32_t id1 = r32(SPIFC_FIFO_DATA);
    controller_ack();
    printf("READID: 0x%08x 0x%08x (mfg: 0x%02x, dev: 0x%02x)\n", id0, id1, id0 & 0xff, (id0 >> 8) & 0xff);

    uint32_t page = 0x14c0;
    if (argc > 1) page = strtoul(argv[1], NULL, 0);

    test_read("Single SPI (0x03, FMT1=0x1020)", 0x03, 0x16, 0x1020, page, 64);
    test_read("Dual SPI (0x3b, FMT1=0x1024)", 0x3b, 0x16, 0x1024, page, 64);
    test_read("Dual SPI 256B (0x3b, FMT1=0x1024)", 0x3b, 0x16, 0x1024, page, 256);

    munmap((void *)base, SPIFC_SIZE);
    close(fd);
    return 0;
}
