#define _POSIX_C_SOURCE 200809L
#include "cfv_mono_control_server.h"
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

static int send_all(int fd, const char *data, size_t size) {
    while (size) {
        ssize_t sent = send(fd, data, size,
#ifdef MSG_NOSIGNAL
                            MSG_NOSIGNAL
#else
                            0
#endif
        );
        if (sent < 0 && errno == EINTR) continue;
        if (sent <= 0) return -1;
        data += sent;
        size -= (size_t)sent;
    }
    return 0;
}

int cfv_mono_control_respond_fd(cfv_mono_control *control, int fd) {
    if (!control || fd < 0) return -1;
    struct timeval timeout = {.tv_sec = 2, .tv_usec = 0};
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout))
        return -1;
#ifdef SO_NOSIGPIPE
    int one = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof one)) return -1;
#endif
    char request[256];
    ssize_t received = recv(fd, request, sizeof request - 1, 0);
    if (received <= 0) return -1;
    request[received] = 0;
    char method[8], path[48], version[16];
    char body[512];
    int status = 400;
    int fields = sscanf(request, "%7s %47s %15s", method, path, version);
    if (strstr(request, "\r\n") && fields == 3 &&
        (!strcmp(version, "HTTP/1.0") ||
                        !strcmp(version, "HTTP/1.1")) &&
        (!strcmp(method, "GET") || !strcmp(method, "POST"))) {
        status = cfv_mono_control_request(control, method, path,
                                          body, sizeof body);
    } else {
        strcpy(body, "{\"ok\":false,\"state\":\"bad_request\"}\n");
    }
    const char *reason = status == 200 ? "OK" : status == 404 ? "Not Found" :
                         status == 503 ? "Service Unavailable" :
                         status == 500 ? "Internal Server Error" : "Bad Request";
    char header[384];
    int length = snprintf(header, sizeof header,
        "HTTP/1.1 %d %s\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Cache-Control: no-store\r\n"
        "Content-Length: %zu\r\nConnection: close\r\n\r\n",
        status, reason, strlen(body));
    if (length <= 0 || (size_t)length >= sizeof header) return -1;
    return send_all(fd, header, (size_t)length) ||
           send_all(fd, body, strlen(body)) ? -1 : status;
}

int cfv_mono_control_serve(cfv_mono_control *control, unsigned short port,
                           const atomic_int *stop) {
    if (!control || !port || !stop) return -1;
    int server = socket(AF_INET, SOCK_STREAM, 0);
    if (server < 0) return -1;
    int one = 1;
    struct sockaddr_in address = {.sin_family = AF_INET,
                                  .sin_port = htons(port)};
    int result = -1;
    if (inet_pton(AF_INET, "127.0.0.1", &address.sin_addr) != 1)
        goto done;
    if (setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one) ||
        bind(server, (const struct sockaddr *)&address, sizeof address) ||
        listen(server, 4)) goto done;
    result = 0;
    while (!atomic_load(stop)) {
        fd_set readable;
        FD_ZERO(&readable);
        FD_SET(server, &readable);
        struct timeval timeout = {.tv_sec = 0, .tv_usec = 250000};
        int selected = select(server + 1, &readable, NULL, NULL, &timeout);
        if (selected < 0 && errno == EINTR) continue;
        if (selected < 0) { result = -1; break; }
        if (selected == 0) continue;
        int client = accept(server, NULL, NULL);
        if (client < 0 && errno == EINTR) continue;
        if (client < 0) { result = -1; break; }
        cfv_mono_control_respond_fd(control, client);
        close(client);
    }
done:
    close(server);
    return result;
}
