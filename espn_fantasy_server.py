from mcp.server.fastmcp import FastMCP
from espn_api.football import League
import os
import sys
import datetime
import logging
import traceback


NON_STARTING_SLOTS = {"BE", "IR", "ER", "FA"}


def is_starting_slot(lineup_slot):
    """Return whether an ESPN lineup slot counts toward the active lineup."""
    return bool(lineup_slot) and lineup_slot not in NON_STARTING_SLOTS


def serialize_box_player(player):
    """Convert an espn-api BoxPlayer into MCP-safe weekly lineup data."""
    lineup_slot = getattr(player, "slot_position", None) or getattr(player, "lineupSlot", None)
    game_date = getattr(player, "game_date", None)
    on_bye_week = bool(getattr(player, "on_bye_week", False))

    locked = False
    if game_date is not None and not on_bye_week:
        now = datetime.datetime.now(game_date.tzinfo) if game_date.tzinfo else datetime.datetime.now()
        locked = now >= game_date

    return {
        "name": player.name,
        "position": player.position,
        "lineup_slot": lineup_slot,
        "is_starter": is_starting_slot(lineup_slot),
        "pro_team": player.proTeam,
        "opponent": getattr(player, "pro_opponent", None),
        "points": getattr(player, "points", 0),
        "projected_points": getattr(player, "projected_points", 0),
        "game_date": game_date.isoformat() if game_date else None,
        "game_played": getattr(player, "game_played", 0),
        "locked": locked,
        "on_bye_week": on_bye_week,
        "active_status": getattr(player, "active_status", None),
        "injury_status": getattr(player, "injuryStatus", None),
        "injured": bool(getattr(player, "injured", False)),
    }


# Set up logging
logging.basicConfig(level=logging.INFO)

# Add stderr logging for Claude Desktop to see
def log_error(message):
    print(message, file=sys.stderr)

