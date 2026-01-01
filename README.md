# care_token_display

A Django plugin for Care that provides server-side rendered (SSR) token display pages with automatic refresh using HTMX. The plugin displays current token information for multiple service point sub-queues in a responsive grid layout.

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

## Configuration

The plugin supports the following configuration options via `PLUGIN_CONFIGS` in your Django settings:

```python
PLUGIN_CONFIGS = {
    "token_display": {
        "TOKEN_DISPLAY_REFRESH_INTERVAL": 10,  # Auto-refresh interval in seconds (default: 10)
        "TOKEN_DISPLAY_CACHE_TIMEOUT": 60,      # Cache timeout in seconds (default: 60)
    }
}
```

### Configuration Options

- **TOKEN_DISPLAY_REFRESH_INTERVAL**: How often (in seconds) each sub-queue card should refresh its data. Default: 10 seconds.
- **TOKEN_DISPLAY_CACHE_TIMEOUT**: How long (in seconds) to cache the rendered partial views. Should be longer than refresh interval. Default: 60 seconds.

## Usage

### URL Structure

#### Main Display Page

To display tokens for multiple sub-queues:

```
/token_display/sub_queues/<uuid1>,<uuid2>,<uuid3>,.../
```

This will render a responsive grid showing token information for all three sub-queues, with each card auto-refreshing every 10 seconds (or your configured interval).

**Note**: Only active sub-queues (with `status=active`) are displayed. Invalid or inactive sub-queue IDs are filtered out.

## How It Works

### Architecture

1. **Initial Load**: The main view renders a full HTML page with HTMX setup
2. **Auto-Refresh**: Each sub-queue card uses HTMX to poll its partial endpoint at configured intervals
3. **Caching**: Partial views are cached to reduce database load
4. **Cache Invalidation**: Django signals automatically invalidate cache when:
   - A Token is saved (status changes, sub_queue changes, etc.)
   - A TokenQueue is updated

### Cache Invalidation

The plugin uses Django signals to automatically invalidate cache when relevant data changes:

- **Token Updates**: When any Token is saved, the cache for its sub-queue is invalidated or if a token has no sub_queue, the cache for all sub-queues in that token's queue resource is invalidated
- **Queue Updates**: When a TokenQueue is updated, all sub-queues for that resource are invalidated

This ensures the display always shows current data without manual cache management.

### Grid Layout

The plugin automatically adjusts the grid layout based on the number of sub-queues:

- **1 sub-queue**: Single column layout
- **2-4 sub-queues**: 2-column grid
- **5+ sub-queues**: 3-column grid (6-column base with smart column spanning)

The layout handles edge cases like odd numbers of items in the last row.

## Development

### Dependencies

- Django
- HTMX (loaded via CDN in templates)
- Django cache framework (uses project's cache backend)

### Project Structure

```
src/token_display/
├── views.py          # View classes for main page and partial views
├── urls.py           # URL routing
├── templates/        # Django templates
│   └── token_display/
│       ├── display.html  # Main display page
│       └── partial.html  # Partial view template
├── signals.py        # Cache invalidation signal handlers
├── utils.py          # Utility functions (cache keys, formatting)
└── settings.py       # Plugin settings configuration
```

## Notes

- The UI is designed to work on displays that may not support modern CSS features
- 
---

This plugin was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) using the [ohcnetwork/care-plugin-cookiecutter](https://github.com/ohcnetwork/care-plugin-cookiecutter).
