#include "x2d_mono_wayland_pool.h"
#include <stdint.h>
#include <string.h>

static int index_ok(int index) {
    return index >= 0 && (unsigned)index < X2D_MONO_WAYLAND_POOL_MAX;
}
static int can_free(const x2d_mono_wayland_pool_slot *slot) {
    return slot->retiring && slot->proxy_destroyed &&
           slot->state != X2D_MONO_POOL_IN_FLIGHT &&
           slot->state != X2D_MONO_POOL_RESERVED;
}
static void take_free(x2d_mono_wayland_pool_slot *slot,
                      x2d_mono_wayland_pool_slot *owned) {
    *owned = *slot;
    memset(slot, 0, sizeof *slot);
}
static void finish_free(x2d_mono_wayland_pool_slot *owned) {
    if (owned->lease) owned->free_lease(owned->user, owned->lease);
}
int x2d_mono_wayland_pool_init(x2d_mono_wayland_pool *pool) {
    if (!pool) return -1;
    memset(pool, 0, sizeof *pool);
    return pthread_mutex_init(&pool->mutex, NULL) == 0 ? 0 : -1;
}
int x2d_mono_wayland_pool_add(x2d_mono_wayland_pool *pool,
                              void *stable_vmem, void *lease,
                              x2d_mono_wayland_pool_free_fn free_lease,
                              void *user) {
    if (!pool || !stable_vmem || !lease || !free_lease) return -1;
    if (pthread_mutex_lock(&pool->mutex) != 0) return -1;
    int free_index = -1;
    for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i) {
        if (pool->slots[i].stable_vmem == stable_vmem ||
            pool->slots[i].lease == lease) {
            pthread_mutex_unlock(&pool->mutex);
            return -1;
        }
        if (pool->slots[i].state == X2D_MONO_POOL_EMPTY && free_index < 0)
            free_index = (int)i;
    }
    if (free_index >= 0)
        pool->slots[free_index] = (x2d_mono_wayland_pool_slot){
            .stable_vmem = stable_vmem, .lease = lease,
            .free_lease = free_lease, .user = user,
            .state = X2D_MONO_POOL_AVAILABLE
        };
    pthread_mutex_unlock(&pool->mutex);
    return free_index;
}
int x2d_mono_wayland_pool_reserve(x2d_mono_wayland_pool *pool) {
    if (!pool || pthread_mutex_lock(&pool->mutex) != 0) return -1;
    int result = -1;
    for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i) {
        x2d_mono_wayland_pool_slot *slot = &pool->slots[i];
        if (slot->state == X2D_MONO_POOL_AVAILABLE && !slot->retiring &&
            !slot->proxy_destroyed) {
            slot->state = X2D_MONO_POOL_RESERVED;
            result = (int)i;
            break;
        }
    }
    pthread_mutex_unlock(&pool->mutex);
    return result;
}
int x2d_mono_wayland_pool_bind_buffer(x2d_mono_wayland_pool *pool,
                                      int slot_index, void *wl_buffer) {
    if (!pool || !index_ok(slot_index) || !wl_buffer ||
        pthread_mutex_lock(&pool->mutex) != 0) return -1;
    x2d_mono_wayland_pool_slot *slot = &pool->slots[slot_index];
    int result = -1;
    if (slot->state == X2D_MONO_POOL_RESERVED && !slot->retiring &&
        !slot->proxy_destroyed &&
        (!slot->wl_buffer || slot->wl_buffer == wl_buffer)) {
        int duplicate = 0;
        for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i)
            duplicate |= i != (unsigned)slot_index &&
                         pool->slots[i].wl_buffer == wl_buffer;
        if (!duplicate) {
            slot->wl_buffer = wl_buffer;
            result = 0;
        }
    }
    pthread_mutex_unlock(&pool->mutex);
    return result;
}
int x2d_mono_wayland_pool_submit_begin(x2d_mono_wayland_pool *pool,
                                       int slot_index) {
    if (!pool || !index_ok(slot_index) ||
        pthread_mutex_lock(&pool->mutex) != 0) return -1;
    x2d_mono_wayland_pool_slot *slot = &pool->slots[slot_index];
    int result = -1;
    if (slot->state == X2D_MONO_POOL_RESERVED && slot->wl_buffer &&
        !slot->retiring && !slot->proxy_destroyed) {
        slot->state = X2D_MONO_POOL_IN_FLIGHT;
        result = 0;
    }
    pthread_mutex_unlock(&pool->mutex);
    return result;
}
int x2d_mono_wayland_pool_abort_unsubmitted(x2d_mono_wayland_pool *pool,
                                            int slot_index) {
    if (!pool || !index_ok(slot_index) ||
        pthread_mutex_lock(&pool->mutex) != 0) return -1;
    x2d_mono_wayland_pool_slot *slot = &pool->slots[slot_index];
    x2d_mono_wayland_pool_slot owned = {0};
    int result = -1;
    if (slot->state == X2D_MONO_POOL_RESERVED) {
        slot->state = X2D_MONO_POOL_AVAILABLE;
        if (can_free(slot)) take_free(slot, &owned);
        result = 0;
    }
    pthread_mutex_unlock(&pool->mutex);
    finish_free(&owned);
    return result;
}
int x2d_mono_wayland_pool_compositor_released(x2d_mono_wayland_pool *pool,
                                              void *wl_buffer) {
    if (!pool || !wl_buffer || pthread_mutex_lock(&pool->mutex) != 0) return -1;
    x2d_mono_wayland_pool_slot owned = {0};
    int result = -1;
    for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i) {
        x2d_mono_wayland_pool_slot *slot = &pool->slots[i];
        if (slot->wl_buffer != wl_buffer) continue;
        if (slot->state == X2D_MONO_POOL_IN_FLIGHT) {
            slot->state = X2D_MONO_POOL_AVAILABLE;
            if (can_free(slot)) take_free(slot, &owned);
            result = 0;
        }
        break;
    }
    pthread_mutex_unlock(&pool->mutex);
    finish_free(&owned);
    return result;
}
int x2d_mono_wayland_pool_proxy_destroyed(x2d_mono_wayland_pool *pool,
                                          void *wl_buffer) {
    if (!pool || !wl_buffer || pthread_mutex_lock(&pool->mutex) != 0) return -1;
    x2d_mono_wayland_pool_slot owned = {0};
    int result = -1;
    for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i) {
        x2d_mono_wayland_pool_slot *slot = &pool->slots[i];
        if (slot->wl_buffer != wl_buffer) continue;
        slot->proxy_destroyed = 1;
        slot->retiring = 1;
        if (can_free(slot)) take_free(slot, &owned);
        result = 0;
        break;
    }
    pthread_mutex_unlock(&pool->mutex);
    finish_free(&owned);
    return result;
}
void x2d_mono_wayland_pool_retire(x2d_mono_wayland_pool *pool) {
    if (!pool || pthread_mutex_lock(&pool->mutex) != 0) return;
    x2d_mono_wayland_pool_slot freed[X2D_MONO_WAYLAND_POOL_MAX] = {{0}};
    unsigned count = 0;
    for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i) {
        x2d_mono_wayland_pool_slot *slot = &pool->slots[i];
        if (slot->state == X2D_MONO_POOL_EMPTY) continue;
        slot->retiring = 1;
        /* A never-bound buffer has no Wayland proxy to wait for. */
        if (!slot->wl_buffer) slot->proxy_destroyed = 1;
        if (can_free(slot)) take_free(slot, &freed[count++]);
    }
    pthread_mutex_unlock(&pool->mutex);
    for (unsigned i = 0; i < count; ++i) finish_free(&freed[i]);
}
x2d_mono_wayland_pool_state x2d_mono_wayland_pool_state_of(
    x2d_mono_wayland_pool *pool, int slot_index) {
    if (!pool || !index_ok(slot_index) ||
        pthread_mutex_lock(&pool->mutex) != 0) return X2D_MONO_POOL_EMPTY;
    x2d_mono_wayland_pool_state state = pool->slots[slot_index].state;
    pthread_mutex_unlock(&pool->mutex);
    return state;
}
size_t x2d_mono_wayland_pool_live(x2d_mono_wayland_pool *pool) {
    if (!pool || pthread_mutex_lock(&pool->mutex) != 0) return SIZE_MAX;
    size_t count = 0;
    for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i)
        count += pool->slots[i].state != X2D_MONO_POOL_EMPTY;
    pthread_mutex_unlock(&pool->mutex);
    return count;
}
int x2d_mono_wayland_pool_destroy(x2d_mono_wayland_pool *pool) {
    if (!pool || x2d_mono_wayland_pool_live(pool)) return -1;
    return pthread_mutex_destroy(&pool->mutex) == 0 ? 0 : -1;
}
