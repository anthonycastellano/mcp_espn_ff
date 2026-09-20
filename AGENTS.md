# AGENTS.md

This file provides guidance to coding agents working in this repository.

## ESPN Fantasy Football MCP Routing

- For prompts about ESPN fantasy football leagues, teams, rosters, players,
  standings, scores, or weekly matchups, always call the
  `espn_fantasy_football` MCP server and use its returned data. Do not answer
  league-specific questions from memory or by guessing.
- When a prompt does not provide an explicit league ID, call
  `get_configured_leagues` first and resolve the requested league or team from
  its name, league ID, and team ID. Ask the user only when the configured
  records are missing or genuinely ambiguous.
- Choose the narrowest applicable MCP tool. Ask for a league ID, team ID, week,
  or year only when the request cannot be completed without it.
- Private-league credentials are loaded automatically from the server's
  `ESPN_S2` and `SWID` environment variables. Do not ask the user for cookies or
  call `authenticate` unless automatic authentication fails and the user
  explicitly wants a temporary override.
- Never repeat, log, or expose ESPN cookie values in responses.
- Repository implementation, debugging, and documentation questions do not
  require an ESPN data tool call unless they also ask for live fantasy-football
  data.

## Project Overview

This is an MCP (Model Context Protocol) server that provides LLMs like Claude with tools to interact with the ESPN Fantasy Football API. The server wraps the `espn-api` Python library and exposes its functionality through MCP tools.

## Running the Server

The server is designed to be run by MCP clients like Claude Desktop. To test locally:

```bash
uv run espn_fantasy_server.py
```

## Architecture

### Single-File MCP Server
The entire server implementation is in `espn_fantasy_server.py`. It uses the FastMCP framework to define MCP tools.

### Core Components

1. **ESPNFantasyFootballAPI Class** (lines 29-72)
   - Manages ESPN league instances with caching
   - Loads ESPN_S2 and SWID cookies from the environment
   - Supports temporary per-session credential overrides
   - Uses cache keys that include authentication info to support both public and private leagues

2. **Session Management**
   - Uses a simple `SESSION_ID = "default_session"` approach
   - Environment credentials are the default; runtime overrides are stored in `api.credentials`
   - League instances are cached with keys that include auth info: `{league_id}_{year}_{espn_s2}_{swid}`

3. **Football Year Logic** (lines 23-25)
   - Defaults to current calendar year
   - If before July, uses previous year (since NFL season spans calendar years)

### MCP Tools

The server exposes 9 tools (all async functions decorated with `@mcp.tool()`):

- `authenticate()` - Temporarily override ESPN credentials for the current session
- `get_configured_leagues()` - List configured league names, league IDs, and team IDs
- `get_league_info()` - Basic league information
- `get_team_roster()` - Player roster for a specific team
- `get_team_info()` - Team statistics and transaction info
- `get_player_stats()` - Stats for a specific player by name
- `get_league_standings()` - Current standings sorted by wins/points
- `get_matchup_info()` - Weekly matchup details
- `logout()` - Clear stored credentials

### Error Handling

All tools:
- Use try/except blocks with logging to stderr via `log_error()`
- Check for 401 errors or "Private" in exceptions to detect private league access issues
- Return user-friendly string messages (not JSON) since MCP converts them

### ESPN API Integration

- Uses the `espn_api.football.League` class from the espn-api package
- Team IDs are 1-based in the ESPN API (teams[0] is team_id=1)
- League objects are cached to avoid repeated API calls
- Private leagues require ESPN_S2 and SWID cookies (obtained from browser after logging into ESPN)

## Dependencies

Managed via `pyproject.toml` with uv:
- `espn-api>=0.44.1` - ESPN Fantasy Football API wrapper
- `mcp[cli]>=1.5.0` - Model Context Protocol framework

## Key Implementation Details

### Credential Storage
Credentials default to the `ESPN_S2` and `SWID` process environment variables.
The `authenticate` tool can store a temporary per-session override in memory,
though the current implementation uses a single default session ID.

### Logging
The server logs extensively to stderr using `log_error()` function. This is important for debugging in Claude Desktop, which captures stderr output.

### Error Recovery
The server initialization is wrapped in a try/except that keeps the process running even if initialization fails, allowing logs to be visible (lines 368-377).

## Testing Considerations

When testing tools:
- Use a public league first (doesn't require authentication)
- For private leagues, populate `.env` and launch the server with `uv run --env-file .env`
- Team IDs start at 1, not 0
- Week numbers are typically 1-17 for most leagues
