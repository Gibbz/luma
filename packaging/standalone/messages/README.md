# Messages standalone

The standalone profile runs the shared Messages interface and native account
helpers without requiring the Luma OS background agent. Luma sign-in requires
Hub support for a Messages-scoped device token. Device credentials use Secret
Service; the native MLS helper receives enrolment through a sealed memory
descriptor. Google Messages and WhatsApp use their existing helper protocols.

Build the MLS helper from `src/luma-messages-e2ee` with its locked Cargo inputs,
and the linked-account helpers from `src/luma-messages-bridges`. Then use
`scripts/standalone/build-messages.py` with the helper binaries, QR encoder,
runtime files and GdkPixbuf inputs. `build-messages-flatpak.sh` packages the
result against GNOME Platform 50.

The Flatpak requests network access, display and audio sockets, and Secret
Service access. It does not request host filesystem access. Dependency sources,
upstream notices and the matching application source accompany a release.

Validation includes the Messages account suite, native MLS end-to-end tests,
and installation and account lifecycle checks in an independent Linux desktop.
