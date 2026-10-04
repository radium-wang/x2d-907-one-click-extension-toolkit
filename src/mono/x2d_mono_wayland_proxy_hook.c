#include "x2d_mono_wayland_proxy_hook.h"
#include <dlfcn.h>
#include <string.h>

static x2d_mono_wayland_proxy_hooks configured;

void x2d_mono_wayland_proxy_hooks_bind(
    const x2d_mono_wayland_proxy_hooks *hooks) {
    /* Startup-only configuration: do not mutate while callbacks are live. */
    if (hooks) configured = *hooks;
    else memset(&configured, 0, sizeof configured);
}

static void (*stock_release(void))(void *, void *) {
    if (configured.stock_buffer_release) return configured.stock_buffer_release;
    void *symbol = dlsym(RTLD_NEXT,
        "_ZN14WaylandControl13bufferReleaseEP9wl_buffer");
    void (*stock)(void *, void *) = NULL;
    memcpy(&stock, &symbol, sizeof stock);
    return stock;
}
static void (*stock_destroy(void))(void *) {
    if (configured.stock_proxy_destroy) return configured.stock_proxy_destroy;
    void *symbol = dlsym(RTLD_NEXT, "wl_proxy_destroy");
    void (*stock)(void *) = NULL;
    memcpy(&stock, &symbol, sizeof stock);
    return stock;
}

void x2d_mono_buffer_release_interpose(void *control, void *wl_buffer) {
    void (*stock)(void *, void *) = stock_release();
    if (!stock) return;
    stock(control, wl_buffer);
    if (configured.on_buffer_release)
        configured.on_buffer_release(configured.user, wl_buffer);
}
void wl_proxy_destroy(void *proxy) {
    void (*stock)(void *) = stock_destroy();
    if (!stock) return;
    stock(proxy);
    /* The stock BufferBase destructor calls this on its wl_buffer at
     * 0x1cb74-0x1cb78. A tracked pointer is the second lease event.
     * If that call never occurs, the bounded pool stays quarantined. */
    if (configured.on_proxy_destroy)
        configured.on_proxy_destroy(configured.user, proxy);
}
