# Usage

To use care_token_display in a project:

```python
import token_display
```

## Audio announcements

The display calls out new tokens with a chime followed by a pre-recorded voice
prompt that spells the token code one character at a time. Audio is assembled
**in the browser** using the Web Audio API from a flat folder of small WAV
fragments shipped with the plugin — no server-side TTS, no extra dependencies,
and no `SpeechSynthesis` (which is unreliable on signage hardware such as
Samsung Tizen / MagicINFO).

A typical announcement plays as:

> *(chime)* "Now serving token, G, zero, zero, one"

The "Now serving token" prefix can be played in multiple languages back to
back for the same token — see [Multi-language announcements](#multi-language-announcements).
Tokens are deduplicated client-side via `localStorage`, so a given token is
announced at most once per display across page refreshes.

### Query parameters

| Param     | Default                  | Description                                                                                                                                  |
| --------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `va_mute` | off                      | `va_mute=1` (or `true`) suppresses the voice announcement entirely — the page is rendered without any announcer markup or script.            |
| `va_lang` | `VA_DEFAULT_LANG` setting | Comma-separated language codes for the prefix announcement (e.g. `en_IN`, `ml_IN,en_IN`). Each code must have a matching `prefix-<code>.wav`. |

### Multi-language announcements

The character/digit fragments and the chime are language-neutral and reused as-is.
Only the *"Now serving token"* prefix is recorded per language, named
`prefix-<lang>.wav` (for example `prefix-en_IN.wav`, `prefix-ml_IN.wav`).

The playback order is controlled by:

1. The `?va_lang=` query parameter, if present (comma-separated, e.g.
   `?va_lang=ml_IN,en_IN`).
2. Otherwise, the `VA_DEFAULT_LANG` plugin setting (default: `["en_IN"]`).

For each token, the announcer schedules every configured language pass
back-to-back with a 1-second pause between languages:

```
[chime] [prefix-ml_IN] [G] [0] [0] [1]
  ... 1 second pause ...
[chime] [prefix-en_IN] [G] [0] [0] [1]
```

An empty `?va_lang=` (or an empty `VA_DEFAULT_LANG`) suppresses voice
playback entirely while still rendering the visual display.

### Audio fragments

The fragments live under
`src/token_display/static/token_display/sounds/`:

| File                        | Contents                                                                |
| --------------------------- | ----------------------------------------------------------------------- |
| `chime.wav`                 | Two-tone leading chime (language-neutral).                              |
| `prefix-<lang>.wav`         | "Now serving token" recorded in `<lang>` (e.g. `prefix-en_IN.wav`).     |
| `A.wav` … `Z.wav`           | One file per English letter (language-neutral).                         |
| `0.wav` … `9.wav`           | One file per digit (language-neutral).                                  |

All files must share the same sample format (the bundled placeholders are
22.05 kHz mono 16-bit PCM, but the Web Audio API will resample anything it
can decode). Each fragment should bake in a short trailing pause (~120 ms) so
that consecutive characters do not slur together when concatenated.

### Replacing the placeholder voice

The shipped fragments are auto-generated placeholders using macOS's `say`
utility (or stdlib tones on other platforms). To swap in real recordings:

1. Record one WAV per fragment using the same filenames as above.
2. Use a single voice talent and a consistent peak level (~ -3 dBFS).
3. Trim leading silence aggressively; leave ~120 ms of trailing silence.
4. Drop the new files into
   `src/token_display/static/token_display/sounds/` — no code changes needed.

To regenerate the placeholders at any time, run:

```sh
python scripts/generate_placeholder_fragments.py
```

### Kiosk setup

Most browsers block autoplay until the user interacts with the page. For an
unattended kiosk, launch Chromium with:

```shell
chromium --kiosk \
  --autoplay-policy=no-user-gesture-required \
  "https://<your-care-host>/token_display/sub_queues/<sub_queue_external_ids>/?token=<api_token>"
```

If the display is opened in a normal browser tab, click anywhere on the page
once after loading to unlock audio.

### Graceful degradation

- If the Web Audio API is unavailable, the page renders silently and the
  currently shown tokens are recorded as "announced" so they do not loop on
  every refresh.
- If a fragment fails to load or decode, the announcement is aborted, the
  affected tokens are still marked as announced, and the page reloads on
  schedule.
- The `<meta http-equiv="refresh">` fallback still works with JavaScript
  disabled — the page refreshes on schedule but plays no audio.
