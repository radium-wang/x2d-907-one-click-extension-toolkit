#ifndef X2D_BRIGHTNESS_POLICY_H
#define X2D_BRIGHTNESS_POLICY_H
/* Pure policy; caller owns thread, sensor validation and durable preference. */
struct brightness_policy {
 double filtered, last_time, target;
 int initialized, applied, effective, last_eligible;
};
void brightness_reset(struct brightness_policy *, int manual, double now);
/* Return 1 for an output request, 0 for no write. Never write while ineligible. */
int brightness_step(struct brightness_policy *, int enabled, int valid, double sensor,
                    int eligible, int manual, double now, int *output);
#endif
