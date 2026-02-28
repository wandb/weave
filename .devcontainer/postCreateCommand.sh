#!/bin/bash
set -e

echo "🚀 Setting up Weave development environment..."

# Fix cache permissions
echo "📁 Setting up cache directory..."
mkdir -p $HOME/.cache
sudo chown -R $USER $HOME/.cache

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y \
    libsndfile1 \
    build-essential \
    git \
    curl

# Install uv (Python package manager used in CI)
echo "🐍 Installing uv (Python package manager)..."
curl -LsSf https://astral.sh/uv/0.8.6/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Install pnpm (Node package manager)
echo "📦 Installing pnpm..."
npm install -g pnpm@9

# Install weave in development mode with test and dev dependencies
echo "🔧 Installing weave in development mode..."
pip install -e ".[test,dev]"

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
uv tool install pre-commit
pre-commit install

# Git configuration for pre-commit
echo "⚙️  Configuring git..."
git config --global --add safe.directory /workspaces/weave

# Install Node.js dependencies if package.json exists in sdks/node
if [ -f "sdks/node/package.json" ]; then
    echo "📦 Installing Node.js dependencies..."
    cd sdks/node
    pnpm install
    cd ../..
fi

echo "✅ Development environment setup complete!"
echo ""
echo "Available tools:"
echo "  - Python $(python --version)"
echo "  - Node.js $(node --version)"
echo "  - pnpm $(pnpm --version)"
echo "  - uv $(uv --version)"
echo ""
echo "Ready to develop! 🎉"
