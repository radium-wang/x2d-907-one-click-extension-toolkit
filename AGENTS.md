# Project rules

Keep this repository focused on the first-generation X2D / CFV 100C 4.2.0 desktop utility, camera menus, autofocus and reversible installation. Preserve firmware gates, transaction checks and stock dynamic corrections. The optional 907 IBIS entry is a text-only joke, never a stabilization control.

Do not commit stock firmware, vendor-derived compiled units, generated camera payloads, runtime distributions, device logs, camera identities, credentials or personal paths. Source is in `src`, offline tests in `tests`, documentation and software screenshots in `docs`; generated inputs and archives stay ignored.

Distinguish offline tests, native desktop UI checks, device checks and user feedback. Ordinary development/publishing does not authorize camera installation, restoration, reboot or capture. Preserve unrelated local changes. Commit, push and release only when authorized by the human user.

Maintain CHANGELOG.md with English first, then Chinese, newest versions first. Record unreleased changes before publishing and move them into the version entry when releasing. Keep documentation-only changes separate from published app packages, preserve validation limits, and do not reveal the 907 Easter egg contents in user-facing documentation.
