# Voice Memos for Linux

Voice Memos uses the shared Luma interface and recording library. The standalone Flatpak bundles the selected GTK, Python, LumaUI and GStreamer dependencies and uses GNOME Platform 50 as its shared runtime.

Install the bundle with `flatpak install --user ./VoiceMemos-0.1.1-x86_64.flatpak`. The application requests desktop audio access and access to `Music/Voice Memos`; it can record, pause, resume, play, rename, delete, undo deletion and export recordings. Microphone routing uses PulseAudio, including desktops using PipeWire's PulseAudio compatibility service. Recording processing and automatic transcription are not provided by this release.

Build the portable directory with `scripts/standalone/build-memos.py --runtime-files PLATFORM_FILES --pixbuf-prefix PIXBUF_PREFIX --output OUTPUT`, then run `scripts/standalone/build-memos-flatpak.sh OUTPUT FLATPAK_OUTPUT`. The qualified platform and GdkPixbuf inputs are the same as the other standalone Luma applications. The release includes corresponding dependency sources and native-library hashes.

`src/prairie-core/tests/voice_memos_audio.py` checks real saved Ogg/Opus audio against the production playback pipeline, including altered playback speed and a deliberate signal corruption. Physical microphone and speaker behavior must be checked on the target device.
