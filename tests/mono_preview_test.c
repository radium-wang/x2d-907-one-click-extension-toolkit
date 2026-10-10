#include "cfv_mono_preview.h"
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int acquire, sync, present, release, fail_sync; } events;
static int acquire(void *u, const cfv_mono_preview_source *s,
                   cfv_mono_preview_private *d) {
    events *e = u; e->acquire++;
    size_t n = s->width * s->height * 3 / 2;
    uint8_t *p = malloc(n);
    if (!p) return -1;
    memset(p, 0x55, n);
    d->y = p; d->y_size = s->width * s->height; d->y_stride = s->width;
    d->uv = p + d->y_size; d->uv_size = s->width * s->height / 2;
    d->uv_stride = s->width; d->width = s->width; d->height = s->height;
    d->owner = p;
    return 0;
}
static int verify_private(void *u, const cfv_mono_preview_source *s,
                          const cfv_mono_preview_private *d) {
    (void)u; return s->owner && d->owner && s->owner != d->owner ? 0 : -1;
}
static int sync_private(void *u, cfv_mono_preview_private *d) {
    events *e = u; e->sync++; assert(d->owner);
    return e->fail_sync ? -1 : 0;
}
static int present(void *u, cfv_mono_preview_private *d) {
    events *e = u; e->present++;
    assert(d->y[0] == 0x23 && d->uv[0] == 0x80);
    free(d->owner); d->owner = NULL; return 0;
}
static void release(void *u, cfv_mono_preview_private *d) {
    events *e = u; e->release++; free(d->owner); d->owner = NULL;
}
int main(void) {
    uint8_t sy[12] = {1,2,3,4,0x99,0x99,5,6,7,8,0x99,0x99};
    uint8_t suv[6] = {10,20,30,40,0x99,0x99};
    uint8_t dy[12], duv[6];
    memset(dy, 0x77, sizeof dy); memset(duv, 0x77, sizeof duv);
    cfv_mono_preview_source s = {sy,suv,sizeof sy,6,sizeof suv,6,4,2,sy};
    cfv_mono_preview_private d = {dy,duv,sizeof dy,6,sizeof duv,6,4,2,NULL};
    assert(cfv_mono_preview_convert(&s,&d) == CFV_MONO_PREVIEW_OK);
    assert(memcmp(dy,sy,4) == 0 && memcmp(dy+6,sy+6,4) == 0);
    assert(dy[4] == 0x77 && dy[10] == 0x77);
    for (int i=0;i<4;++i) assert(duv[i] == 0x80);
    assert(duv[4] == 0x77 && memcmp(suv,(uint8_t[]){10,20,30,40,0x99,0x99},6)==0);
    d.uv = sy;
    assert(cfv_mono_preview_convert(&s,&d) == CFV_MONO_PREVIEW_ALIAS);
    d.uv = duv; d.uv_size = 3;
    assert(cfv_mono_preview_convert(&s,&d) == CFV_MONO_PREVIEW_TOO_SMALL);
    d.uv_size = sizeof duv; s.height = 3;
    assert(cfv_mono_preview_convert(&s,&d) == CFV_MONO_PREVIEW_BAD_FRAME);

    const size_t w=1944, h=1248, n=w*h*3/2;
    uint8_t *buf=malloc(n); assert(buf); memset(buf,0x23,w*h);
    memset(buf+w*h,0x60,w*h/2);
    cfv_mono_preview_source full={buf,buf+w*h,w*h,w,w*h/2,w,w,h,buf};
    events e={0};
    cfv_mono_preview_ops ops={acquire,verify_private,sync_private,present,release};
    assert(cfv_mono_preview_process(0,&full,&ops,&e)==CFV_MONO_PREVIEW_OFF);
    assert(e.acquire==0);
    assert(cfv_mono_preview_process(1,&full,&ops,&e)==CFV_MONO_PREVIEW_OK);
    assert(e.acquire==1 && e.sync==1 && e.present==1 && e.release==0);
    assert(buf[0]==0x23 && buf[w*h]==0x60);
    e.fail_sync=1;
    assert(cfv_mono_preview_process(1,&full,&ops,&e)==CFV_MONO_PREVIEW_SYNC_FAILED);
    assert(e.acquire==2 && e.sync==2 && e.present==1 && e.release==1);
    full.width=640;
    assert(cfv_mono_preview_process(1,&full,&ops,&e)==CFV_MONO_PREVIEW_BAD_FRAME);
    assert(e.acquire==2);
    full.width=w; full.y_size=1;
    assert(cfv_mono_preview_process(1,&full,&ops,&e)==CFV_MONO_PREVIEW_TOO_SMALL);
    assert(e.acquire==2);
    free(buf);
    return 0;
}
