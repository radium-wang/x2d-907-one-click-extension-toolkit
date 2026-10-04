#ifndef X2D_MONO_WAYLAND_PROXY_HOOK_H
#define X2D_MONO_WAYLAND_PROXY_HOOK_H

/* Source-only observers for the pinned first-generation 4.2.0 Wayland path.
 * Bind before frames are submitted. The callbacks must accept unrelated
 * Wayland objects and identify only tracked video wl_buffer pointers. */
typedef struct {
    void (*stock_buffer_release)(void *control, void *wl_buffer);
    void (*stock_proxy_destroy)(void *proxy);
    void (*on_buffer_release)(void *user, void *wl_buffer);
    void (*on_proxy_destroy)(void *user, void *proxy);
    void *user;
} x2d_mono_wayland_proxy_hooks;

void x2d_mono_wayland_proxy_hooks_bind(
    const x2d_mono_wayland_proxy_hooks *hooks);

/* Exact exported method, called by stock wl_buffer listener. */
void x2d_mono_buffer_release_interpose(void *control, void *wl_buffer)
    __asm__("_ZN14WaylandControl13bufferReleaseEP9wl_buffer");
/* libwayland-client export used by BufferBase::~BufferBase for wl_buffer. */
void wl_proxy_destroy(void *proxy);

#endif
