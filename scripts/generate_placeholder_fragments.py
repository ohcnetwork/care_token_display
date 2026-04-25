"""Generate placeholder WAV fragments for the token-display announcer.

This script produces 22.05 kHz mono 16-bit PCM WAVs for:

- ``prefix.wav`` — "Now serving token"
- ``A.wav`` … ``Z.wav`` — each English letter
- ``0.wav`` … ``9.wav`` — each digit

Real recordings should drop into the same path with the same filenames.

Strategy:

1. If the macOS ``say`` binary is available, use it (with the highest-quality
   built-in voice we can pick, defaulting to ``Samantha``) to render each
   fragment via ``say -o tmp.aiff``, then convert to WAV via ``afconvert``
   (also ships with macOS).
2. Otherwise, fall back to a stdlib-only synthetic placeholder: a short
   beep tone whose pitch encodes the character (so they're at least
   distinguishable when debugging). The prefix becomes a longer two-tone
   beep.

Both paths normalize to roughly -3 dBFS, mono, 22.05 kHz, 16-bit PCM, with
~120 ms of trailing silence baked in so that consecutive fragments don't
slur together when concatenated by the Web Audio API client.

Run from the repo root::

    python scripts/generate_placeholder_fragments.py
"""

from __future__ import annotations

import argparse
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

SAMPLE_RATE = 22050
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit
TRAILING_SILENCE_S = 0.12
PEAK_AMPLITUDE = 0.7079  # ~ -3 dBFS

# Each fragment is identified by ("filename stem", "spoken text").
FRAGMENTS: list[tuple[str, str]] = [
    ("prefix", "Now serving token"),
]
FRAGMENTS.extend((chr(c), chr(c)) for c in range(ord("A"), ord("Z") + 1))
FRAGMENTS.extend(
    (str(d), word)
    for d, word in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        ]
    )
)


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _read_wav(path: Path) -> tuple[int, int, int, bytes]:
    with wave.open(str(path), "rb") as wf:
        return (
            wf.getframerate(),
            wf.getnchannels(),
            wf.getsampwidth(),
            wf.readframes(wf.getnframes()),
        )


def _write_wav(path: Path, frames: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(frames)


def _trim_silence(samples: list[int], threshold: int = 200) -> list[int]:
    start = 0
    end = len(samples)
    while start < end and abs(samples[start]) < threshold:
        start += 1
    while end > start and abs(samples[end - 1]) < threshold:
        end -= 1
    return samples[start:end]


def _normalize(samples: list[int]) -> list[int]:
    if not samples:
        return samples
    peak = max(abs(s) for s in samples) or 1
    target = int(PEAK_AMPLITUDE * 32767)
    gain = target / peak
    return [max(-32768, min(32767, int(s * gain))) for s in samples]


def _append_silence(samples: list[int], seconds: float) -> list[int]:
    return samples + [0] * int(seconds * SAMPLE_RATE)


def _samples_to_bytes(samples: list[int]) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def _bytes_to_samples(raw: bytes) -> list[int]:
    n = len(raw) // SAMPLE_WIDTH
    return list(struct.unpack(f"<{n}h", raw))


def _render_with_say(text: str, voice: str) -> list[int]:
    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "f.aiff"
        wav = Path(td) / "f.wav"
        subprocess.run(
            ["say", "-v", voice, "-o", str(aiff), text],
            check=True,
            capture_output=True,
        )
        # Convert AIFF -> 22.05 kHz mono 16-bit linear PCM WAV.
        subprocess.run(
            [
                "afconvert",
                str(aiff),
                str(wav),
                "-d",
                "LEI16@22050",
                "-c",
                "1",
                "-f",
                "WAVE",
            ],
            check=True,
            capture_output=True,
        )
        rate, channels, width, raw = _read_wav(wav)
        if (rate, channels, width) != (SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH):
            raise RuntimeError(
                f"unexpected output format from afconvert: "
                f"{rate}Hz {channels}ch {width * 8}bit"
            )
        return _bytes_to_samples(raw)


def _render_synthetic(stem: str, text: str) -> list[int]:
    """Stdlib-only fallback: a short tone whose pitch is character-derived."""
    if stem == "prefix":
        # Two descending tones to mark "Now serving token".
        return _tone_sequence([(880.0, 0.18), (660.0, 0.22)])
    base = sum(ord(c) for c in stem) * 13.0 + 220.0
    base = max(220.0, min(1760.0, base))
    return _tone_sequence([(base, 0.22)])


def _tone_sequence(notes: list[tuple[float, float]]) -> list[int]:
    samples: list[int] = []
    for freq, dur in notes:
        n = int(dur * SAMPLE_RATE)
        for i in range(n):
            t = i / SAMPLE_RATE
            # Cosine attack/release envelope, 15 ms each end.
            attack = min(1.0, t / 0.015)
            release = min(1.0, (dur - t) / 0.015)
            env = 0.5 * (1 - math.cos(math.pi * min(attack, release)))
            samples.append(int(PEAK_AMPLITUDE * 32767 * env * math.sin(2 * math.pi * freq * t)))
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="src/token_display/static/token_display/sounds",
        help="Output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--voice",
        default="Samantha",
        help="macOS `say` voice to use (default: Samantha)",
    )
    parser.add_argument(
        "--force-synthetic",
        action="store_true",
        help="Skip macOS `say` and use synthetic placeholders.",
    )
    args = parser.parse_args()

    use_say = (
        not args.force_synthetic
        and sys.platform == "darwin"
        and _have("say")
        and _have("afconvert")
    )
    print(
        "[fragments] backend:",
        f"macOS say (voice={args.voice})" if use_say else "synthetic tones",
    )

    out_dir = Path(args.out)
    written = 0
    for stem, text in FRAGMENTS:
        try:
            samples = (
                _render_with_say(text, args.voice)
                if use_say
                else _render_synthetic(stem, text)
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"[fragments] say/afconvert failed for {stem!r}; falling back: {exc}",
                file=sys.stderr,
            )
            samples = _render_synthetic(stem, text)

        samples = _trim_silence(samples)
        samples = _normalize(samples)
        samples = _append_silence(samples, TRAILING_SILENCE_S)
        path = out_dir / f"{stem}.wav"
        _write_wav(path, _samples_to_bytes(samples))
        written += 1

    print(f"[fragments] wrote {written} files to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
