# Magician Environment Setup

## Quick Start

The Magician uses simple JavaScript configuration files for easy setup.

### Default Setup (Demo Mode)

The toolkit comes configured in demo mode - no changes needed to try it out!

### Using OpenAI

You have two options:

#### Option 1: Quick Test (Not for committing)
Edit `src/WBMagician/env.js` directly:

```javascript
export const ENV = {
  MAGICIAN_SERVICE: 'openai',  // Change from 'demo'
  OPENAI_API_KEY: 'sk-your-actual-api-key-here',
  OPENAI_BASE_URL: 'https://api.openai.com/v1',
};
```

**Warning**: Don't commit this file with your API key!

#### Option 2: Local Configuration (Recommended)

This approach keeps your API key safe:

1. Copy `env.local.example.js` to `env.local.js`
2. Edit `env.local.js` with your API key:
   ```javascript
   export const ENV = {
     MAGICIAN_SERVICE: 'openai',
     OPENAI_API_KEY: 'sk-your-actual-api-key-here',
     OPENAI_BASE_URL: 'https://api.openai.com/v1',
   };
   ```

3. In `Magician.tsx` (line 77), change:
   ```javascript
   import {ENV} from './env';
   ```
   to:
   ```javascript
   import {ENV} from './env.local';
   ```

The `env.local.js` file is gitignored and won't be committed.

## File Structure Explained

- `env.js` - Default config (demo mode) that's safe to commit
- `env.local.js` - Your personal config with API keys (gitignored)
- `env.local.example.js` - Template for creating env.local.js

## Configuration via Props

You can also configure the service directly:

```tsx
<MagicianContextProvider 
  service="openai"
  openAIKey="sk-your-api-key"
>
  <App />
</MagicianContextProvider>
```

## Getting an OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (it starts with `sk-`)
5. Add it to your `env.js` or `env.local.js` file

## Troubleshooting

- If OpenAI fails, the system automatically falls back to demo mode
- Check the browser console for error messages
- Ensure your API key has chat completion permissions

## Security Notes

- For hackweek, editing `env.js` directly is fine
- For production, use the backend service instead of client-side API keys
- Never commit real API keys to public repositories 