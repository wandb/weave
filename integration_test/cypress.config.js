const { defineConfig } = require("cypress");

// Retrieve the port from the environment variable or set a default
const FE_PORT = process.env.FE_PORT || '9994';
const BASE_URL = `http://localhost:${FE_PORT}`;

module.exports = defineConfig({
  projectId: "dsmm8g",
  chromeWebSecurity: false,
  e2e: {
    baseUrl: BASE_URL,
    setupNodeEvents(on, config) {
      // implement node event listeners here
      // ❗ Must be declared at the top of the function to prevent conflicts
      [on, config] = require('@deploysentinel/cypress-debugger/plugin')(
        on,
        config,
      );
    },
  },
});
