"""Simulates live race progress by generating checkpoint data."""
import asyncio
import random
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Race, RaceEntry, RaceStatus, Checkpoint, Skier, FantasyTeam, TeamMember, Bet, BetStatus, BetType

# Points awarded by finish position
POSITION_POINTS = {
    1: 100, 2: 80, 3: 65, 4: 55, 5: 50,
    6: 45, 7: 40, 8: 36, 9: 32, 10: 29,
    11: 26, 12: 24, 13: 22, 14: 20, 15: 18,
    16: 16, 17: 15, 18: 14, 19: 13, 20: 12,
}


def calculate_odds(skier_rating: float, num_entrants: int) -> tuple[float, float]:
    """Calculate betting odds based on skill rating."""
    # Higher rating = lower (better) odds
    base = max(1.1, (100 - skier_rating) / 10)
    win_odds = round(base + random.uniform(-0.3, 0.3), 2)
    podium_odds = round(max(1.05, win_odds * 0.4), 2)
    return max(1.1, win_odds), max(1.05, podium_odds)


async def simulate_checkpoint(race_id: int):
    """Generate the next checkpoint for all skiers in a live race."""
    async with async_session() as db:
        race = await db.get(Race, race_id)
        if not race or race.status != RaceStatus.LIVE:
            return None

        # Get current checkpoint progress
        result = await db.execute(
            select(func.max(Checkpoint.checkpoint_number))
            .where(Checkpoint.race_id == race_id)
        )
        current_max = result.scalar() or 0
        next_cp = current_max + 1

        if next_cp > race.num_checkpoints:
            return None  # Race already fully simulated

        # Get all entries with skier info
        result = await db.execute(
            select(RaceEntry, Skier)
            .join(Skier, RaceEntry.skier_id == Skier.id)
            .where(RaceEntry.race_id == race_id)
            .where(RaceEntry.dnf == False)
        )
        entries = result.all()

        if not entries:
            return None

        cp_distance = (race.distance_km / race.num_checkpoints) * next_cp
        cp_name = f"CP{next_cp} ({cp_distance:.1f}km)"

        # Simulate times based on skill + randomness
        times = []
        for entry, skier in entries:
            # Base pace: higher skill = faster
            base_pace = 200 - skier.skill_rating  # seconds per km base
            # Add race-type modifier
            if race.race_type == "sprint":
                base_pace *= 0.6
            # Randomness factor (fatigue, conditions, etc.)
            variance = random.gauss(0, 3 + (next_cp * 0.5))
            time_sec = cp_distance * base_pace + variance
            # Small chance of DNF in later checkpoints
            is_dnf = random.random() < 0.01 * next_cp
            times.append((entry, skier, max(time_sec, cp_distance * 50), is_dnf))

        # Sort by time for positioning
        times.sort(key=lambda x: (x[3], x[2]))  # DNF last, then by time
        leader_time = times[0][2] if not times[0][3] else 0

        checkpoints = []
        for position, (entry, skier, time_sec, is_dnf) in enumerate(times, 1):
            if is_dnf:
                entry.dnf = True
                continue

            speed = (cp_distance / time_sec) * 3600 if time_sec > 0 else 0
            gap = time_sec - leader_time

            cp = Checkpoint(
                race_id=race_id,
                skier_id=skier.id,
                checkpoint_number=next_cp,
                checkpoint_name=cp_name,
                distance_km=cp_distance,
                time_seconds=round(time_sec, 2),
                position=position,
                speed_kmh=round(speed, 1),
                gap_to_leader=round(gap, 2),
                timestamp=datetime.utcnow(),
            )
            db.add(cp)
            checkpoints.append(cp)

        # If this is the final checkpoint, finish the race
        if next_cp >= race.num_checkpoints:
            race.status = RaceStatus.FINISHED
            for position, (entry, skier, time_sec, is_dnf) in enumerate(times, 1):
                if not is_dnf:
                    entry.final_position = position
                    entry.final_time_seconds = round(time_sec, 2)
                    entry.points_earned = POSITION_POINTS.get(position, 10)

            # Score fantasy teams
            await _score_fantasy_teams(db, race_id)
            # Settle bets
            await _settle_bets(db, race_id)

        await db.commit()
        return next_cp


async def _score_fantasy_teams(db: AsyncSession, race_id: int):
    """Calculate points for all fantasy teams in this race."""
    result = await db.execute(
        select(FantasyTeam).where(FantasyTeam.race_id == race_id)
    )
    teams = result.scalars().all()

    for team in teams:
        result = await db.execute(
            select(TeamMember, RaceEntry)
            .join(RaceEntry, (TeamMember.skier_id == RaceEntry.skier_id) & (RaceEntry.race_id == race_id))
            .where(TeamMember.team_id == team.id)
        )
        members_entries = result.all()

        team_total = 0.0
        for member, entry in members_entries:
            points = entry.points_earned
            if member.is_captain:
                points *= 2  # Captain gets double points
            member.points_earned = points
            team_total += points

        team.total_points = team_total

        # Update user total points
        user = await db.get(team.user.__class__, team.user_id)
        if user:
            user.total_points += team_total


async def _settle_bets(db: AsyncSession, race_id: int):
    """Settle all bets for a finished race."""
    # Get final results
    result = await db.execute(
        select(RaceEntry)
        .where(RaceEntry.race_id == race_id)
        .where(RaceEntry.final_position != None)
        .order_by(RaceEntry.final_position)
    )
    entries = result.scalars().all()
    if not entries:
        return

    winner_id = entries[0].skier_id
    podium_ids = {e.skier_id for e in entries[:3]}

    # Get pending bets
    result = await db.execute(
        select(Bet)
        .where(Bet.race_id == race_id)
        .where(Bet.status == BetStatus.PENDING)
    )
    bets = result.scalars().all()

    for bet in bets:
        won = False
        if bet.bet_type == BetType.WINNER and bet.skier_id == winner_id:
            won = True
        elif bet.bet_type == BetType.PODIUM and bet.skier_id in podium_ids:
            won = True

        if won:
            bet.status = BetStatus.WON
            bet.payout = bet.amount * bet.odds
            user = await db.get(bet.user.__class__, bet.user_id)
            if user:
                user.balance += bet.payout
        else:
            bet.status = BetStatus.LOST
            bet.payout = 0.0


async def run_race_simulation(race_id: int, interval_seconds: float = 8.0):
    """Run full race simulation with periodic checkpoint updates."""
    async with async_session() as db:
        race = await db.get(Race, race_id)
        if not race:
            return
        if race.status == RaceStatus.UPCOMING:
            race.status = RaceStatus.LIVE
            await db.commit()

    for _ in range(50):  # Safety limit
        result = await simulate_checkpoint(race_id)
        if result is None:
            break
        await asyncio.sleep(interval_seconds)
