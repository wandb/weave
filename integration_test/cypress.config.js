const { defineConfig } = require("cypress");
const { plugin: replayPlugin } = require("@replayio/cypress")
const cypressSplit = require('cypress-split')

// Retrieve the port from the environment variable or set a default
const FE_PORT = process.env.FE_PORT || '9994';
const BASE_URL = `http://localhost:${FE_PORT}`;

module.exports = defineConfig({
  projectId: "dsmm8g",
  chromeWebSecurity: false,
  e2e: {
    baseUrl: BASE_URL,
    experimentalSessionAndOrigin: true,
    setupNodeEvents(on, config) {
      cypressSplit(on, config)

      // 🙋‍♂️ Add this line to install the replay plugin
      replayPlugin(on, config, {
        upload: true,
        apiKey: process.env.REPLAY_API_KEY,
      });
      // Make sure that setupNodeEvents returns config
      return config;
    },
  },
});
