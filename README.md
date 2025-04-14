# VLC MCP Server

An MCP (Model Contex Protocol) Server to play and control movies using VLC.
I use this MCP server together with my [signal-mcp-client](https://github.com/piebro/signal-mcp-client) on a Raspberry PI connected to my beamer.
This way I can save video to a folder on my PI and I can send a signal message to play a movie.

The Anthropic API key is used to use claude-haiku to summarize all existing videos in your video folder.

## Usage

The server uses the VLC http interface to play and control movies.
Install VLC and start the http server with the following command:

```bash
vlc --extraintf=http --http-host=localhost --http-port=8080 --http-password=your_password
```

You also need to install mediainfo to get the subtitles:

*Note: I don't know if this library is available on Mac and Windows. If you want to use it there, you can might need to disable using subtitles or find an alternative.*

```bash
sudo apt-get install mediainfo
```

Then install [uv](https://docs.astral.sh/uv/) and add the server to an MCP config using `uvx`:

```json
{
    "name": "vlc-mcp-server",
    "command": "uvx",
    "args": [
        "vlc-mcp-server"
    ],
    "env": {
        "ANTHROPIC_API_KEY": "your-key",
        "ROOT_VIDEO_FOLDER": "path/to/your/video/folder",
        "VLC_HTTP_HOST": "localhost",
        "VLC_HTTP_PORT": "8080",
        "VLC_HTTP_PASSWORD": "your_password"
    }
}
```

or clone the repo and use `uv` with a directory:

```json
{
    "name": "vlc-mcp-server",
    "command": "uv",
    "args": [
        "--directory",
        "path/to/root/dir/",
        "run",
        "vlc_mcp_player/main.py"
    ],
    "env": {
        "the same as above"
    }
}
```

## Development

### Testing

Clone the repo and use [mcp-client-for-testing](https://github.com/piebro/mcp-client-for-testing) to test the tools of the server.

```bash
uvx mcp-client-for-testing \
    --config '
    [
        "the json config from above"
    ]
    ' \
    --tool_call '{"name": "show_video", "arguments": {"video_title": "David Lynch - Dune", "subtitle_language_code": "en"}}'
```

### Formatting and Linting

The code is formatted and linted with ruff:

```bash
uv run ruff format
uv run ruff check --fix
```

### Building with uv

Build the package using uv:

```bash
uv build
```

### Releasing a New Version

To release a new version of the package to PyPI:

1. Create and push a new Git tag following semantic versioning:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

The GitHub Actions workflow will automatically build and publish the package to PyPI when a new tag is pushed. The version number will be derived directly from the Git tag.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.