try:
    # Initialize FastMCP server
    log_error("Initializing FastMCP server...")
    mcp = FastMCP("espn-fantasy-football", dependencies=['espn-api'])

    # Constants
    CURRENT_YEAR = datetime.datetime.now().year
    if datetime.datetime.now().month < 7:  # If before July, use previous year
        CURRENT_YEAR -= 1

    log_error(f"Using football year: {CURRENT_YEAR}")

    SESSION_ID = "default_session"

    class ESPNFantasyFootballAPI:
        def __init__(self):
            self.leagues = {}  # Cache for league objects
            # Runtime credentials override environment credentials per session.
            self.credentials = {}

            espn_s2, swid = self.get_credentials(SESSION_ID)
            if espn_s2 and swid:
                log_error("ESPN credentials detected in the environment.")
            elif espn_s2 or swid:
                log_error("Incomplete ESPN credentials: both ESPN_S2 and SWID must be set.")
            else:
                log_error("No ESPN credentials detected; public leagues remain available.")

        def get_credentials(self, session_id):
            """Return a runtime override, falling back to process environment variables."""
            if session_id in self.credentials:
                credentials = self.credentials[session_id]
                return credentials.get("espn_s2"), credentials.get("swid")

            return os.getenv("ESPN_S2"), os.getenv("SWID")

        def environment_credentials_configured(self):
            """Return whether both ESPN credential environment variables are present."""
            return bool(os.getenv("ESPN_S2") and os.getenv("SWID"))

        def get_configured_leagues(self):
            """Return non-secret league metadata from indexed environment variables."""
            leagues = []
            for index in range(1, 100):
                prefix = f"ESPN_LEAGUE_{index}_"
                values = {
                    "name": os.getenv(f"{prefix}NAME", "").strip(),
                    "league_id": os.getenv(f"{prefix}ID", "").strip(),
                    "team_id": os.getenv(f"{prefix}TEAM_ID", "").strip(),
                }
                if not any(values.values()):
                    continue

                league = {
                    "slot": index,
                    "name": values["name"] or f"League {index}",
                }
                errors = []
                for source, destination, env_suffix in (
                    ("league_id", "league_id", "ID"),
                    ("team_id", "team_id", "TEAM_ID"),
                ):
                    value = values[source]
                    if not value:
                        league[destination] = None
                        if source == "league_id":
                            errors.append(f"{prefix}ID is required")
                        continue
                    try:
                        league[destination] = int(value)
                    except ValueError:
                        league[destination] = None
                        errors.append(f"{prefix}{env_suffix} must be an integer")

                if errors:
                    league["configuration_errors"] = errors
                leagues.append(league)

            return leagues
        
        def get_league(self, session_id, league_id, year=CURRENT_YEAR):
            """Get a league instance with caching, using stored credentials if available"""
            key = f"{league_id}_{year}"
            
            espn_s2, swid = self.get_credentials(session_id)
            if bool(espn_s2) != bool(swid):
                raise ValueError("Both ESPN_S2 and SWID must be set together.")
            
            # Create league cache key including auth info
            cache_key = f"{key}_{espn_s2}_{swid}"
            
            if cache_key not in self.leagues:
                log_error(f"Creating new league instance for {league_id}, year {year}")
                try:
                    self.leagues[cache_key] = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
                except Exception as e:
                    log_error(f"Error creating league: {str(e)}")
                    raise
            
            return self.leagues[cache_key]
        
        def store_credentials(self, session_id, espn_s2, swid):
            """Store credentials for a session"""
            self.credentials[session_id] = {
                'espn_s2': espn_s2,
                'swid': swid
            }
            log_error(f"Stored credentials for session {session_id}")
        
        def clear_credentials(self, session_id):
            """Clear credentials for a session"""
            if session_id in self.credentials:
                del self.credentials[session_id]
                log_error(f"Cleared credentials for session {session_id}")

    # Create our API instance
    api = ESPNFantasyFootballAPI()

    @mcp.tool()
    async def authenticate(espn_s2: str, swid: str) -> str:
        """Temporarily override ESPN authentication credentials for this session.

        Normally credentials are loaded automatically from the ESPN_S2 and SWID
        environment variables. Use this tool only when a temporary override is needed.
        
        Args:
            espn_s2: The ESPN_S2 cookie value from your ESPN account
            swid: The SWID cookie value from your ESPN account
        """
        try:
            log_error("Authenticating...")
            if not espn_s2 or not swid:
                return "Both espn_s2 and swid are required."
            # Store credentials for this session
            api.store_credentials(SESSION_ID, espn_s2, swid)
            
            return "Authentication override stored for this session only."
        except Exception as e:
            log_error(f"Authentication error: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            return f"Authentication error: {str(e)}"

    @mcp.tool()
    async def get_configured_leagues() -> str:
        """List league and team metadata configured in the server environment.

        This returns non-secret names, league IDs, and team IDs. It never
        returns ESPN authentication cookies.
        """
        try:
            leagues = api.get_configured_leagues()
            if not leagues:
                return ("No leagues are configured. Add ESPN_LEAGUE_1_ID and related "
                        "ESPN_LEAGUE_<N>_* values to the server environment.")
            return str(leagues)
        except Exception as e:
            log_error(f"Error retrieving configured leagues: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            return f"Error retrieving configured leagues: {str(e)}"

    @mcp.tool()
    async def get_league_info(league_id: int, year: int = CURRENT_YEAR) -> str:
        """Get basic information about a fantasy football league.
        
        Args:
            league_id: The ESPN fantasy football league ID
            year: Optional year for historical data (defaults to current season)
        """
        try:
            log_error(f"Getting league info for league {league_id}, year {year}")
            # Get league using stored credentials
            league = api.get_league(SESSION_ID, league_id, year)
            
            info = {
                "name": league.settings.name,
                "year": league.year,
                "current_week": league.current_week,
                "nfl_week": league.nfl_week,
                "team_count": len(league.teams),
                "teams": [team.team_name for team in league.teams],
                "scoring_type": league.settings.scoring_type,
            }
            
            return str(info)
        except Exception as e:
            log_error(f"Error retrieving league info: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            if "401" in str(e) or "Private" in str(e):
                return ("This appears to be a private league. Set ESPN_S2 and SWID in the server environment "
                      "or use the authenticate tool with those cookies.")
            return f"Error retrieving league: {str(e)}"

    @mcp.tool()
    async def get_team_roster(league_id: int, team_id: int, year: int = CURRENT_YEAR) -> str:
        """Get a team's current roster.
        
        Args:
            league_id: The ESPN fantasy football league ID
            team_id: The team ID in the league (usually 1-12)
            year: Optional year for historical data (defaults to current season)
        """
        try:
            log_error(f"Getting team roster for league {league_id}, team {team_id}, year {year}")
            # Get league using stored credentials
            league = api.get_league(SESSION_ID, league_id, year)
            
            # Team IDs in ESPN API are 1-based
            if team_id < 1 or team_id > len(league.teams):
                return f"Invalid team_id. Must be between 1 and {len(league.teams)}"
            
            team = league.teams[team_id - 1]
            
            roster_info = {
                "team_name": team.team_name,
                "owner": team.owners,
                "wins": team.wins,
                "losses": team.losses, 
                "roster": []
            }
            
            for player in team.roster:
                lineup_slot = getattr(player, "lineupSlot", None)
                roster_info["roster"].append({
                    "name": player.name,
                    "position": player.position,
                    "lineup_slot": lineup_slot,
                    "is_starter": is_starting_slot(lineup_slot),
                    "proTeam": player.proTeam,
                    "points": player.total_points,
                    "projected_points": player.projected_total_points,
                    "stats": player.stats,
                    "injury_status": getattr(player, "injuryStatus", None),
                    "injured": bool(getattr(player, "injured", False)),
                })
            
            return str(roster_info)
        except Exception as e:
            log_error(f"Error retrieving team roster: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            if "401" in str(e) or "Private" in str(e):
                return ("This appears to be a private league. Set ESPN_S2 and SWID in the server environment "
                      "or use the authenticate tool with those cookies.")
            return f"Error retrieving team roster: {str(e)}"
        
    @mcp.tool()
    async def get_team_info(league_id: int, team_id: int, year: int = CURRENT_YEAR) -> str:
        """Get a team's general information. Including points scored, transactions, etc.

        Args:
            league_id: The ESPN fantasy football league ID
            team_id: The team ID in the league (usually 1-12)
            year: Optional year for historical data (defaults to current season)
        """
        try:
            log_error(f"Getting team info for league {league_id}, team {team_id}, year {year}")
            # Get league using stored credentials
            league = api.get_league(SESSION_ID, league_id, year)

            # Team IDs in ESPN API are 1-based
            if team_id < 1 or team_id > len(league.teams):
                return f"Invalid team_id. Must be between 1 and {len(league.teams)}"
            
            team = league.teams[team_id - 1]

            team_info = {
                "team_name": team.team_name,
                "owner": team.owners,
                "wins": team.wins,
                "losses": team.losses,
                "ties": team.ties,
                "points_for": team.points_for,
                "points_against": team.points_against,
                "acquisitions": team.acquisitions,
                "drops": team.drops,
                "trades": team.trades,
                "playoff_pct": team.playoff_pct,
                "final_standing": team.final_standing,
                "outcomes": team.outcomes
            }
            
            return str(team_info)

        except Exception as e:
            log_error(f"Error retrieving team results: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            if "401" in str(e) or "Private" in str(e):
                return ("This appears to be a private league. Set ESPN_S2 and SWID in the server environment "
                      "or use the authenticate tool with those cookies.")
            return f"Error retrieving team results: {str(e)}"

    @mcp.tool()
    async def get_player_stats(league_id: int, player_name: str, year: int = CURRENT_YEAR) -> str:
        """Get stats for a specific player.
        
        Args:
            league_id: The ESPN fantasy football league ID
            player_name: Name of the player to search for
            year: Optional year for historical data (defaults to current season)
        """
        try:
            log_error(f"Getting player stats for {player_name} in league {league_id}, year {year}")
            # Get league using stored credentials
            league = api.get_league(SESSION_ID, league_id, year)
            
            # Search for player by name
            player = None
            for team in league.teams:
                for roster_player in team.roster:
                    if player_name.lower() in roster_player.name.lower():
                        player = roster_player
                        break
                if player:
                    break
            
            if not player:
                return f"Player '{player_name}' not found in league {league_id}"
            
            # Get player stats
            stats = {
                "name": player.name,
                "position": player.position,
                "team": player.proTeam,
                "points": player.total_points,
                "projected_points": player.projected_total_points,
                "stats": player.stats,
                "injured": player.injured
            }
            
            return str(stats)
        except Exception as e:
            log_error(f"Error retrieving player stats: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            if "401" in str(e) or "Private" in str(e):
                return ("This appears to be a private league. Set ESPN_S2 and SWID in the server environment "
                      "or use the authenticate tool with those cookies.")
            return f"Error retrieving player stats: {str(e)}"

    @mcp.tool()
    async def get_league_standings(league_id: int, year: int = CURRENT_YEAR) -> str:
        """Get current standings for a league.
        
        Args:
            league_id: The ESPN fantasy football league ID
            year: Optional year for historical data (defaults to current season)
        """
        try:
            log_error(f"Getting league standings for league {league_id}, year {year}")
            # Get league using stored credentials
            league = api.get_league(SESSION_ID, league_id, year)
            
            # Sort teams by wins (descending), then points (descending)
            sorted_teams = sorted(league.teams, 
                                key=lambda x: (x.wins, x.points_for),
                                reverse=True)
            
            standings = []
            for i, team in enumerate(sorted_teams):
                standings.append({
                    "rank": i + 1,
                    "team_name": team.team_name,
                    "owner": team.owners,
                    "wins": team.wins,
                    "losses": team.losses,
                    "points_for": team.points_for,
                    "points_against": team.points_against
                })
            
            return str(standings)
        except Exception as e:
            log_error(f"Error retrieving league standings: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            if "401" in str(e) or "Private" in str(e):
                return ("This appears to be a private league. Set ESPN_S2 and SWID in the server environment "
                      "or use the authenticate tool with those cookies.")
            return f"Error retrieving league standings: {str(e)}"

    @mcp.tool()
    async def get_matchup_info(league_id: int, week: int = None, year: int = CURRENT_YEAR) -> str:
        """Get matchup information for a specific week.
        
        Args:
            league_id: The ESPN fantasy football league ID
            week: The week number (if None, uses current week)
            year: Optional year for historical data (defaults to current season)
        """
        try:
            log_error(f"Getting matchup info for league {league_id}, week {week}, year {year}")
            # Get league using stored credentials
            league = api.get_league(SESSION_ID, league_id, year)
            
            if week is None:
                week = league.current_week
                
            if week < 1 or week > 17:  # Most leagues have 17 weeks max
                return f"Invalid week number. Must be between 1 and 17"
            
            matchups = league.box_scores(week)
            
            matchup_info = []
            for matchup in matchups:
                matchup_info.append({
                    "home_team": matchup.home_team.team_name,
                    "home_score": matchup.home_score,
                    "home_projected": matchup.home_projected,
                    "home_lineup": [serialize_box_player(player) for player in matchup.home_lineup],
                    "away_team": matchup.away_team.team_name if matchup.away_team else "BYE",
                    "away_score": matchup.away_score if matchup.away_team else 0,
                    "away_projected": matchup.away_projected if matchup.away_team else 0,
                    "away_lineup": [serialize_box_player(player) for player in matchup.away_lineup],
                    "winner": "HOME" if matchup.home_score > matchup.away_score else "AWAY" if matchup.away_score > matchup.home_score else "TIE"
                })
            
            return str(matchup_info)
        except Exception as e:
            log_error(f"Error retrieving matchup information: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            if "401" in str(e) or "Private" in str(e):
                return ("This appears to be a private league. Set ESPN_S2 and SWID in the server environment "
                      "or use the authenticate tool with those cookies.")
            return f"Error retrieving matchup information: {str(e)}"

    @mcp.tool()
    async def logout() -> str:
        """Clear a temporary authentication override for this session.

        Environment credentials remain available until the server is restarted
        without ESPN_S2 and SWID.
        """
        try:
            log_error("Logging out...")
            # Clear credentials for this session
            api.clear_credentials(SESSION_ID)
            
            if api.environment_credentials_configured():
                return ("The session override has been cleared. Environment credentials remain active; "
                        "remove them from the server environment and restart to disable private-league access.")
            return "The session authentication override has been cleared."
        except Exception as e:
            log_error(f"Error logging out: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            return f"Error logging out: {str(e)}"

    if __name__ == "__main__":
        # Run the server
        log_error("Starting MCP server...")
        mcp.run()
except Exception as e:
    # Log any exception that might occur during server initialization
    log_error(f"ERROR DURING SERVER INITIALIZATION: {str(e)}")
    traceback.print_exc(file=sys.stderr)
    # Keep the process running to see logs
    log_error("Server failed to start, but kept running for logging. Press Ctrl+C to exit.")
    # Wait indefinitely to keep the process alive for logs
    import time
    while True:
        time.sleep(10)
