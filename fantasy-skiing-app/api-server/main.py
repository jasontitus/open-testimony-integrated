import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import hash_password, verify_password, create_token, get_current_user
from config import settings
from database import get_db, init_db
from models import (
    Skier, Race, RaceEntry, Checkpoint, User,
    FantasyTeam, TeamMember, Bet, BetType, BetStatus, RaceStatus,
)
from race_simulation import calculate_odds, simulate_checkpoint, run_race_simulation
from schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    SkierOut, SkierOdds, RaceOut, RaceEntryOut, CheckpointOut,
    CreateTeamRequest, FantasyTeamOut, TeamMemberOut,
    PlaceBetRequest, BetOut,
    SkierDashboardEntry, RaceDashboard,
    LeaderboardEntry, UserProfile,
)
from seed_data import seed_database


# --- WebSocket manager for live updates ---
class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = {}  # race_id -> connections

    async def connect(self, websocket: WebSocket, race_id: int):
        await websocket.accept()
        if race_id not in self.connections:
            self.connections[race_id] = []
        self.connections[race_id].append(websocket)

    def disconnect(self, websocket: WebSocket, race_id: int):
        if race_id in self.connections:
            self.connections[race_id] = [
                ws for ws in self.connections[race_id] if ws != websocket
            ]

    async def broadcast(self, race_id: int, data: dict):
        if race_id not in self.connections:
            return
        dead = []
        for ws in self.connections[race_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, race_id)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with get_db_session() as db:
        await seed_database(db)
    yield


async def get_db_session():
    from database import async_session
    return async_session()


app = FastAPI(
    title="Fantasy XC Skiing",
    description="Fantasy sports platform for cross-country skiing",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================
# AUTH ENDPOINTS
# =====================

@app.post("/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already taken")

    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name or req.username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(user.id, user.username)
    return TokenResponse(
        access_token=token, user_id=user.id,
        username=user.username, balance=user.balance,
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user.id, user.username)
    return TokenResponse(
        access_token=token, user_id=user.id,
        username=user.username, balance=user.balance,
    )


@app.get("/auth/me", response_model=UserProfile)
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    team_count = (await db.execute(
        select(func.count(FantasyTeam.id)).where(FantasyTeam.user_id == user.id)
    )).scalar()
    bet_count = (await db.execute(
        select(func.count(Bet.id)).where(Bet.user_id == user.id)
    )).scalar()
    return UserProfile(
        id=user.id, username=user.username, email=user.email,
        display_name=user.display_name, balance=user.balance,
        total_points=user.total_points, team_count=team_count, bet_count=bet_count,
    )


# =====================
# SKIER ENDPOINTS
# =====================

@app.get("/skiers", response_model=list[SkierOut])
async def list_skiers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skier).order_by(desc(Skier.skill_rating)))
    return result.scalars().all()


@app.get("/skiers/{skier_id}", response_model=SkierOut)
async def get_skier(skier_id: int, db: AsyncSession = Depends(get_db)):
    skier = await db.get(Skier, skier_id)
    if not skier:
        raise HTTPException(status_code=404, detail="Skier not found")
    return skier


# =====================
# RACE ENDPOINTS
# =====================

@app.get("/races", response_model=list[RaceOut])
async def list_races(status: str = None, db: AsyncSession = Depends(get_db)):
    query = select(Race).order_by(Race.start_time)
    if status:
        query = query.where(Race.status == status)
    result = await db.execute(query)
    races = result.scalars().all()

    out = []
    for race in races:
        count = (await db.execute(
            select(func.count(RaceEntry.id)).where(RaceEntry.race_id == race.id)
        )).scalar()
        race_dict = RaceOut(
            id=race.id, name=race.name, race_type=race.race_type,
            technique=race.technique, location=race.location,
            distance_km=race.distance_km, start_time=race.start_time,
            status=race.status.value, num_checkpoints=race.num_checkpoints,
            entry_count=count,
        )
        out.append(race_dict)
    return out


@app.get("/races/{race_id}", response_model=RaceOut)
async def get_race(race_id: int, db: AsyncSession = Depends(get_db)):
    race = await db.get(Race, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    count = (await db.execute(
        select(func.count(RaceEntry.id)).where(RaceEntry.race_id == race.id)
    )).scalar()
    return RaceOut(
        id=race.id, name=race.name, race_type=race.race_type,
        technique=race.technique, location=race.location,
        distance_km=race.distance_km, start_time=race.start_time,
        status=race.status.value, num_checkpoints=race.num_checkpoints,
        entry_count=count,
    )


@app.get("/races/{race_id}/entries", response_model=list[RaceEntryOut])
async def get_race_entries(race_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RaceEntry)
        .options(selectinload(RaceEntry.skier))
        .where(RaceEntry.race_id == race_id)
        .order_by(RaceEntry.bib_number)
    )
    entries = result.scalars().all()
    return [
        RaceEntryOut(
            id=e.id,
            skier=SkierOut.model_validate(e.skier),
            bib_number=e.bib_number,
            final_position=e.final_position,
            final_time_seconds=e.final_time_seconds,
            dnf=e.dnf,
            points_earned=e.points_earned,
        )
        for e in entries
    ]


