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

## Usage

### URL Structure

#### Main Display Page

To display tokens for multiple sub-queues:

```
/token_display/sub_queues/<uuid1>,<uuid2>,<uuid3>,.../
```

This will render a responsive grid showing a static snapshot of current token information for all sub-queues. The page must be manually refreshed to see updated data.

**Note**: Only active sub-queues (with `status=active`) are displayed. Invalid or inactive sub-queue IDs are filtered out.

## How It Works

The plugin provides a simple server-side rendered page that displays current token information:

1. **Request**: The view receives comma-separated sub-queue UUIDs
2. **Data Fetching**: For each sub-queue, the plugin fetches the current in-progress token
3. **Rendering**: All data is rendered in a single HTML response with a responsive grid layout
4. **Static Display**: The page shows a snapshot of data at request time - manual refresh is required to see updates

### Grid Layout

The plugin automatically adjusts the grid layout based on the number of sub-queues:

- **1 sub-queue**: Single column layout
- **2-4 sub-queues**: 2-column grid
- **5+ sub-queues**: 3-column grid (6-column base with smart column spanning)

The layout handles edge cases like odd numbers of items in the last row.

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

- The UI is designed to work on displays that may not support modern CSS features
- The page displays a static snapshot of token data at the time of request
- Users must manually refresh the browser to see updated token information


---

This plugin was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) using the [ohcnetwork/care-plugin-cookiecutter](https://github.com/ohcnetwork/care-plugin-cookiecutter).
