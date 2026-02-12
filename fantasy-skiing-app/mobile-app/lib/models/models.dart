class Skier {
  final int id;
  final String name;
  final String country;
  final int age;
  final String specialty;
  final double skillRating;
  final String? photoUrl;
  final String? bio;

  Skier({
    required this.id,
    required this.name,
    required this.country,
    required this.age,
    required this.specialty,
    required this.skillRating,
    this.photoUrl,
    this.bio,
  });

  factory Skier.fromJson(Map<String, dynamic> json) => Skier(
        id: json['id'],
        name: json['name'],
        country: json['country'],
        age: json['age'],
        specialty: json['specialty'],
        skillRating: (json['skill_rating'] as num).toDouble(),
        photoUrl: json['photo_url'],
        bio: json['bio'],
      );
}

class Race {
  final int id;
  final String name;
  final String raceType;
  final String technique;
  final String location;
  final double distanceKm;
  final DateTime startTime;
  final String status;
  final int numCheckpoints;
  final int entryCount;

  Race({
    required this.id,
    required this.name,
    required this.raceType,
    required this.technique,
    required this.location,
    required this.distanceKm,
    required this.startTime,
    required this.status,
    required this.numCheckpoints,
    this.entryCount = 0,
  });

  factory Race.fromJson(Map<String, dynamic> json) => Race(
        id: json['id'],
        name: json['name'],
        raceType: json['race_type'],
        technique: json['technique'],
        location: json['location'],
        distanceKm: (json['distance_km'] as num).toDouble(),
        startTime: DateTime.parse(json['start_time']),
        status: json['status'],
        numCheckpoints: json['num_checkpoints'],
        entryCount: json['entry_count'] ?? 0,
      );

  bool get isLive => status == 'live';
  bool get isUpcoming => status == 'upcoming';
  bool get isFinished => status == 'finished';
}

class RaceEntry {
  final int id;
  final Skier skier;
  final int bibNumber;
  final int? finalPosition;
  final double? finalTimeSeconds;
  final bool dnf;
  final double pointsEarned;

  RaceEntry({
    required this.id,
    required this.skier,
    required this.bibNumber,
    this.finalPosition,
    this.finalTimeSeconds,
    this.dnf = false,
    this.pointsEarned = 0,
  });

  factory RaceEntry.fromJson(Map<String, dynamic> json) => RaceEntry(
        id: json['id'],
        skier: Skier.fromJson(json['skier']),
        bibNumber: json['bib_number'],
        finalPosition: json['final_position'],
        finalTimeSeconds: json['final_time_seconds'] != null
            ? (json['final_time_seconds'] as num).toDouble()
            : null,
        dnf: json['dnf'] ?? false,
        pointsEarned: (json['points_earned'] as num?)?.toDouble() ?? 0,
      );
}

class SkierOdds {
  final Skier skier;
  final double winOdds;
  final double podiumOdds;

  SkierOdds({
    required this.skier,
    required this.winOdds,
    required this.podiumOdds,
  });

  factory SkierOdds.fromJson(Map<String, dynamic> json) => SkierOdds(
        skier: Skier.fromJson(json['skier']),
        winOdds: (json['win_odds'] as num).toDouble(),
        podiumOdds: (json['podium_odds'] as num).toDouble(),
      );
}

class TeamMember {
  final int id;
  final Skier skier;
  final bool isCaptain;
  final double pointsEarned;

  TeamMember({
    required this.id,
    required this.skier,
    required this.isCaptain,
    this.pointsEarned = 0,
  });

  factory TeamMember.fromJson(Map<String, dynamic> json) => TeamMember(
        id: json['id'],
        skier: Skier.fromJson(json['skier']),
        isCaptain: json['is_captain'] ?? false,
        pointsEarned: (json['points_earned'] as num?)?.toDouble() ?? 0,
      );
}

class FantasyTeam {
  final int id;
  final int userId;
  final int raceId;
  final String name;
  final double totalPoints;
  final List<TeamMember> members;

  FantasyTeam({
    required this.id,
    required this.userId,
    required this.raceId,
    required this.name,
    this.totalPoints = 0,
    this.members = const [],
  });

