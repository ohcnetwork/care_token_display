# care_token_display

A Django plugin for Care that provides server-side rendered (SSR) token display
pages for clinic waiting-room TV signage. The plugin renders current and
upcoming token information for multiple service-point sub-queues as a
full-screen queue board, with an optional auto-refresh interval and voice
announcements.

## Local Development

To develop the plug in local environment along with care, follow the steps below:

1. Go to the care root directory and clone the plugin repository:

```bash
cd care
git clone git@github.com:ohcnetwork/care_token_display.git
```

2. Add the plugin config in plug_config.py

```python
...

care_token_display_plugin = Plug(
    name=care_token_display, # name of the django app in the plugin
    package_name="/app/care_token_display", # this has to be /app/ + plugin folder name
    version="", # keep it empty for local development
    configs={}, # plugin configurations if any
)
plugs = [care_token_display_plugin]

...
```

3. Tweak the code in plugs/manager.py, install the plugin in editable mode

```python
...

subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-e", *packages] # add -e flag to install in editable mode
)

...
```

4. Rebuild the docker image and run the server

```bash
make re-build
make up
```

> [!IMPORTANT]
> Do not push these changes in a PR. These changes are only for local development.

## Production Setup

To install care care_token_display, you can add the plugin config in [care/plug_config.py](https://github.com/ohcnetwork/care/blob/develop/plug_config.py) as follows:

```python
...

care_token_display_plug = Plug(
    name=care_token_display,
    package_name="git+https://github.com/ohcnetwork/care_token_display.git",
    version="@master",
    configs={},
)
plugs = [care_token_display_plug]
...
```

[Extended Docs on Plug Installation](https://care-be-docs.ohc.network/pluggable-apps/configuration.html)

## Usage

### URL Structure

#### Main Display Page

To display tokens for multiple sub-queues:

```
/token_display/sub_queues/<uuid1>,<uuid2>,<uuid3>,.../
```

This will render a full-screen queue board showing current and upcoming token information for all sub-queues. The page reloads automatically when an auto-refresh interval (or voice announcements) is configured; otherwise it shows a snapshot and must be refreshed manually.

**Note**: Only active sub-queues (with `status=active`) are displayed. Invalid or inactive sub-queue IDs are filtered out.

## How It Works

The plugin provides a simple server-side rendered page that displays current token information:

1. **Request**: The view receives comma-separated sub-queue UUIDs
2. **Data Fetching**: For each sub-queue, the plugin fetches the current in-progress token and the next two upcoming tokens
3. **Layout selection**: The view inspects the resource type behind each sub-queue to pick the practitioner or counter board layout (see [Layout](#layout))
4. **Rendering**: All data is rendered in a single HTML response as a full-screen table board
5. **Refresh**: When an auto-refresh interval is configured the page reloads via a `<meta http-equiv="refresh">` tag; when voice announcements are enabled the announcer coordinates the reload so audio is never cut off

### Layout

The page renders as a full-screen, rounded TV queue board. The board adapts to
the type of scheduled resource behind each sub-queue:

**Practitioner boards** (`Doctor | Room | Token`)

Used when at least one sub-queue is backed by a practitioner. A fixed header
labels three columns and each sub-queue is one row showing:

- the resource name (**Doctor**),
- the sub-queue name as a bordered badge (**Room**), and
- the current token plus the next two upcoming tokens (**Token**).

**Counter boards** (`Counter | Token`)

Used when _every_ sub-queue is backed by a non-practitioner resource (a
healthcare service or a location) — e.g. pharmacy or billing counters. The
Doctor column is dropped and the badge column is relabelled **Counter**.

In both layouts the rows are equal height and shrink to fit the viewport, so all
sub-queues stay visible on a fixed TV screen without scrolling. Font sizes scale
fluidly with the smaller viewport dimension (`vmin`), keeping the board readable
across landscape, portrait, and 4:3 screens.

## Development

### Dependencies

- Django
- Django REST Framework

### Project Structure

```
src/token_display/
├── views.py          # View class for token display page
├── pages.py          # URL routing for UI pages
├── urls.py           # URL routing for API endpoints
├── templates/        # Django templates
│   └── token_display/
│       └── display.html  # Main display page
├── utils.py          # Utility functions (formatting helpers)
├── settings.py       # Plugin settings configuration
└── authentication.py # Custom authentication classes
```

## Notes

- The board styling follows the Care UI `tv-display` design (dark board, lime
  header, bordered badges, animated current token).
- With no auto-refresh interval configured, the page shows a static snapshot at
  request time and must be refreshed manually.
- Setting an auto-refresh interval (or enabling voice announcements) makes the
  page reload on its own to pick up new tokens.


---

This plugin was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) using the [ohcnetwork/care-plugin-cookiecutter](https://github.com/ohcnetwork/care-plugin-cookiecutter).