@app.get("/races/{race_id}/odds", response_model=list[SkierOdds])
async def get_race_odds(race_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RaceEntry, Skier)
        .join(Skier, RaceEntry.skier_id == Skier.id)
        .where(RaceEntry.race_id == race_id)
        .order_by(desc(Skier.skill_rating))
    )
    entries = result.all()
    num_entrants = len(entries)
    return [
        SkierOdds(
            skier=SkierOut.model_validate(skier),
            win_odds=calculate_odds(skier.skill_rating, num_entrants)[0],
            podium_odds=calculate_odds(skier.skill_rating, num_entrants)[1],
        )
        for entry, skier in entries
    ]


@app.get("/races/{race_id}/checkpoints", response_model=list[CheckpointOut])
async def get_race_checkpoints(
    race_id: int, checkpoint_number: int = None, db: AsyncSession = Depends(get_db)
):
    query = (
        select(Checkpoint, Skier)
        .join(Skier, Checkpoint.skier_id == Skier.id)
        .where(Checkpoint.race_id == race_id)
    )
    if checkpoint_number:
        query = query.where(Checkpoint.checkpoint_number == checkpoint_number)
    query = query.order_by(Checkpoint.checkpoint_number, Checkpoint.position)

    result = await db.execute(query)
    rows = result.all()
    return [
        CheckpointOut(
            id=cp.id, skier_id=cp.skier_id, skier_name=skier.name,
            skier_country=skier.country,
            checkpoint_number=cp.checkpoint_number, checkpoint_name=cp.checkpoint_name,
            distance_km=cp.distance_km, time_seconds=cp.time_seconds,
            position=cp.position, speed_kmh=cp.speed_kmh,
            gap_to_leader=cp.gap_to_leader, timestamp=cp.timestamp,
        )
        for cp, skier in rows
    ]


# =====================
# LIVE DASHBOARD
# =====================

