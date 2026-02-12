import 'package:flutter/material.dart';

class StatusBadge extends StatelessWidget {
  final String status;

  const StatusBadge({super.key, required this.status});

  Color get _backgroundColor {
    switch (status) {
      case 'live':
        return const Color(0xFFFEE2E2);
      case 'upcoming':
        return const Color(0xFFDBEAFE);
      case 'finished':
        return const Color(0xFFF3F4F6);
      case 'won':
        return const Color(0xFFDCFCE7);
      case 'lost':
        return const Color(0xFFFEE2E2);
      case 'pending':
        return const Color(0xFFFEF9C3);
      default:
        return const Color(0xFFF3F4F6);
    }
  }

  Color get _textColor {
    switch (status) {
      case 'live':
        return const Color(0xFF991B1B);
      case 'upcoming':
        return const Color(0xFF1E40AF);
      case 'finished':
        return const Color(0xFF374151);
      case 'won':
        return const Color(0xFF166534);
      case 'lost':
        return const Color(0xFF991B1B);
      case 'pending':
        return const Color(0xFF854D0E);
      default:
        return const Color(0xFF374151);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _backgroundColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (status == 'live') ...[
            Container(
              width: 6,
              height: 6,
              margin: const EdgeInsets.only(right: 4),
              decoration: const BoxDecoration(
                color: Color(0xFFEF4444),
                shape: BoxShape.circle,
              ),
            ),
          ],
          Text(
            status.toUpperCase(),
            style: TextStyle(
              color: _textColor,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}
