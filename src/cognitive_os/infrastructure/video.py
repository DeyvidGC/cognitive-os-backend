"""Decode untrusted video in a bounded child process; keep secrets out of its environment."""

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import wave


def decode(path, directory, media_type, max_seconds, interval):
    import av

    samples = []
    next_sample = 0.0
    last_timestamp = 0.0
    first_timestamp = None
    count = 0
    with av.open(str(path), format="matroska" if media_type == "video/webm" else "mov",
                 options={"protocol_whitelist": "file", "enable_drefs": "0"}) as container:
        if len(container.streams.video) != 1:
            raise ValueError("Exactly one video track is required")
        stream = container.streams.video[0]
        stream.thread_count = 1
        if (not 1 <= stream.width <= 4096 or not 1 <= stream.height <= 4096
                or stream.width * stream.height > 8_500_000):
            raise ValueError("Video resolution exceeds limit")
        for frame in container.decode(stream):
            count += 1
            if count > 72000 or frame.time is None or not math.isfinite(frame.time):
                raise ValueError("Video decode limit or invalid timestamps")
            if frame.width * frame.height > 8_500_000:
                raise ValueError("Frame resolution exceeds limit")
            if first_timestamp is None:
                first_timestamp = float(frame.time)
            timestamp = float(frame.time) - first_timestamp
            if timestamp < last_timestamp or timestamp > max_seconds:
                raise ValueError("Video duration or timestamp order invalid")
            last_timestamp = timestamp
            if timestamp + 0.001 < next_sample:
                continue
            if len(samples) >= 61:
                raise ValueError("Too many sampled frames")
            filename = f"frame-{len(samples):03d}.jpg"
            image = frame.to_image()
            image.thumbnail((1280, 720))
            image.save(directory / filename, format="JPEG", quality=80)
            samples.append({"index": len(samples), "timestamp_ms": round(timestamp * 1000), "file": filename})
            next_sample += interval
    if not samples:
        raise ValueError("Video contains no decodable frames")
    result = {"frames": samples, "duration_ms": round(last_timestamp * 1000),
              "frame_interval_seconds": interval, "audio_analyzed": False,
              "mode": "sampled_frames", "decoded_frame_count": count}
    with av.open(str(path), options={"protocol_whitelist": "file", "enable_drefs": "0"}) as container:
        if container.streams.audio:
            if len(container.streams.audio) > 1:
                raise ValueError("Mix audio into one track before uploading")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            written = 0
            with wave.open(str(directory / "audio.wav"), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                for frame in container.decode(audio=0):
                    for converted in resampler.resample(frame):
                        written += converted.samples
                        if written > max_seconds * 16000:
                            raise ValueError("Audio duration exceeds limit")
                        output.writeframes(converted.to_ndarray().tobytes())
                for converted in resampler.resample(None):
                    written += converted.samples
                    if written > max_seconds * 16000:
                        raise ValueError("Audio duration exceeds limit")
                    output.writeframes(converted.to_ndarray().tobytes())
            result["audio_present"] = written > 0
        else:
            result["audio_present"] = False
    (directory / "sampling.json").write_text(json.dumps(result), encoding="utf-8")


def extract_frames(path: Path, directory: Path, media_type: str, settings):
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
    subprocess.run([sys.executable, "-m", "cognitive_os.infrastructure.video",
                    str(path), str(directory), media_type,
                    str(settings.recording_max_seconds), str(settings.recording_frame_interval_seconds)],
                   env=env, check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return json.loads((directory / "sampling.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("directory", type=Path)
    parser.add_argument("media_type", choices=["video/webm", "video/mp4"])
    parser.add_argument("max_seconds", type=int)
    parser.add_argument("interval", type=int)
    args = parser.parse_args()
    decode(args.path, args.directory, args.media_type, args.max_seconds, args.interval)
