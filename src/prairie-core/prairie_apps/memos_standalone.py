# SPDX-License-Identifier: Apache-2.0
"""Voice Memos with the sandbox's PulseAudio microphone route."""
from . import audio_backend as audio
_original_start=audio.start_recording

def capability():
    try:
        gst=audio.gst()
        for name in ('pulsesrc','audioconvert','audioresample','level','opusenc','oggmux'):
            if not gst.ElementFactory.find(name):
                return audio.RecordingCapability(False,'The microphone audio component is unavailable.')
    except (ImportError,ValueError,RuntimeError):
        return audio.RecordingCapability(False,'The audio service is unavailable.')
    return audio.RecordingCapability(True,'Microphone access uses the desktop audio service.','Default microphone')

def start(root=None,**kwargs):
    kwargs.setdefault('source','pulsesrc')
    return _original_start(root,**kwargs)

audio.inspect_recording_capability=capability
audio.start_recording=start
from .voice_memos import main
if __name__=='__main__':raise SystemExit(main())
