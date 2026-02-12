from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Auth ---
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str
    password: str = Field(min_length=6)
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    balance: float


# --- Skiers ---
class SkierOut(BaseModel):
    id: int
    name: str
    country: str
    age: int
    specialty: str
    skill_rating: float
    photo_url: Optional[str] = None
    bio: Optional[str] = None

    class Config:
        from_attributes = True


class SkierOdds(BaseModel):
    skier: SkierOut
    win_odds: float
    podium_odds: float


# --- Races ---
class RaceOut(BaseModel):
    id: int
    name: str
    race_type: str
    technique: str
    location: str
    distance_km: float
    start_time: datetime
    status: str
    num_checkpoints: int
    entry_count: int = 0

    class Config:
        from_attributes = True


class RaceEntryOut(BaseModel):
    id: int
    skier: SkierOut
    bib_number: int
    final_position: Optional[int] = None
    final_time_seconds: Optional[float] = None
    dnf: bool = False
    points_earned: float = 0.0

    class Config:
        from_attributes = True


class CheckpointOut(BaseModel):
    id: int
    skier_id: int
    skier_name: str
    skier_country: str
    checkpoint_number: int
    checkpoint_name: str
    distance_km: float
    time_seconds: float
    position: int
    speed_kmh: Optional[float] = None
    gap_to_leader: float = 0.0
    timestamp: datetime

    class Config:
        from_attributes = True


# --- Fantasy Teams ---
class CreateTeamRequest(BaseModel):
    race_id: int
    name: str = Field(min_length=1, max_length=200)
    skier_ids: list[int] = Field(min_length=1, max_length=6)
    captain_id: int


class TeamMemberOut(BaseModel):
    id: int
    skier: SkierOut
    is_captain: bool
    points_earned: float = 0.0

    class Config:
        from_attributes = True


class FantasyTeamOut(BaseModel):
    id: int
    user_id: int
    race_id: int
    name: str
    total_points: float
    members: list[TeamMemberOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


# --- Bets ---
class PlaceBetRequest(BaseModel):
    race_id: int
    bet_type: str  # winner, podium, head_to_head
    skier_id: int
    amount: float = Field(gt=0)


class BetOut(BaseModel):
    id: int
    race_id: int
    bet_type: str
    skier_id: int
    skier_name: str = ""
    amount: float
    odds: float
    status: str
    payout: float
    created_at: datetime

    class Config:
        from_attributes = True


# --- Dashboard ---
class SkierDashboardEntry(BaseModel):
    skier_id: int
    skier_name: str
    country: str
    bib_number: int
    is_on_team: bool = False
    is_captain: bool = False
    current_position: int
    current_checkpoint: int
    total_checkpoints: int
    last_time_seconds: float
    gap_to_leader: float
    speed_kmh: Optional[float] = None
    fantasy_points: float = 0.0


class RaceDashboard(BaseModel):
    race: RaceOut
    standings: list[SkierDashboardEntry]
    team: Optional[FantasyTeamOut] = None
    team_total_points: float = 0.0


# --- Leaderboard ---
class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    display_name: Optional[str] = None
    total_points: float
    team_count: int


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    balance: float
    total_points: float
    team_count: int = 0
    bet_count: int = 0

    class Config:
        from_attributes = True
