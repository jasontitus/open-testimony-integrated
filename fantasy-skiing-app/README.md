# Fantasy XC Skiing

A fantasy sports platform for cross-country skiing. Draft your team, place bets on races, and track live results as skiers compete through checkpoints.

## Architecture

- **Backend API**: FastAPI + PostgreSQL (Python)
- **Web Dashboard**: React + Tailwind CSS
- **Mobile App**: Flutter (iOS & Android)
- **Infrastructure**: Docker Compose, Nginx reverse proxy

## Features

- **Fantasy Teams**: Draft up to 5 skiers per race, designate a captain for 2x points
- **Betting**: Place win or podium bets with dynamic odds based on skier ratings
- **Live Dashboard**: Real-time race tracking with checkpoint-by-checkpoint standings
- **Race Simulation**: Built-in simulation engine for testing and demo purposes
- **Leaderboard**: Global rankings based on accumulated fantasy points
- **WebSocket Support**: Live updates pushed to connected clients

## Quick Start

### Docker (recommended)

```bash
cd fantasy-skiing-app
docker compose up -d
```

Services:
- Web Dashboard: http://localhost:3001
- API: http://localhost:8001
- Nginx proxy: http://localhost:8080

### Development (without Docker)

**API Server:**
```bash
cd api-server
pip install -r requirements.txt
# Start PostgreSQL on localhost:5433
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Web Dashboard:**
```bash
cd web-dashboard
npm install
REACT_APP_API_URL=http://localhost:8001 npm start
```

**Mobile App:**
```bash
cd mobile-app
flutter pub get
flutter run
```

## API Endpoints

### Auth
- `POST /auth/register` - Create account
- `POST /auth/login` - Sign in
- `GET /auth/me` - Get profile

### Races
- `GET /races` - List races (filter by status: upcoming/live/finished)
- `GET /races/{id}` - Race details
- `GET /races/{id}/entries` - Start list / results
- `GET /races/{id}/odds` - Betting odds
- `GET /races/{id}/dashboard` - Live dashboard with standings + team info
- `GET /races/{id}/checkpoints` - Checkpoint timing data

### Fantasy Teams
- `POST /teams` - Create team (skier_ids, captain_id)
- `GET /teams` - List your teams

### Betting
- `POST /bets` - Place a bet
- `GET /bets` - List your bets

### Other
- `GET /leaderboard` - Global rankings
- `GET /skiers` - All skiers
- `POST /admin/simulate/{id}` - Advance race by one checkpoint
- `POST /admin/simulate/{id}/full` - Run full race simulation
- `WS /ws/race/{id}` - WebSocket for live race updates

## Points System

| Position | Points |
|----------|--------|
| 1st | 100 |
| 2nd | 80 |
| 3rd | 65 |
| 4th | 55 |
| 5th | 50 |
| 6th-10th | 45-29 |
| 11th-20th | 26-12 |
| 21st+ | 10 |

Captain bonus: 2x points for your designated captain.

## Seed Data

The database is automatically seeded with:
- 30 professional skiers (men & women) with real-world-inspired profiles
- 8 race events across different distances and techniques
- The first race starts in "live" status for immediate testing
