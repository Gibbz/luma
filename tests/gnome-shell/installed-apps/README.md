# Live application discovery

`python3 tests/gnome-shell/installed-apps/check-discovery.py` checks the production
Applications directory and Search APIs using real GIO desktop discovery in an
isolated temporary data directory. It creates and removes exported desktop-file
symlinks for both user and system installations without launching an application.

`bash tests/gnome-shell/installed-apps/run-native.sh` runs only inside a disposable
native Luma Shell fixture. Install the candidate Shell RPMs there first. The
script opens Luma Search before publishing the launcher and verifies prompt
discovery, refresh without retyping, and removal from an open query. It writes
package identities, the Shell log, and a JSON result beneath `DEV_ARTIFACT_DIR`.
The exported entries model Flatpak's desktop integration; this test does not
install Minecraft or test its runtime.
