#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "cfv_mono_pref.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int is_on(const char *path) {
    if (!path) return 0;
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return 0;
    struct stat info;
    char data[3];
    int ok = fstat(fd, &info) == 0 && S_ISREG(info.st_mode) &&
             read(fd, data, sizeof data) == 2 &&
             data[0] == '1' && data[1] == '\n';
    close(fd);
    return ok;
}

int cfv_mono_pref_load(const char *feature_path, const char *pref_path) {
    return is_on(feature_path) && is_on(pref_path);
}

int cfv_mono_feature_available(const char *feature_path) {
    return is_on(feature_path);
}

static int sync_parent(const char *path) {
    const char *slash = strrchr(path, '/');
    if (!slash) return -1;
    size_t length = (size_t)(slash - path);
    if (!length) length = 1;
    char *parent = malloc(length + 1);
    if (!parent) return -1;
    memcpy(parent, path, length);
    parent[length] = 0;
    int fd = open(parent, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    free(parent);
    if (fd < 0) return -1;
    int result = fsync(fd);
    int saved = errno;
    close(fd);
    errno = saved;
    return result;
}

int cfv_mono_pref_save(const char *pref_path, int enabled) {
    if (!pref_path || pref_path[0] != '/' || (enabled != 0 && enabled != 1))
        return -1;
    size_t length = strlen(pref_path);
    if (length > 1024) return -1;
    char *temporary = malloc(length + sizeof ".next.XXXXXX");
    if (!temporary) return -1;
    snprintf(temporary, length + sizeof ".next.XXXXXX", "%s.next.XXXXXX", pref_path);
    int fd = mkstemp(temporary);
    if (fd < 0) { free(temporary); return -1; }
    const char bytes[2] = {enabled ? '1' : '0', '\n'};
    int ok = fchmod(fd, 0600) == 0 && write(fd, bytes, 2) == 2 &&
             fsync(fd) == 0;
    if (close(fd) != 0) ok = 0;
    if (ok) ok = rename(temporary, pref_path) == 0 &&
                 sync_parent(pref_path) == 0;
    if (!ok) unlink(temporary);
    free(temporary);
    return ok ? 0 : -1;
}

static int remove_file(const char *path) {
    if (!path || path[0] != '/') return -1;
    if (unlink(path) != 0 && errno != ENOENT) return -1;
    return sync_parent(path);
}

static int is_absent(const char *path) {
    struct stat info;
    return lstat(path, &info) != 0 && errno == ENOENT;
}

int cfv_mono_pref_clear(const char *feature_path, const char *pref_path) {
    /* Remove availability first so an interrupted restore cannot activate an
     * old user preference on the next boot. */
    if (remove_file(feature_path) != 0) return -1;
    if (remove_file(pref_path) != 0) return -1;
    return is_absent(feature_path) && is_absent(pref_path) ? 0 : -1;
}
