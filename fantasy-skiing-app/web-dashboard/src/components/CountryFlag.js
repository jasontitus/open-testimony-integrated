import React from 'react';

const COUNTRY_FLAGS = {
  NOR: '🇳🇴', RUS: '🇷🇺', ITA: '🇮🇹', FRA: '🇫🇷', FIN: '🇫🇮',
  SWE: '🇸🇪', GBR: '🇬🇧', SUI: '🇨🇭', GER: '🇩🇪', USA: '🇺🇸',
  CAN: '🇨🇦', AUT: '🇦🇹', CZE: '🇨🇿', POL: '🇵🇱', JPN: '🇯🇵',
};

export default function CountryFlag({ country, className = '' }) {
  return (
    <span className={`inline-block ${className}`} title={country}>
      {COUNTRY_FLAGS[country] || country}
    </span>
  );
}
