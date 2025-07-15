# Magician Environment Setup

## Quick Start

1. Create a `.env` file in the `weave-js` directory with the following content:

```bash
# OpenAI Configuration
VITE_OPENAI_API_KEY=sk-your-openai-api-key-here

# Service to use: 'demo' or 'openai'
VITE_MAGICIAN_SERVICE=openai

# Optional: Custom OpenAI base URL (for proxies or Azure)
# VITE_OPENAI_BASE_URL=https://api.openai.com/v1
```

2. Make sure `.env` is in your `.gitignore` (we've already added it)

## Usage Options

### Option 1: Environment Variables (Recommended)
Set up your `.env` file as shown above, then use:

```tsx
<MagicianContextProvider>
  <App />
</MagicianContextProvider>
```

### Option 2: Direct Props
Pass the configuration directly to the provider:

```tsx
<MagicianContextProvider 
  service="openai"
  openAIKey="sk-your-api-key"
>
  <App />
</MagicianContextProvider>
```

### Option 3: Demo Mode (Default)
No configuration needed - uses mock responses:

```tsx
<MagicianContextProvider>
  <App />
</MagicianContextProvider>
```

## Getting an OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (it starts with `sk-`)
5. Add it to your `.env` file

## Testing the Connection

You can test if OpenAI is working by checking the console when the provider initializes. If there's an error, it will fall back to demo mode automatically.

## Security Notes

- Never commit your API key to git
- Don't expose your API key in client-side code in production
- For production, use your backend service instead of direct OpenAI calls 