#define _POSIX_C_SOURCE 200809L
#include "cfv_mono_control_server.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static void request(cfv_mono_control *control, const char *line,
                    int expected_status, const char *expected_body) {
    int sockets[2];
    assert(socketpair(AF_UNIX, SOCK_STREAM, 0, sockets) == 0);
    assert(write(sockets[0], line, strlen(line)) == (ssize_t)strlen(line));
    assert(cfv_mono_control_respond_fd(control, sockets[1]) == expected_status);
    char response[1024];
    ssize_t size = read(sockets[0], response, sizeof response - 1);
    assert(size > 0);
    response[size] = 0;
    assert(strstr(response, expected_body));
    close(sockets[0]);
    close(sockets[1]);
}

int main(int argc, char **argv) {
    assert(argc == 3);
    FILE *file = fopen(argv[1], "w");
    assert(file && fputs("1\n", file) >= 0 && fclose(file) == 0);
    file = fopen(argv[2], "w");
    assert(file && fputs("0\n", file) >= 0 && fclose(file) == 0);
    cfv_mono_control control;
    cfv_mono_control_init(&control, argv[1], argv[2]);
    request(&control, "GET /mono/status HTTP/1.1\r\n\r\n", 200,
            "\"available\":true");
    request(&control, "POST /mono/enable HTTP/1.1\r\n\r\n", 503,
            "\"effective\":false");
    cfv_mono_control_set_ready(&control, CFV_MONO_READY_ALL, 1);
    request(&control, "POST /mono/enable HTTP/1.1\r\n\r\n", 200,
            "\"effective\":true");
    cfv_mono_control_set_ready(&control, CFV_MONO_READY_HEIF, 0);
    request(&control, "POST /mono/disable HTTP/1.1\r\n\r\n", 200,
            "\"selected\":false");
    request(&control, "POST /not-a-route HTTP/1.1\r\n\r\n", 404,
            "\"ok\":false");
    request(&control, "GET /mono/status HTTP/9.9\r\n\r\n", 400,
            "bad_request");
    return 0;
}
