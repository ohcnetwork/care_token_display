# Usage

To use care_token_display in a project:

```python
import token_display
```

## Audio announcements

The display calls out new tokens using a chime followed by synthesized speech
generated **on the server** with [Piper TTS](https://github.com/rhasspy/piper).
The browser only plays a single WAV per announcement, so the feature works on
any signage display that can decode HTML5 audio — including Samsung Tizen /
MagicINFO WebViews where `SpeechSynthesis` is unavailable.

Each unique announcement is hashed by `(voice, text)` and cached on disk; only
the first request renders audio, subsequent requests are served from cache.
Announcements are also deduplicated client-side via `localStorage`, so a given
token is announced at most once per display across page refreshes.

### Query parameters

| Param   | Default               | Description                                                                                                         |
| ------- | --------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `lang`  | `en-US`               | BCP-47 tag. Currently informational; voice selection takes precedence.                                              |
| `voice` | `TTS_DEFAULT_VOICE`   | Voice id from `TTS_VOICE_CATALOG`. Unknown values fall back to the default; an unknown id with no default → 400.    |
| `mute`  | off                   | `mute=1` skips audio. Dedup state is still maintained.                                                              |

The default catalog ships with these voices (extend via the `TTS_VOICE_CATALOG`
plugin setting):

| Voice id                  | Language |
| ------------------------- | -------- |
| `en_US-amy-medium`        | en-US    |
| `en_US-ryan-high`         | en-US    |
| `en_GB-alan-medium`       | en-GB    |
| `hi_IN-pratham-medium`    | hi-IN    |
| `hi_IN-priyamvada-medium` | hi-IN    |
| `ml_IN-arjun-medium`      | ml-IN    |
| `ml_IN-meera-medium`      | ml-IN    |

### Announcement format

> Token `<code spelled out>`, please proceed to `<resource name>`

For example, `G-001` assigned to *Dr. Smith* becomes
*"Token G, zero zero one, please proceed to Dr. Smith."*

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

- If the announcement endpoint returns an error (e.g. voice model not yet
  downloaded and no internet), the page still renders silently and the offending
  token is recorded as "announced" so it does not loop on every refresh.
- The `<meta http-equiv="refresh">` fallback still works with JavaScript
  disabled — the page refreshes on schedule but plays no audio.
