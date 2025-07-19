/**
 * Example local environment configuration for Magician
 * 
 * To use your own OpenAI API key:
 * 1. Copy this file to `env.local.js`
 * 2. Update the values below
 * 3. Import from './env.local' instead of './env' in Magician.tsx
 */

export const ENV = {
  // Service type: 'demo' or 'openai'
  MAGICIAN_SERVICE: 'openai',
  
  // OpenAI configuration
  OPENAI_API_KEY: 'sk-your-actual-api-key-here',
  OPENAI_BASE_URL: 'https://api.openai.com/v1',
}; 