---
name: setup-demo-app
description: Scaffold a Vite + React + Tailwind demo app with a small, consistent project structure.
---

## When to use this

Use when you need a fresh demo app for quick UI experiments or reproductions.

## What to build

Create a Vite React TypeScript app and configure Tailwind. Keep it minimal.

Project structure after setup:

- src/
  - main.tsx (entry)
  - App.tsx (root UI)
  - components/
    - Header.tsx
    - Card.tsx
  - index.css (Tailwind import)
- index.html
- package.json

Style requirements:

- TypeScript components
- Functional components only
- Tailwind classes for styling (no CSS modules)
- No extra UI libraries

## Steps

1. Scaffold with Vite using the React TS template:
   npm create vite@latest demo-app -- --template react-ts

2. Install dependencies:
   cd demo-app
   npm install

3. Install and configure Tailwind using the Vite plugin.
   - npm install tailwindcss @tailwindcss/vite
   - Add the tailwind plugin to vite.config.ts
   - In src/index.css, replace contents with:
     @import "tailwindcss";

4. Implement the minimal UI:
   - Header: app title and short subtitle
   - Card: reusable card container
   - App: render Header + 2 Cards with placeholder text

## Definition of done

- npm run dev starts successfully
- package.json exists
- src/components/Header.tsx and src/components/Card.tsx exist
