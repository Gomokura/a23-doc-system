/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#f4f6f9',
        sidebar: '#ffffff',
        surface: '#ffffff',
        surface2: '#f0f2f5',
        border: '#e4e7ed',
        'border-l': '#edf0f4',
        text: '#1f2329',
        text2: '#646a73',
        muted: '#8f959e',
        accent: '#3370ff',
        'accent-bg': 'rgba(51,112,255,.08)',
        'accent-light': 'rgba(51,112,255,.12)',
        red: '#f54a45',
        green: '#34c759',
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', '-apple-system', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '8px',
      },
    },
  },
  plugins: [],
}