  factory FantasyTeam.fromJson(Map<String, dynamic> json) => FantasyTeam(
        id: json['id'],
        userId: json['user_id'],
        raceId: json['race_id'],
        name: json['name'],
        totalPoints: (json['total_points'] as num?)?.toDouble() ?? 0,
        members: (json['members'] as List?)
                ?.map((m) => TeamMember.fromJson(m))
                .toList() ??
            [],
      );
}

class DashboardEntry {
  final int skierId;
  final String skierName;
  final String country;
  final int bibNumber;
  final bool isOnTeam;
  final bool isCaptain;
  final int currentPosition;
  final int currentCheckpoint;
  final int totalCheckpoints;
  final double lastTimeSeconds;
  final double gapToLeader;
  final double? speedKmh;
  final double fantasyPoints;

  DashboardEntry({
    required this.skierId,
    required this.skierName,
    required this.country,
    required this.bibNumber,
    this.isOnTeam = false,
    this.isCaptain = false,
    required this.currentPosition,
    required this.currentCheckpoint,
    required this.totalCheckpoints,
    required this.lastTimeSeconds,
    required this.gapToLeader,
    this.speedKmh,
    this.fantasyPoints = 0,
  });

  factory DashboardEntry.fromJson(Map<String, dynamic> json) => DashboardEntry(
        skierId: json['skier_id'],
        skierName: json['skier_name'],
        country: json['country'],
        bibNumber: json['bib_number'],
        isOnTeam: json['is_on_team'] ?? false,
        isCaptain: json['is_captain'] ?? false,
        currentPosition: json['current_position'],
        currentCheckpoint: json['current_checkpoint'],
        totalCheckpoints: json['total_checkpoints'],
        lastTimeSeconds: (json['last_time_seconds'] as num).toDouble(),
        gapToLeader: (json['gap_to_leader'] as num).toDouble(),
        speedKmh: json['speed_kmh'] != null
            ? (json['speed_kmh'] as num).toDouble()
            : null,
        fantasyPoints: (json['fantasy_points'] as num?)?.toDouble() ?? 0,
      );
}

class RaceDashboard {
  final Race race;
  final List<DashboardEntry> standings;
  final FantasyTeam? team;
  final double teamTotalPoints;

  RaceDashboard({
    required this.race,
    required this.standings,
    this.team,
    this.teamTotalPoints = 0,
  });

  factory RaceDashboard.fromJson(Map<String, dynamic> json) => RaceDashboard(
        race: Race.fromJson(json['race']),
        standings: (json['standings'] as List)
            .map((s) => DashboardEntry.fromJson(s))
            .toList(),
        team: json['team'] != null
            ? FantasyTeam.fromJson(json['team'])
            : null,
        teamTotalPoints:
            (json['team_total_points'] as num?)?.toDouble() ?? 0,
      );
}

class Bet {
  final int id;
  final int raceId;
  final String betType;
  final int skierId;
  final String skierName;
  final double amount;
  final double odds;
  final String status;
  final double payout;

  Bet({
    required this.id,
    required this.raceId,
    required this.betType,
    required this.skierId,
    required this.skierName,
    required this.amount,
    required this.odds,
    required this.status,
    this.payout = 0,
  });

  factory Bet.fromJson(Map<String, dynamic> json) => Bet(
        id: json['id'],
        raceId: json['race_id'],
        betType: json['bet_type'],
        skierId: json['skier_id'],
        skierName: json['skier_name'] ?? '',
        amount: (json['amount'] as num).toDouble(),
        odds: (json['odds'] as num).toDouble(),
        status: json['status'],
        payout: (json['payout'] as num?)?.toDouble() ?? 0,
      );
}

class LeaderboardEntry {
  final int rank;
  final int userId;
  final String username;
  final String? displayName;
  final double totalPoints;
  final int teamCount;

  LeaderboardEntry({
    required this.rank,
    required this.userId,
    required this.username,
    this.displayName,
    required this.totalPoints,
    required this.teamCount,
  });

  factory LeaderboardEntry.fromJson(Map<String, dynamic> json) =>
      LeaderboardEntry(
        rank: json['rank'],
        userId: json['user_id'],
        username: json['username'],
        displayName: json['display_name'],
        totalPoints: (json['total_points'] as num).toDouble(),
        teamCount: json['team_count'],
      );
}
