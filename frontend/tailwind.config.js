/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'accent-primary': '#8b5cf6',
                'accent-hover': '#7c3aed',
                'text-primary': '#f8fafc',
                'text-secondary': '#94a3b8',
                'text-muted': '#64748b',
            }
        },
    },
    plugins: [],
}
