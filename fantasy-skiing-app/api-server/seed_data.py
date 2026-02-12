"""Seed the database with skiers and upcoming races."""
import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Skier, Race, RaceEntry, RaceStatus

SKIER_DATA = [
    {"name": "Johannes Klaebo", "country": "NOR", "age": 28, "specialty": "sprint", "skill_rating": 95.0, "bio": "Norwegian sprint sensation and multiple Olympic gold medalist."},
    {"name": "Alexander Bolshunov", "country": "RUS", "age": 27, "specialty": "distance", "skill_rating": 93.0, "bio": "Dominant distance skier with incredible endurance."},
    {"name": "Federico Pellegrino", "country": "ITA", "age": 34, "specialty": "sprint", "skill_rating": 88.0, "bio": "Italian sprint specialist known for tactical racing."},
    {"name": "Simen Hegstad Krueger", "country": "NOR", "age": 31, "specialty": "distance", "skill_rating": 87.0, "bio": "Norwegian distance racer with Olympic pedigree."},
    {"name": "Paal Golberg", "country": "NOR", "age": 34, "specialty": "all-around", "skill_rating": 86.0, "bio": "Versatile Norwegian skier competing across all distances."},
    {"name": "Hugo Lapalus", "country": "FRA", "age": 27, "specialty": "distance", "skill_rating": 83.0, "bio": "Rising French talent in distance events."},
    {"name": "Iivo Niskanen", "country": "FIN", "age": 32, "specialty": "distance", "skill_rating": 89.0, "bio": "Finnish classic specialist and Olympic champion."},
    {"name": "Erik Valnes", "country": "NOR", "age": 28, "specialty": "sprint", "skill_rating": 85.0, "bio": "Explosive Norwegian sprinter."},
    {"name": "Richard Jouve", "country": "FRA", "age": 30, "specialty": "sprint", "skill_rating": 84.0, "bio": "French sprint contender with World Cup podiums."},
    {"name": "Sergey Ustiugov", "country": "RUS", "age": 32, "specialty": "all-around", "skill_rating": 86.0, "bio": "Russian all-rounder and Tour de Ski winner."},
    {"name": "Lucas Chanavat", "country": "FRA", "age": 29, "specialty": "sprint", "skill_rating": 82.0, "bio": "French sprinter with blistering speed."},
    {"name": "Martin Loewstroem Nyenget", "country": "NOR", "age": 32, "specialty": "distance", "skill_rating": 85.0, "bio": "Consistent Norwegian distance performer."},
    {"name": "Didrik Toenseth", "country": "NOR", "age": 33, "specialty": "distance", "skill_rating": 81.0, "bio": "Norwegian relay specialist and team player."},
    {"name": "Andrew Musgrave", "country": "GBR", "age": 33, "specialty": "distance", "skill_rating": 79.0, "bio": "British cross-country skiing pioneer."},
    {"name": "Dario Cologna", "country": "SUI", "age": 38, "specialty": "distance", "skill_rating": 82.0, "bio": "Swiss legend and four-time Olympic gold medalist."},
    {"name": "Sjur Roethe", "country": "NOR", "age": 36, "specialty": "distance", "skill_rating": 83.0, "bio": "Experienced Norwegian distance veteran."},
    {"name": "Calle Halfvarsson", "country": "SWE", "age": 35, "specialty": "all-around", "skill_rating": 80.0, "bio": "Swedish all-rounder known for fiery temperament."},
    {"name": "Ristomatti Hakola", "country": "FIN", "age": 32, "specialty": "sprint", "skill_rating": 81.0, "bio": "Finnish sprint specialist."},
    {"name": "Artem Maltsev", "country": "RUS", "age": 28, "specialty": "distance", "skill_rating": 80.0, "bio": "Young Russian distance talent."},
    {"name": "Janosch Brugger", "country": "GER", "age": 29, "specialty": "sprint", "skill_rating": 78.0, "bio": "German sprint hope."},
    {"name": "Jessie Diggins", "country": "USA", "age": 33, "specialty": "all-around", "skill_rating": 92.0, "bio": "American star and Olympic gold medalist."},
    {"name": "Therese Johaug", "country": "NOR", "age": 36, "specialty": "distance", "skill_rating": 94.0, "bio": "Norwegian legend and multiple world champion."},
    {"name": "Frida Karlsson", "country": "SWE", "age": 25, "specialty": "distance", "skill_rating": 90.0, "bio": "Swedish distance prodigy."},
    {"name": "Ebba Andersson", "country": "SWE", "age": 27, "specialty": "distance", "skill_rating": 88.0, "bio": "Swedish distance powerhouse."},
    {"name": "Rosie Brennan", "country": "USA", "age": 35, "specialty": "all-around", "skill_rating": 83.0, "bio": "Versatile American racer."},
    {"name": "Natalia Nepryaeva", "country": "RUS", "age": 29, "specialty": "all-around", "skill_rating": 89.0, "bio": "Russian overall World Cup leader."},
    {"name": "Linn Svahn", "country": "SWE", "age": 25, "specialty": "sprint", "skill_rating": 87.0, "bio": "Swedish sprint queen."},
    {"name": "Maja Dahlqvist", "country": "SWE", "age": 30, "specialty": "sprint", "skill_rating": 86.0, "bio": "Swedish sprint specialist and team relay anchor."},
    {"name": "Heidi Weng", "country": "NOR", "age": 33, "specialty": "distance", "skill_rating": 84.0, "bio": "Norwegian distance veteran."},
    {"name": "Krista Parmakoski", "country": "FIN", "age": 34, "specialty": "distance", "skill_rating": 82.0, "bio": "Finnish distance stalwart."},
]

