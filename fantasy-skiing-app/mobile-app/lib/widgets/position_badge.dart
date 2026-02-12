import 'package:flutter/material.dart';

class PositionBadge extends StatelessWidget {
  final int position;
  final double size;

  const PositionBadge({
    super.key,
    required this.position,
    this.size = 32,
  });

  Color get _backgroundColor {
    switch (position) {
      case 1:
        return const Color(0xFFFACC15);
      case 2:
        return const Color(0xFFD1D5DB);
      case 3:
        return const Color(0xFFD97706);
      default:
        return const Color(0xFFE5E7EB);
    }
  }

  Color get _textColor {
    switch (position) {
      case 1:
        return const Color(0xFF713F12);
      case 2:
        return const Color(0xFF374151);
      case 3:
        return Colors.white;
      default:
        return const Color(0xFF374151);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _backgroundColor,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        '$position',
        style: TextStyle(
          color: _textColor,
          fontWeight: FontWeight.bold,
          fontSize: size * 0.45,
        ),
      ),
    );
  }
}
