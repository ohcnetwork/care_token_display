"""
Server-side text-to-speech for token announcements.

Uses Piper TTS (ONNX neural voices) to synthesize speech offline. Each
announcement is rendered as a single WAV file with the chime prefixed in,
hashed by ``(voice_id, text)`` and cached on disk so repeat requests are
served instantly. Voice models are downloaded lazily on first use.

The output WAV is fixed at 22.05 kHz / mono / 16-bit so that it matches the
shipped chime asset and can be concatenated without any resampling step.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import tempfile
import threading
import wave
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from filelock import FileLock

from token_display.settings import plugin_settings

logger = logging.getLogger(__name__)

EXPECTED_SAMPLE_RATE = 22050
EXPECTED_CHANNELS = 1
EXPECTED_SAMPLE_WIDTH = 2  # 16-bit PCM

_DOWNLOAD_TIMEOUT_SECONDS = 60
_MIN_ONNX_BYTES = 1_000_000  # ~1 MB sanity floor; real medium voices are 50+ MB
_MIN_CONFIG_BYTES = 100

_VOICE_PROCESS_CACHE: dict[str, object] = {}
_VOICE_PROCESS_LOCK = threading.Lock()


class TTSError(RuntimeError):
    """Raised when speech synthesis cannot be completed."""


# ---------------------------------------------------------------------------
# Cache directory layout
# ---------------------------------------------------------------------------


def _resolve_cache_dir() -> Path:
    configured = plugin_settings.TTS_CACHE_DIR
    if configured:
        base = Path(configured)
    else:
        base = Path(tempfile.gettempdir()) / "care_token_display_tts"
    base.mkdir(parents=True, exist_ok=True)
    (base / "voices").mkdir(parents=True, exist_ok=True)
    (base / "announcements").mkdir(parents=True, exist_ok=True)
    return base


def _voice_paths(voice_id: str) -> tuple[Path, Path]:
    base = _resolve_cache_dir() / "voices"
    return base / f"{voice_id}.onnx", base / f"{voice_id}.onnx.json"


def _announcement_path(cache_key: str) -> Path:
    return _resolve_cache_dir() / "announcements" / f"{cache_key}.wav"


def _lock_for(path: Path) -> FileLock:
    return FileLock(str(path) + ".lock", timeout=120)


# ---------------------------------------------------------------------------
# Voice model fetch
# ---------------------------------------------------------------------------


def _download(url: str, dest: Path, min_size: int) -> None:
    """Atomically download ``url`` to ``dest`` (verifies a minimum size)."""
    tmp = dest.with_suffix(dest.suffix + ".partial")
    try:
        with urlopen(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as resp:  # noqa: S310 — URL is from a trusted, hardcoded catalog
            with open(tmp, "wb") as fh:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    fh.write(chunk)
        size = tmp.stat().st_size
        if size < min_size:
            raise TTSError(
                f"downloaded file too small ({size} < {min_size}): {url}"
            )
        os.replace(tmp, dest)
    except URLError as exc:  # network failure
        raise TTSError(f"failed to download {url}: {exc}") from exc
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def ensure_voice(voice_id: str) -> tuple[Path, Path]:
    """Return ``(onnx_path, config_path)`` for ``voice_id``, downloading if absent."""
    catalog = plugin_settings.TTS_VOICE_CATALOG or {}
    entry = catalog.get(voice_id)
    if not entry:
        raise TTSError(f"voice {voice_id!r} is not in TTS_VOICE_CATALOG")

    onnx_path, config_path = _voice_paths(voice_id)
    if onnx_path.exists() and config_path.exists():
        return onnx_path, config_path

    with _lock_for(onnx_path):
        if not config_path.exists():
            _download(entry["config_url"], config_path, _MIN_CONFIG_BYTES)
        if not onnx_path.exists():
            _download(entry["onnx_url"], onnx_path, _MIN_ONNX_BYTES)
    return onnx_path, config_path


def _load_voice(voice_id: str):
    """Load and cache a ``PiperVoice`` for the lifetime of the process."""
    cached = _VOICE_PROCESS_CACHE.get(voice_id)
    if cached is not None:
        return cached
    with _VOICE_PROCESS_LOCK:
        cached = _VOICE_PROCESS_CACHE.get(voice_id)
        if cached is not None:
            return cached
        try:
            from piper import PiperVoice  # type: ignore[import-not-found]
        except ImportError as exc:
            raise TTSError("piper-tts is not installed") from exc
        onnx_path, config_path = ensure_voice(voice_id)
        voice = PiperVoice.load(str(onnx_path), config_path=str(config_path))
        _VOICE_PROCESS_CACHE[voice_id] = voice
        return voice


# ---------------------------------------------------------------------------
# Audio synthesis + chime concatenation
# ---------------------------------------------------------------------------


def _read_wav_frames(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wf:
        if wf.getframerate() != EXPECTED_SAMPLE_RATE:
            raise TTSError(
                f"{path}: expected {EXPECTED_SAMPLE_RATE} Hz, got {wf.getframerate()}"
            )
        if wf.getnchannels() != EXPECTED_CHANNELS:
            raise TTSError(
                f"{path}: expected {EXPECTED_CHANNELS} channel(s), got {wf.getnchannels()}"
            )
        if wf.getsampwidth() != EXPECTED_SAMPLE_WIDTH:
            raise TTSError(
                f"{path}: expected {EXPECTED_SAMPLE_WIDTH}-byte samples, got {wf.getsampwidth()}"
            )
        return wf.readframes(wf.getnframes())


def _synthesize_speech_frames(voice_id: str, text: str) -> bytes:
    """Return raw 22.05 kHz mono 16-bit PCM frames for ``text``."""
    voice = _load_voice(voice_id)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        # Piper drives wave header configuration via synthesize_wav.
        try:
            voice.synthesize_wav(text, wf)
        except Exception as exc:  # noqa: BLE001 — surface any backend failure as TTSError
            raise TTSError(f"piper synthesis failed: {exc}") from exc
    buffer.seek(0)
    with wave.open(buffer, "rb") as wf:
        if (
            wf.getframerate() != EXPECTED_SAMPLE_RATE
            or wf.getnchannels() != EXPECTED_CHANNELS
            or wf.getsampwidth() != EXPECTED_SAMPLE_WIDTH
        ):
            raise TTSError(
                "voice produced unexpected audio params: "
                f"{wf.getframerate()} Hz / {wf.getnchannels()} ch / "
                f"{wf.getsampwidth()*8}-bit"
            )
        return wf.readframes(wf.getnframes())


def _chime_path() -> Path:
    return (
        Path(__file__).parent
        / "static"
        / "token_display"
        / "sounds"
        / "chime.wav"
    )


def _cache_key(voice_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{voice_id}|{text}".encode()).hexdigest()
    return digest[:32]


def render_announcement(voice_id: str, text: str) -> Path:
    """Render (or fetch from cache) a WAV containing chime + spoken ``text``."""
    if not plugin_settings.TTS_ENABLED:
        raise TTSError("TTS is disabled (TTS_ENABLED=False)")
    if not text:
        raise TTSError("text must not be empty")

    cache_key = _cache_key(voice_id, text)
    out_path = _announcement_path(cache_key)
    if out_path.exists():
        return out_path

    with _lock_for(out_path):
        if out_path.exists():
            return out_path

        chime_frames = _read_wav_frames(_chime_path())
        speech_frames = _synthesize_speech_frames(voice_id, text)

        # Insert a brief silence between chime and speech so they don't blur.
        silence_ms = 220
        silence_frames = b"\x00\x00" * int(EXPECTED_SAMPLE_RATE * silence_ms / 1000)

        tmp_path = out_path.with_suffix(out_path.suffix + ".partial")
        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(EXPECTED_CHANNELS)
                wf.setsampwidth(EXPECTED_SAMPLE_WIDTH)
                wf.setframerate(EXPECTED_SAMPLE_RATE)
                wf.writeframes(chime_frames)
                wf.writeframes(silence_frames)
                wf.writeframes(speech_frames)
            os.replace(tmp_path, out_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    return out_path