RACE_TEMPLATES = [
    {"name": "World Cup Sprint Drammen", "race_type": "sprint", "technique": "classic", "location": "Drammen, Norway", "distance_km": 1.5, "num_checkpoints": 3},
    {"name": "World Cup 10km Ruka", "race_type": "10km", "technique": "freestyle", "location": "Ruka, Finland", "distance_km": 10.0, "num_checkpoints": 5},
    {"name": "World Cup 15km Davos", "race_type": "15km", "technique": "classic", "location": "Davos, Switzerland", "distance_km": 15.0, "num_checkpoints": 6},
    {"name": "Tour de Ski Stage 1", "race_type": "10km", "technique": "freestyle", "location": "Val di Fiemme, Italy", "distance_km": 10.0, "num_checkpoints": 5},
    {"name": "World Cup 30km Holmenkollen", "race_type": "30km", "technique": "classic", "location": "Oslo, Norway", "distance_km": 30.0, "num_checkpoints": 8},
    {"name": "World Cup Sprint Lahti", "race_type": "sprint", "technique": "freestyle", "location": "Lahti, Finland", "distance_km": 1.8, "num_checkpoints": 3},
    {"name": "World Cup 50km Vasaloppet", "race_type": "50km", "technique": "classic", "location": "Mora, Sweden", "distance_km": 50.0, "num_checkpoints": 10},
    {"name": "World Cup 15km Falun", "race_type": "15km", "technique": "freestyle", "location": "Falun, Sweden", "distance_km": 15.0, "num_checkpoints": 6},
]


async def seed_database(db: AsyncSession):
    """Seed database with initial data if empty."""
    result = await db.execute(select(Skier).limit(1))
    if result.scalar_one_or_none():
        return  # Already seeded

    # Create skiers
    skiers = []
    for data in SKIER_DATA:
        skier = Skier(**data)
        db.add(skier)
        skiers.append(skier)
    await db.flush()

    # Create races at various future times
    now = datetime.utcnow()
    races = []
    for i, template in enumerate(RACE_TEMPLATES):
        # Spread races: first one is "live", rest are upcoming
        if i == 0:
            start_time = now - timedelta(minutes=10)
            status = RaceStatus.LIVE
        elif i == 1:
            start_time = now + timedelta(hours=2)
            status = RaceStatus.UPCOMING
        else:
            start_time = now + timedelta(days=i, hours=random.randint(8, 16))
            status = RaceStatus.UPCOMING

        race = Race(
            name=template["name"],
            race_type=template["race_type"],
            technique=template["technique"],
            location=template["location"],
            distance_km=template["distance_km"],
            start_time=start_time,
            status=status,
            num_checkpoints=template["num_checkpoints"],
        )
        db.add(race)
        races.append(race)
    await db.flush()

    # Add entries: each race gets 15-20 random skiers
    for race in races:
        num_entries = random.randint(15, min(20, len(skiers)))
        selected = random.sample(skiers, num_entries)
        for bib, skier in enumerate(selected, 1):
            entry = RaceEntry(
                race_id=race.id,
                skier_id=skier.id,
                bib_number=bib,
            )
            db.add(entry)

    await db.commit()
