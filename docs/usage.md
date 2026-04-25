# Usage

To use care_token_display in a project:

```python
import token_display
```

## Audio announcements

The display announces new tokens out loud using the browser's Web Speech API.
An announcement consists of a short chime followed by synthesized speech in the
form:

> Token `<spelled code>`, please proceed to `<resource name>`

For example, token `G-001` assigned to `Dr. Smith` is spoken as
*"Token G, 0 0 1, please proceed to Dr. Smith"*.

Announcements are deduplicated across page refreshes via `localStorage`, so a
given token is announced at most once per display.

### Query parameters

| Param   | Default  | Description                                                                                          |
| ------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `lang`  | `en-US`  | BCP-47 tag (e.g. `en-GB`, `ml-IN`, `hi-IN`). Falls back to default if the tag is invalid or unknown. |
| `mute`  | off      | `mute=1` disables audio entirely. Dedup state is still maintained.                                   |

The device's operating system must ship a voice for the requested language; if
not, the browser's default voice is used.

### Kiosk setup

Most browsers block autoplay until the user interacts with the page. For an
unattended kiosk, launch Chromium with:

```shell
chromium --kiosk \
  --autoplay-policy=no-user-gesture-required \
  "https://<your-care-host>/token-display/<sub_queue_external_ids>/"
```

If the display is opened in a normal browser tab, click anywhere on the page
once after loading to unlock audio.

### Graceful degradation

- If `SpeechSynthesis` is unavailable, the page renders silently and all
  currently shown tokens are recorded as "announced" to avoid a burst when
  moved to a capable browser later.
- The `<meta http-equiv="refresh">` fallback still works with JavaScript
  disabled — the page refreshes on schedule but plays no audio.
