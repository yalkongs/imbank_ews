/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'imbank': {
          primary: '#1e40af',
          secondary: '#3b82f6',
          accent: '#06b6d4',
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          dark: '#1e293b',
          light: '#f1f5f9'
        }
      }
    },
  },
  plugins: [],
}
