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

## Audio announcements

Audio is assembled in the browser from pre-recorded WAV fragments shipped
with the plugin. There are no additional Python dependencies, no system
packages (e.g. `ffmpeg`, `espeak`) and no server-side text-to-speech
required. See [Audio announcements in *Usage*](usage.md#audio-announcements)
for how to replace the placeholder voice.
