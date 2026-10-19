# Native status and Quick Options regression

Run `run-native.sh` inside an owned disposable Shell fixture with the candidate
Shell resources installed, the normal Luma theme/icons/fonts, the `luma-media-test`
user (UID 1000), and `LUMA_NATIVE_SHELL_DISPOSABLE=1`. Set `DEV_ARTIFACT_DIR` to its
private output directory. Never run it in a person's desktop session.

The fixture checks AM/PM allocation at real 100% and 125% monitor scaling,
including a right-to-left clock row; background-app artwork and readable names;
disclosure insets, native rounded controls and network row spacing across dark,
light, frost and glass treatments. It saves geometry results and screenshots.
Synthetic status notifiers and ordinary Quick Options actors exercise native
layout and paint; these are not hardware connectivity or third-party app tests.

Source-only overlays may be used for development, but must contain exactly the
changed resources and use the current shipped Shell binary/schema as a baseline.
Archive the source comparison, installed package tuple and actual test result.
