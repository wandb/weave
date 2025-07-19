/**
 * Environment configuration for Magician
 * For hackweek, we'll just hardcode these values
 */

export const ENV = {
  // Service type: 'demo' or 'openai'
  MAGICIAN_SERVICE: 'demo',
  
  // OpenAI configuration (only needed if MAGICIAN_SERVICE is 'openai')
  OPENAI_API_KEY: 'sk-your-api-key-here',
  OPENAI_BASE_URL: 'https://api.openai.com/v1',
}; 