#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

/*
 * tcp_dump.c: Stream a block device or partition directly to a listening TCP socket.
 * Useful for fast network partition backups from stripped vendor environments.
 * Usage: tcp_dump <file_or_dev> <host_ip> <port>
 */
int main(int argc, char *argv[]) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s <file_or_dev> <host_ip> <port>\n", argv[0]);
        return 1;
    }
    const char *path = argv[1];
    const char *host = argv[2];
    int port = atoi(argv[3]);

    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        perror("open");
        return 1;
    }

    int s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) {
        perror("socket");
        close(fd);
        return 1;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, host, &addr.sin_addr);

    if (connect(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect");
        close(s);
        close(fd);
        return 1;
    }

    char buf[65536];
    ssize_t n;
    size_t total = 0;
    while ((n = read(fd, buf, sizeof(buf))) > 0) {
        ssize_t sent = 0;
        while (sent < n) {
            ssize_t w = write(s, buf + sent, n - sent);
            if (w <= 0) {
                perror("write");
                break;
            }
            sent += w;
        }
        total += n;
    }

    fprintf(stderr, "Dumped %zu bytes from %s to %s:%d\n", total, path, host, port);
    close(s);
    close(fd);
    return 0;
}
