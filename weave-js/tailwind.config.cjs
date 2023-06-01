/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
  corePlugins: {
    /* 
    we disable preflight since it resets CSS styles for base html elements, and that will mess with 
    the layout/appearance of the site as a whole. 
    */
    preflight: false,
    /* we disable container since for some reason it does not follow the important selector strategy  (ie
       its css selector doesn't get prefixed with .tw-style */
    container: false
  },
  /* we use this so tailwind styles all require that they have an element with the tw-style somewhere
     in their parent hierarchy */
  important: '.tw-style',
};
