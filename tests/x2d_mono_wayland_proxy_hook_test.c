#include "x2d_mono_wayland_proxy_hook.h"
#include "x2d_mono_wayland_pool.h"
#include <assert.h>
#include <stdio.h>

static int releases, destroys, frees;
static void stock_release(void *control, void *buffer) {
    assert(control && buffer);
    releases++;
}
static void stock_destroy(void *proxy) {
    assert(proxy);
    destroys++;
}
static void free_lease(void *user, void *lease) {
    assert(user == lease);
    frees++;
}
static void observed_release(void *user, void *buffer) {
    (void)x2d_mono_wayland_pool_compositor_released(user, buffer);
}
static void observed_destroy(void *user, void *buffer) {
    (void)x2d_mono_wayland_pool_proxy_destroyed(user, buffer);
}
int main(void) {
    x2d_mono_wayland_pool pool;
    int vmem, lease, wl_buffer, unrelated, control;
    assert(x2d_mono_wayland_pool_init(&pool) == 0);
    assert(x2d_mono_wayland_pool_add(&pool, &vmem, &lease,
                                    free_lease, &lease) == 0);
    x2d_mono_wayland_proxy_hooks_bind(&(x2d_mono_wayland_proxy_hooks){
        stock_release, stock_destroy, observed_release, observed_destroy, &pool});
    int slot = x2d_mono_wayland_pool_reserve(&pool);
    assert(slot == 0);
    assert(x2d_mono_wayland_pool_bind_buffer(&pool, slot, &wl_buffer) == 0);
    assert(x2d_mono_wayland_pool_submit_begin(&pool, slot) == 0);
    wl_proxy_destroy(&unrelated);
    assert(destroys == 1 && frees == 0);
    x2d_mono_buffer_release_interpose(&control, &wl_buffer);
    assert(releases == 1 && frees == 0);
    x2d_mono_wayland_pool_retire(&pool);
    wl_proxy_destroy(&wl_buffer);
    assert(destroys == 2 && frees == 1);
    assert(x2d_mono_wayland_pool_destroy(&pool) == 0);
    puts("x2d Wayland proxy hooks: OK");
    return 0;
}