@app.get("/races/{race_id}/dashboard", response_model=RaceDashboard)
async def get_race_dashboard(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    race = await db.get(Race, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    entry_count = (await db.execute(
        select(func.count(RaceEntry.id)).where(RaceEntry.race_id == race.id)
    )).scalar()
    race_out = RaceOut(
        id=race.id, name=race.name, race_type=race.race_type,
        technique=race.technique, location=race.location,
        distance_km=race.distance_km, start_time=race.start_time,
        status=race.status.value, num_checkpoints=race.num_checkpoints,
        entry_count=entry_count,
    )

    # Get user's team for this race
    team_result = await db.execute(
        select(FantasyTeam)
        .options(selectinload(FantasyTeam.members).selectinload(TeamMember.skier))
        .where(FantasyTeam.user_id == user.id)
        .where(FantasyTeam.race_id == race_id)
    )
    team = team_result.scalar_one_or_none()
    team_skier_ids = set()
    captain_id = None
    team_out = None

    if team:
        team_skier_ids = {m.skier_id for m in team.members}
        captain_member = next((m for m in team.members if m.is_captain), None)
        captain_id = captain_member.skier_id if captain_member else None
        team_out = FantasyTeamOut(
            id=team.id, user_id=team.user_id, race_id=team.race_id,
            name=team.name, total_points=team.total_points,
            created_at=team.created_at,
            members=[
                TeamMemberOut(
                    id=m.id,
                    skier=SkierOut.model_validate(m.skier),
                    is_captain=m.is_captain,
                    points_earned=m.points_earned,
                )
                for m in team.members
            ],
        )

    # Build standings from latest checkpoints
    # Get latest checkpoint number
    max_cp = (await db.execute(
        select(func.max(Checkpoint.checkpoint_number))
        .where(Checkpoint.race_id == race_id)
    )).scalar() or 0

    standings = []
    if max_cp > 0:
        cp_result = await db.execute(
            select(Checkpoint, Skier, RaceEntry)
            .join(Skier, Checkpoint.skier_id == Skier.id)
            .join(RaceEntry, (RaceEntry.skier_id == Skier.id) & (RaceEntry.race_id == race_id))
            .where(Checkpoint.race_id == race_id)
            .where(Checkpoint.checkpoint_number == max_cp)
            .order_by(Checkpoint.position)
        )
        for cp, skier, entry in cp_result.all():
            # Calculate fantasy points based on current position
            from race_simulation import POSITION_POINTS
            current_pts = POSITION_POINTS.get(cp.position, 10)
            if skier.id == captain_id:
                current_pts *= 2

            standings.append(SkierDashboardEntry(
                skier_id=skier.id,
                skier_name=skier.name,
                country=skier.country,
                bib_number=entry.bib_number,
                is_on_team=skier.id in team_skier_ids,
                is_captain=skier.id == captain_id,
                current_position=cp.position,
                current_checkpoint=max_cp,
                total_checkpoints=race.num_checkpoints,
                last_time_seconds=cp.time_seconds,
                gap_to_leader=cp.gap_to_leader,
                speed_kmh=cp.speed_kmh,
                fantasy_points=current_pts if skier.id in team_skier_ids else 0,
            ))
    else:
        # No checkpoints yet, show starting list
        entries_result = await db.execute(
            select(RaceEntry, Skier)
            .join(Skier, RaceEntry.skier_id == Skier.id)
            .where(RaceEntry.race_id == race_id)
            .order_by(RaceEntry.bib_number)
        )
        for entry, skier in entries_result.all():
            standings.append(SkierDashboardEntry(
                skier_id=skier.id,
                skier_name=skier.name,
                country=skier.country,
                bib_number=entry.bib_number,
                is_on_team=skier.id in team_skier_ids,
                is_captain=skier.id == captain_id,
                current_position=entry.bib_number,
                current_checkpoint=0,
                total_checkpoints=race.num_checkpoints,
                last_time_seconds=0,
                gap_to_leader=0,
                speed_kmh=None,
                fantasy_points=0,
            ))

    return RaceDashboard(
        race=race_out,
        standings=standings,
        team=team_out,
        team_total_points=team.total_points if team else 0,
    )


# =====================
# FANTASY TEAM ENDPOINTS
# =====================

@app.post("/teams", response_model=FantasyTeamOut)
async def create_team(
    req: CreateTeamRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify race exists and is upcoming
    race = await db.get(Race, req.race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    if race.status == RaceStatus.FINISHED:
        raise HTTPException(status_code=400, detail="Cannot create team for finished race")

    # Check no existing team
    existing = await db.execute(
        select(FantasyTeam)
        .where(FantasyTeam.user_id == user.id)
        .where(FantasyTeam.race_id == req.race_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a team for this race")

    # Verify skiers are in this race
    entries = await db.execute(
        select(RaceEntry.skier_id)
        .where(RaceEntry.race_id == req.race_id)
        .where(RaceEntry.skier_id.in_(req.skier_ids))
    )
    valid_ids = {row[0] for row in entries.all()}
    invalid = set(req.skier_ids) - valid_ids
    if invalid:
        raise HTTPException(status_code=400, detail=f"Skiers not in race: {invalid}")

    if req.captain_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Captain must be on your team")

    # Create team
    team = FantasyTeam(user_id=user.id, race_id=req.race_id, name=req.name)
    db.add(team)
    await db.flush()

    for sid in req.skier_ids:
        member = TeamMember(
            team_id=team.id, skier_id=sid,
            is_captain=(sid == req.captain_id),
        )
        db.add(member)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(FantasyTeam)
        .options(selectinload(FantasyTeam.members).selectinload(TeamMember.skier))
        .where(FantasyTeam.id == team.id)
    )
    team = result.scalar_one()
    return FantasyTeamOut(
        id=team.id, user_id=team.user_id, race_id=team.race_id,
        name=team.name, total_points=team.total_points,
        created_at=team.created_at,
        members=[
            TeamMemberOut(
                id=m.id,
                skier=SkierOut.model_validate(m.skier),
                is_captain=m.is_captain,
                points_earned=m.points_earned,
            )
            for m in team.members
        ],
    )


@app.get("/teams", response_model=list[FantasyTeamOut])
async def list_my_teams(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FantasyTeam)
        .options(selectinload(FantasyTeam.members).selectinload(TeamMember.skier))
        .where(FantasyTeam.user_id == user.id)
        .order_by(desc(FantasyTeam.created_at))
    )
    teams = result.scalars().all()
    return [
        FantasyTeamOut(
            id=t.id, user_id=t.user_id, race_id=t.race_id,
            name=t.name, total_points=t.total_points,
            created_at=t.created_at,
            members=[
                TeamMemberOut(
                    id=m.id,
                    skier=SkierOut.model_validate(m.skier),
                    is_captain=m.is_captain,
                    points_earned=m.points_earned,
                )
                for m in t.members
            ],
        )
        for t in teams
    ]


# =====================
# BETTING ENDPOINTS
# =====================

@app.post("/bets", response_model=BetOut)
async def place_bet(
    req: PlaceBetRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    race = await db.get(Race, req.race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    if race.status == RaceStatus.FINISHED:
        raise HTTPException(status_code=400, detail="Race already finished")

    if req.amount > user.balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Verify skier in race
    entry = await db.execute(
        select(RaceEntry, Skier)
        .join(Skier, RaceEntry.skier_id == Skier.id)
        .where(RaceEntry.race_id == req.race_id)
        .where(RaceEntry.skier_id == req.skier_id)
    )
    row = entry.first()
    if not row:
        raise HTTPException(status_code=400, detail="Skier not in this race")
    _, skier = row

    # Calculate odds
    entry_count = (await db.execute(
        select(func.count(RaceEntry.id)).where(RaceEntry.race_id == req.race_id)
    )).scalar()
    win_odds, podium_odds = calculate_odds(skier.skill_rating, entry_count)

    bet_type = BetType(req.bet_type)
    odds = win_odds if bet_type == BetType.WINNER else podium_odds

    # Deduct balance
    user.balance -= req.amount

    bet = Bet(
        user_id=user.id, race_id=req.race_id,
        bet_type=bet_type, skier_id=req.skier_id,
        amount=req.amount, odds=odds,
    )
    db.add(bet)
    await db.commit()
    await db.refresh(bet)

    return BetOut(
        id=bet.id, race_id=bet.race_id, bet_type=bet.bet_type.value,
        skier_id=bet.skier_id, skier_name=skier.name,
        amount=bet.amount, odds=bet.odds,
        status=bet.status.value, payout=bet.payout,
        created_at=bet.created_at,
    )


@app.get("/bets", response_model=list[BetOut])
async def list_my_bets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Bet, Skier)
        .join(Skier, Bet.skier_id == Skier.id)
        .where(Bet.user_id == user.id)
        .order_by(desc(Bet.created_at))
    )
    return [
        BetOut(
            id=b.id, race_id=b.race_id, bet_type=b.bet_type.value,
            skier_id=b.skier_id, skier_name=s.name,
            amount=b.amount, odds=b.odds,
            status=b.status.value, payout=b.payout,
            created_at=b.created_at,
        )
        for b, s in result.all()
    ]


# =====================
# LEADERBOARD
# =====================

@app.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            User.id, User.username, User.display_name, User.total_points,
            func.count(FantasyTeam.id).label("team_count"),
        )
        .outerjoin(FantasyTeam, FantasyTeam.user_id == User.id)
        .group_by(User.id)
        .order_by(desc(User.total_points))
        .limit(50)
    )
    rows = result.all()
    return [
        LeaderboardEntry(
            rank=i + 1, user_id=row[0], username=row[1],
            display_name=row[2], total_points=row[3], team_count=row[4],
        )
        for i, row in enumerate(rows)
    ]


# =====================
# RACE SIMULATION (ADMIN)
# =====================

@app.post("/admin/simulate/{race_id}")
async def trigger_simulation(race_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger a single checkpoint simulation for testing."""
    race = await db.get(Race, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    if race.status == RaceStatus.UPCOMING:
        race.status = RaceStatus.LIVE
        await db.commit()

    result = await simulate_checkpoint(race_id)
    if result is None:
        return {"message": "Race simulation complete or race not live", "checkpoint": None}

    # Broadcast update via WebSocket
    await manager.broadcast(race_id, {
        "type": "checkpoint_update",
        "race_id": race_id,
        "checkpoint_number": result,
    })

    return {"message": f"Checkpoint {result} simulated", "checkpoint": result}


@app.post("/admin/simulate/{race_id}/full")
async def trigger_full_simulation(race_id: int):
    """Start full race simulation in background."""
    asyncio.create_task(run_race_simulation(race_id, interval_seconds=5.0))
    return {"message": "Full simulation started"}


# =====================
# WEBSOCKET FOR LIVE UPDATES
# =====================

@app.websocket("/ws/race/{race_id}")
async def websocket_race(websocket: WebSocket, race_id: int):
    await manager.connect(websocket, race_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, race_id)


# =====================
# HEALTH CHECK
# =====================

@app.get("/health")
async def health():
    return {"status": "ok", "service": "fantasy-xc-skiing", "timestamp": datetime.utcnow().isoformat()}
