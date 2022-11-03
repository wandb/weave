const { defineConfig } = require("cypress");

module.exports = defineConfig({
  projectId: "dsmm8g",
  chromeWebSecurity: false,
  e2e: {
    baseUrl: 'http://localhost:9994',
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
});
