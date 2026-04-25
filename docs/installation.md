# Installation

## Stable release

To install care_token_display, run this command in your terminal:

```sh
pip install care_token_display
```

## From source

The source files for care_token_display can be downloaded from the [Github repo](https://github.com/ohcnetwork/token_display).

You can either clone the public repository:

```sh
git clone git://github.com/ohcnetwork/token_display
```

Or download the [tarball](https://github.com/ohcnetwork/token_display/tarball/master):

```sh
curl -OJL https://github.com/ohcnetwork/token_display/tarball/master
```

Once you have a copy of the source, you can install it with:

```sh
cd token_display
pip install .
```

## Audio announcements (Piper TTS)

Server-side text-to-speech is provided by
[`piper-tts`](https://pypi.org/project/piper-tts/) and is installed
automatically as a dependency. No system packages (e.g. `ffmpeg`) are
required.

### Plugin settings

Configure under `PLUGIN_CONFIGS["token_display"]` in your Care settings or via
environment variables:

| Setting              | Default                                                | Description                                                                                                                                        |
| -------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TTS_ENABLED`        | `True`                                                 | Master switch. When `False`, the announcement endpoint returns 503 and the display falls back to silent mode.                                      |
| `TTS_DEFAULT_VOICE`  | `en_US-amy-medium`                                     | Voice id used when the request does not specify `?voice=`.                                                                                         |
| `TTS_CACHE_DIR`      | `<tempdir>/care_token_display_tts`                     | Where downloaded voice models and rendered announcements are cached. Use a persistent path in production so models are not re-downloaded on boot.  |
| `TTS_VOICE_CATALOG`  | 7 default voices (en-US ×2, en-GB, hi-IN ×2, ml-IN ×2) | Mapping of voice id → `{onnx_url, config_url, lang}`. Override or extend with custom voices.                                                       |

### First-request latency and disk usage

Voice models are downloaded lazily on first use to
`<TTS_CACHE_DIR>/voices/`. A medium-quality Piper voice is roughly 50 MB; a
high-quality voice is ~110 MB. The first request that needs a given voice
will block on the download (typically a few seconds on a fast link); all
subsequent requests are served from the on-disk cache.

Rendered announcements live in `<TTS_CACHE_DIR>/announcements/` and are
roughly 30–80 KB each. The number of unique announcements is bounded by the
number of distinct `(voice, token-code, resource)` combinations seen, so
unbounded growth is unlikely; if you wish to clean older entries, simply
delete files in that directory.

### Air-gapped deployments

To run without internet, pre-populate `<TTS_CACHE_DIR>/voices/` with the
required `.onnx` and `.onnx.json` files (filenames must match the voice id —
e.g. `en_US-amy-medium.onnx` and `en_US-amy-medium.onnx.json`). Once both
files are present the plugin will not attempt any network access.

### Custom voices

Add an entry to `TTS_VOICE_CATALOG` whose `onnx_url` and `config_url` point
to a Piper-compatible model. You can host these on any HTTPS endpoint
reachable from the Care server, or use the air-gapped flow above to bypass
downloads entirely.
