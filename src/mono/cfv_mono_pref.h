#ifndef CFV_MONO_PREF_H
#define CFV_MONO_PREF_H

/* Persistent camera-data state, following Shuaqi's brightness preference.
 * The feature marker and the user's choice are separate: a missing marker
 * disables the mode even if an old preference survives an interrupted restore.
 * Call load at every GUI/camera-service start, before exposing the menu or
 * processing a frame. A corrupt or unreadable preference fails closed. */
#define CFV_MONO_FEATURE_PATH "/blackbox/x2d-play-mono.available"
#define CFV_MONO_PREF_PATH "/blackbox/x2d-play-mono.enabled"

/* Returns 1 only when both files contain exactly "1\n". Returns 0 for
 * missing, disabled, corrupt or unreadable state. */
int cfv_mono_pref_load(const char *feature_path, const char *pref_path);
int cfv_mono_feature_available(const char *feature_path);

/* Atomically persist the selected state. Returns 0 on success, -1 on error.
 * The installer owns feature_path; this function never creates it. */
int cfv_mono_pref_save(const char *pref_path, int enabled);

/* Restore-original must remove both paths and confirm their absence. */
int cfv_mono_pref_clear(const char *feature_path, const char *pref_path);

#endif
