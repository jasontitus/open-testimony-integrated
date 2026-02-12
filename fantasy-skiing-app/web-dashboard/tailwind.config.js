/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        snow: {
          50: '#f0f7ff',
          100: '#e0efff',
          200: '#b9dffe',
          300: '#7cc5fd',
          400: '#36a8fa',
          500: '#0c8eeb',
          600: '#006fc9',
          700: '#0159a3',
          800: '#064b86',
          900: '#0b3f6f',
        },
        nordic: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          500: '#22c55e',
          700: '#15803d',
          900: '#14532d',
        }
      }
    },
  },
  plugins: [],
}
