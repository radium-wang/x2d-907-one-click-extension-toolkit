#include "x2d_mono_wayland_pool.h"
#include <assert.h>
#include <stdio.h>

static int freed;
static void free_lease(void *user, void *lease) {
    assert(user == lease);
    freed++;
}
int main(void) {
    x2d_mono_wayland_pool pool;
    int vmem[3], lease[3], wl[3];
    assert(x2d_mono_wayland_pool_init(&pool) == 0);
    for (int i = 0; i < 3; ++i)
        assert(x2d_mono_wayland_pool_add(&pool, &vmem[i], &lease[i],
                                        free_lease, &lease[i]) == i);
    int slot[3];
    for (int i = 0; i < 3; ++i) {
        slot[i] = x2d_mono_wayland_pool_reserve(&pool);
        assert(slot[i] == i);
        assert(x2d_mono_wayland_pool_bind_buffer(&pool, slot[i], &wl[i]) == 0);
        assert(x2d_mono_wayland_pool_submit_begin(&pool, slot[i]) == 0);
    }
    assert(x2d_mono_wayland_pool_reserve(&pool) == -1);
    assert(x2d_mono_wayland_pool_compositor_released(&pool, &wl[0]) == 0);
    for (int iteration = 0; iteration < 50; ++iteration) {
        int reused = x2d_mono_wayland_pool_reserve(&pool);
        assert(reused == slot[0]);
        assert(x2d_mono_wayland_pool_bind_buffer(&pool, reused, &wl[0]) == 0);
        assert(x2d_mono_wayland_pool_bind_buffer(&pool, reused, &wl[1]) == -1);
        assert(x2d_mono_wayland_pool_submit_begin(&pool, reused) == 0);
        assert(x2d_mono_wayland_pool_reserve(&pool) == -1);
        assert(x2d_mono_wayland_pool_compositor_released(&pool, &wl[0]) == 0);
    }
    assert(freed == 0 && x2d_mono_wayland_pool_live(&pool) == 3);
    x2d_mono_wayland_pool_retire(&pool);
    assert(x2d_mono_wayland_pool_reserve(&pool) == -1);
    assert(x2d_mono_wayland_pool_proxy_destroyed(&pool, &wl[0]) == 0);
    assert(freed == 1);
    assert(x2d_mono_wayland_pool_proxy_destroyed(&pool, &wl[1]) == 0);
    assert(freed == 1);
    assert(x2d_mono_wayland_pool_compositor_released(&pool, &wl[1]) == 0);
    assert(freed == 2);
    assert(x2d_mono_wayland_pool_compositor_released(&pool, &wl[2]) == 0);
    assert(freed == 2);
    assert(x2d_mono_wayland_pool_proxy_destroyed(&pool, &wl[2]) == 0);
    assert(freed == 3);
    assert(x2d_mono_wayland_pool_destroy(&pool) == 0);
    x2d_mono_wayland_pool never_submitted;
    int idle_vmem, idle_lease;
    assert(x2d_mono_wayland_pool_init(&never_submitted) == 0);
    assert(x2d_mono_wayland_pool_add(&never_submitted, &idle_vmem,
            &idle_lease, free_lease, &idle_lease) == 0);
    x2d_mono_wayland_pool_retire(&never_submitted);
    assert(freed == 4);
    assert(x2d_mono_wayland_pool_destroy(&never_submitted) == 0);
    puts("x2d Wayland pool: OK");
    return 0;
}
