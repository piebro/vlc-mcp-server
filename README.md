# VLC MCP Server

An MCP (Model Contex Protocol) Server to play and control movies using VLC.
I use this MCP server together with my [signal-mcp-client](https://github.com/piebro/signal-mcp-client) on an old laptop connected to my beamer.
This way I can play a movie from my laptop by sending a signal message.

The Anthropic API key is used to use claude-haiku to summarize all existing videos in your video folder.

## Usage

This installation is for Linux systems running Ubuntu or a similar Debian-based system like Raspberry Pi OS.
With a few modifications it should also work on other systems.
Feel free to create a pull request if you get it working on another system.

1. Install VLC, mediainfo and uv.
    ```bash
    sudo apt-get install vlc mediainfo
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2. Start the VLC http server:
    ```bash
    export DISPLAY=:0 # needed when running it remotely on a server
    vlc --extraintf=http --http-host=localhost --http-port=8081 --http-password=your_password
    ```
3. Add the server to the MCP config file of your client.
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
            "VLC_HTTP_PORT": "8081",
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

## Contributing

Contributions to this project are welcome. Feel free to report bugs, suggest ideas, or create merge requests.


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
    --client_log_level "INFO" \
	--server_log_level "INFO" \
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

To release a new version of the package to PyPI, create and push a new Git tag:

1. Checkout the main branch and get the current version:
   ```bash
   git checkout main
   git pull origin main
   git describe --tags
   ```

2. Create and push a new Git tag:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

The GitHub Actions workflow will automatically build and publish the package to PyPI when a new tag is pushed.
The python package version number will be derived directly from the Git tag.

## Running as a Systemd Service

To ensure the VLC HTTP interface runs automatically on boot and restarts if it fails (on Linux systems), you can set it up as a systemd user service.
User services run under your specific user account.

This setup assumes that you have completed the setup steps.

1. Enable User Lingering to keep your user session active after logging out.
    ```bash
    sudo loginctl enable-linger $USER
    ```

2. Create Systemd Service Directory
    ```bash
    mkdir -p /home/$USER/.config/systemd/user/
    ```
3. Create Service File for VLC HTTP Server.
Make sure vlc is installed using apt and not using snap or change the path to the vlc binary.
    ```bash
    cat << EOF > "/home/$USER/.config/systemd/user/vlc-http.service"
    [Unit]
    Description=VLC Media Player with HTTP Interface
    After=network.target sound.target

    [Service]
    Restart=on-failure
    RestartSec=30
    SyslogIdentifier=vlc-http
    Environment="DISPLAY=:0"

    ExecStart=/usr/bin/vlc --extraintf=http --http-host=localhost --http-port=8081 --http-password=your_password

    ExecStop=/usr/bin/pkill -f '/usr/bin/vlc --extraintf=http --http-host=localhost --http-port=8080'

    [Install]
    WantedBy=default.target
    EOF
    ```

4. Enable and Start the Services
    ```bash
    systemctl --user daemon-reload
    systemctl --user enable vlc-http.service
    systemctl --user start vlc-http.service
    ```


5. Check Service Status and Logs
    ```bash
    systemctl --user status vlc-http.service
    journalctl --user -u vlc-http.service -f
    ```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.