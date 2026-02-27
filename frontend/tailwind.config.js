/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./app/**/*.{js,jsx}",
        "./components/**/*.{js,jsx}",
    ],
    theme: {
        extend: {
            colors: {
                loksabha: {
                    DEFAULT: '#006a4d',
                    light: '#e6f3ef',
                    dark: '#004d38',
                },
                rajyasabha: {
                    DEFAULT: '#8d153a',
                    light: '#f5e6eb',
                    dark: '#6b0f2d',
                },
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
            },
        },
    },
    plugins: [],
};
