/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "color-mix(in srgb, var(--surface))",
        "surface-alt": "color-mix(in srgb, var(--surface-alt))",
        ink: "color-mix(in srgb, var(--ink))",
        "ink-muted": "color-mix(in srgb, var(--ink-muted))",
        "ink-subtle": "color-mix(in srgb, var(--ink-subtle))",
        primary: "color-mix(in srgb, var(--primary))",
        "primary-hover": "color-mix(in srgb, var(--primary-hover))",
        "primary-dark": "color-mix(in srgb, var(--primary-dark))",
        "border-hairline": "color-mix(in srgb, var(--border-hairline))",
      },
      keyframes: {
        'fade-in': {
          'from': { opacity: '0' },
          'to': { opacity: '1' },
        ],
    plugins: [],
  };
        'slide-down': {
          'from': { opacity: '0', transform: 'translateY(-16px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-up': {
          'from': { opacity: '0', transform: 'translateY(8px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
        'scale-in': {
          'from': { opacity: '0', transform: 'scale(0.95)' },
          'to': { opacity: '1', transform: 'scale(1)' },
        },
        'rotate-in': {
          'from': { opacity: '0', transform: 'rotate(-90deg) scale(0.8)' },
          'to': { opacity: '1', transform: 'rotate(0) scale(1)' },
        },
        'bounce-in': {
          '0%': { opacity: '0', transform: 'scale(0.3)' },
          '50%': { opacity: '1' },
          '100%': { transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 300ms ease-out both',
        'slide-up': 'slide-up 400ms cubic-bezier(0.4, 0, 0.2, 1) both',
        'slide-down': 'slide-down 400ms cubic-bezier(0.4, 0, 0.2, 1) both',
        'fade-up': 'fade-up 300ms ease-out both',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'shimmer': 'shimmer 2s infinite',
        'scale-in': 'scale-in 300ms cubic-bezier(0.4, 0, 0.2, 1) both',
        'bounce-in': 'bounce-in 500ms cubic-bezier(0.34, 1.56, 0.64, 1) both',
        'rotate-in': 'rotate-in 400ms cubic-bezier(0.34, 1.56, 0.64, 1) both',
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [],
}
