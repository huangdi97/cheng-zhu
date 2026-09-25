/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'rgb(var(--c-bg-primary) / <alpha-value>)',
          secondary: 'rgb(var(--c-bg-secondary) / <alpha-value>)',
          tertiary: 'rgb(var(--c-bg-tertiary) / <alpha-value>)',
          hover: 'rgb(var(--c-bg-hover) / <alpha-value>)',
        },
        accent: {
          blue: 'rgb(var(--c-accent-blue) / <alpha-value>)',
          green: 'rgb(var(--c-accent-green) / <alpha-value>)',
          red: 'rgb(var(--c-accent-red) / <alpha-value>)',
          amber: 'rgb(var(--c-accent-amber) / <alpha-value>)',
        },
        text: {
          primary: 'rgb(var(--c-text-primary) / <alpha-value>)',
          secondary: 'rgb(var(--c-text-secondary) / <alpha-value>)',
          muted: 'rgb(var(--c-text-muted) / <alpha-value>)',
        },
        container: {
          primary: 'rgb(var(--c-primary-container) / <alpha-value>)',
          'on-primary': 'rgb(var(--c-on-primary-container) / <alpha-value>)',
          secondary: 'rgb(var(--c-secondary-container) / <alpha-value>)',
          'on-secondary': 'rgb(var(--c-on-secondary-container) / <alpha-value>)',
          tertiary: 'rgb(var(--c-tertiary-container) / <alpha-value>)',
          'on-tertiary': 'rgb(var(--c-on-tertiary-container) / <alpha-value>)',
        },
        surface: {
          variant: 'rgb(var(--c-surface-variant) / <alpha-value>)',
          'on-variant': 'rgb(var(--c-on-surface-variant) / <alpha-value>)',
        },
        outline: {
          subtle: 'rgb(var(--c-outline-variant) / <alpha-value>)',
        },
      },
    },
  },
  plugins: [],
}
