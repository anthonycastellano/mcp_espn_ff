# ESPN Fantasy Football MCP Server

## Overview

This MCP (Model Context Protocol) server allows LLMs like Claude to interact with the ESPN Fantasy Football API. It provides tools for accessing league data, team rosters, player statistics, and more through a standardized interface. It can work with both public and private ESPN Leagues.

## Features (MCP Tools)

- **Authentication**: Load ESPN credentials from environment variables, with optional per-session overrides
- **League Info**: Get basic information about fantasy football leagues
- **Team Rosters**: View current team rosters, lineup slots, and starter/bench status
- **Player Stats**: Find and display stats for specific players
- **League Standings**: View current team rankings and performance metrics
- **Matchup Information**: Get weekly scores, projections, complete lineups, and player lock/status details

## Installation

### Prerequisites

- Python 3.12 or higher
- `uv` package manager
- [Claude Desktop](https://claude.ai/download) for the best experience

### ESPN credentials for private leagues

Public leagues do not need credentials. For a private league, copy the example
file and add the `espn_s2` and `SWID` cookies from an authenticated ESPN browser
session:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` and replace both placeholders. The file is ignored by Git. The
server reads `ESPN_S2` and `SWID` from its process environment; `uv run
--env-file .env` loads them without exposing the cookie values to the MCP
client or model.

You can also store named league and team defaults so the MCP client does not
need to ask for IDs repeatedly:

```dotenv
ESPN_LEAGUE_1_NAME="Main league"
ESPN_LEAGUE_1_ID="123456789"
ESPN_LEAGUE_1_TEAM_ID="4"
```

Repeat the numbered block as `ESPN_LEAGUE_2_*`, `ESPN_LEAGUE_3_*`, and so on.
The tools use the current football season automatically. The
`get_configured_leagues` MCP tool exposes only this non-secret metadata to the
agent; authentication cookies are never included.

### Usage with Codex

Add this project-scoped configuration to `.codex/config.toml`:

```toml
[mcp_servers.espn_fantasy_football]
command = "/opt/homebrew/bin/uv"
args = [
  "--directory",
  "/absolute/path/to/mcp_espn_ff",
  "run",
  "--env-file",
  "/absolute/path/to/mcp_espn_ff/.env",
  "espn_fantasy_server.py",
]
startup_timeout_sec = 30
```

Restart Codex after creating or changing `.env`. The `authenticate` MCP tool is
still available when a temporary runtime override is needed.

### Usage with Claude Desktop

1. Update the Claude Desktop config:
- MacOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Include reference to the MCP server
  ```json
  {
    "mcpServers": {
      "espn-fantasy-football": {
        "command": "uv",
        "args": [
          "--directory",
          "/absolute/path/to/directory",
          "run",
          "--env-file",
          "/absolute/path/to/directory/.env",
          "espn_fantasy_server.py"
        ]
      }
    }
  }
  ```

2. Restart Claude Desktop


## Acknowledgements

[cwendt94/espn-api](https://github.com/cwendt94/espn-api) for the nifty python wrapper around the ESPN Fantasy API
