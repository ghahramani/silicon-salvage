#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

/*
 * rwmem: Direct physical address reader and writer via /dev/mem
 * Usage:
 *   rwmem <hex_addr>               # Read 32-bit word at hex_addr
 *   rwmem <hex_addr> <hex_value>   # Write 32-bit hex_value to hex_addr
 */
int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <hex_addr> [hex_val]\n", argv[0]);
        return 1;
    }
    off_t addr = strtoul(argv[1], NULL, 16);
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) {
        perror("open /dev/mem");
        return 1;
    }

    size_t pagesize = sysconf(_SC_PAGE_SIZE);
    off_t page_base = (addr / pagesize) * pagesize;
    off_t page_offset = addr - page_base;

    void *map = mmap(NULL, pagesize, PROT_READ | PROT_WRITE, MAP_SHARED, fd, page_base);
    if (map == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return 1;
    }

    volatile unsigned int *ptr = (volatile unsigned int *)((char *)map + page_offset);
    if (argc == 2) {
        printf("0x%08x\n", *ptr);
    } else {
        *ptr = strtoul(argv[2], NULL, 16);
    }

    munmap(map, pagesize);
    close(fd);
    return 0;
}
