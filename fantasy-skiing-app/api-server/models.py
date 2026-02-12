import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey,
    Enum as SAEnum, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship

from database import Base


class RaceStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    LIVE = "live"
    FINISHED = "finished"


class BetStatus(str, enum.Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    CANCELLED = "cancelled"


class BetType(str, enum.Enum):
    WINNER = "winner"
    PODIUM = "podium"
    HEAD_TO_HEAD = "head_to_head"


class Skier(Base):
    __tablename__ = "skiers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    country = Column(String(3), nullable=False)  # ISO 3166-1 alpha-3
    age = Column(Integer, nullable=False)
    specialty = Column(String(50), nullable=False)  # sprint, distance, all-around
    skill_rating = Column(Float, default=50.0)
    photo_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    race_entries = relationship("RaceEntry", back_populates="skier")
    checkpoints = relationship("Checkpoint", back_populates="skier")


class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    race_type = Column(String(50), nullable=False)  # sprint, 10km, 15km, 30km, 50km, relay
    technique = Column(String(20), nullable=False)  # classic, freestyle
    location = Column(String(200), nullable=False)
    distance_km = Column(Float, nullable=False)
    start_time = Column(DateTime, nullable=False)
    status = Column(SAEnum(RaceStatus), default=RaceStatus.UPCOMING)
    num_checkpoints = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)

    entries = relationship("RaceEntry", back_populates="race")
    checkpoints = relationship("Checkpoint", back_populates="race")


class RaceEntry(Base):
    __tablename__ = "race_entries"

    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    skier_id = Column(Integer, ForeignKey("skiers.id"), nullable=False)
    bib_number = Column(Integer, nullable=False)
    final_position = Column(Integer, nullable=True)
    final_time_seconds = Column(Float, nullable=True)
    dnf = Column(Boolean, default=False)
    points_earned = Column(Float, default=0.0)

    race = relationship("Race", back_populates="entries")
    skier = relationship("Skier", back_populates="race_entries")

    __table_args__ = (
        UniqueConstraint("race_id", "skier_id", name="uq_race_skier"),
    )


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    skier_id = Column(Integer, ForeignKey("skiers.id"), nullable=False)
    checkpoint_number = Column(Integer, nullable=False)
    checkpoint_name = Column(String(100), nullable=False)
    distance_km = Column(Float, nullable=False)
    time_seconds = Column(Float, nullable=False)
    position = Column(Integer, nullable=False)
    speed_kmh = Column(Float, nullable=True)
    gap_to_leader = Column(Float, default=0.0)  # seconds behind leader
    timestamp = Column(DateTime, default=datetime.utcnow)

    race = relationship("Race", back_populates="checkpoints")
    skier = relationship("Skier", back_populates="checkpoints")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    display_name = Column(String(200), nullable=True)
    balance = Column(Float, default=10000.0)  # Starting virtual currency
    total_points = Column(Float, default=0.0)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    teams = relationship("FantasyTeam", back_populates="user")
    bets = relationship("Bet", back_populates="user")


class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    name = Column(String(200), nullable=False)
    total_points = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="teams")
    race = relationship("Race")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "race_id", name="uq_user_race_team"),
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False)
    skier_id = Column(Integer, ForeignKey("skiers.id"), nullable=False)
    is_captain = Column(Boolean, default=False)
    points_earned = Column(Float, default=0.0)

    team = relationship("FantasyTeam", back_populates="members")
    skier = relationship("Skier")

    __table_args__ = (
        UniqueConstraint("team_id", "skier_id", name="uq_team_skier"),
    )


class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    bet_type = Column(SAEnum(BetType), nullable=False)
    skier_id = Column(Integer, ForeignKey("skiers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    odds = Column(Float, nullable=False)
    status = Column(SAEnum(BetStatus), default=BetStatus.PENDING)
    payout = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bets")
    race = relationship("Race")
    skier = relationship("Skier")
