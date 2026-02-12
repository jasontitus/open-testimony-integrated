import 'package:flutter/material.dart';

const Map<String, String> _countryFlags = {
  'NOR': '\u{1F1F3}\u{1F1F4}',
  'RUS': '\u{1F1F7}\u{1F1FA}',
  'ITA': '\u{1F1EE}\u{1F1F9}',
  'FRA': '\u{1F1EB}\u{1F1F7}',
  'FIN': '\u{1F1EB}\u{1F1EE}',
  'SWE': '\u{1F1F8}\u{1F1EA}',
  'GBR': '\u{1F1EC}\u{1F1E7}',
  'SUI': '\u{1F1E8}\u{1F1ED}',
  'GER': '\u{1F1E9}\u{1F1EA}',
  'USA': '\u{1F1FA}\u{1F1F8}',
  'CAN': '\u{1F1E8}\u{1F1E6}',
  'AUT': '\u{1F1E6}\u{1F1F9}',
};

class CountryFlag extends StatelessWidget {
  final String country;
  final double fontSize;

  const CountryFlag({
    super.key,
    required this.country,
    this.fontSize = 20,
  });

  @override
  Widget build(BuildContext context) {
    return Text(
      _countryFlags[country] ?? country,
      style: TextStyle(fontSize: fontSize),
    );
  }
}
