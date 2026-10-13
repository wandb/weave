#!/bin/bash

set -e  # Exit on any error

#==============================================================================
# Weave Development Environment Setup Script
#
# PURPOSE:
#   This script sets up a complete development environment for Weave, including:
#   - uv (Python package manager)
#   - nox (testing automation)
#   - prek (code quality hooks)
#   - Test environments for all shards
#   - Lint environment
#
# USAGE:
#   ./bin/codex_setup.sh
#
# REQUIREMENTS:
#   - Ubuntu 24.04 or compatible Linux distribution
#   - Internet connection for downloading packages
#
# FEATURES:
#   - Sequential execution for easier debugging
#   - Clear progress feedback and error handling
#
# AUTHOR: AI Assistant
# VERSION: 1.0
# LAST UPDATED: 2024
#==============================================================================

#------------------------------------------------------------------------------
# Python Development Tools Installation
#------------------------------------------------------------------------------

install_uv() {
    echo "Installing uv Python package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✓ uv installed successfully"
}

install_global_tools() {
    echo "Installing global development tools..."
    # Install tools sequentially for clear debugging output
    echo "  Installing nox..."
    uv tool install nox
    echo "  Installing prek..."
    uv tool install prek
    echo "✓ Global tools installed successfully"
}

setup_prek() {
    echo "Setting up prek hooks..."
    # Dry-run prek on a single file to force dependency installation
    prek run --hook-stage pre-push --files ./weave/__init__.py
    echo "✓ Prek setup completed"
}

#------------------------------------------------------------------------------
# Test Environment Setup
#------------------------------------------------------------------------------

install_test_environments() {
    echo "Installing test environment shards..."
    
    # Install all test shards sequentially for clear debugging
    echo "  Installing custom shard..."
    nox --install-only -e "tests-3.12(shard='custom')"
    echo "  ✓ Custom shard installed"
    
    echo "  Installing trace shard..."
    nox --install-only -e "tests-3.12(shard='trace')"
    echo "  ✓ Trace shard installed"
    
    echo "  Installing flow shard..."
    nox --install-only -e "tests-3.12(shard='flow')"
    echo "  ✓ Flow shard installed"
    
    echo "  Installing trace server bindings shard..."
    nox --install-only -e "tests-3.12(shard='trace_server_bindings')"
    echo "  ✓ Trace server bindings shard installed"
    
    echo "✓ All test environments installed successfully"
}

install_lint_environment() {
    echo "Installing lint environment..."
    nox -e lint -- dry-run
    echo "✓ Lint environment installed"
}

#------------------------------------------------------------------------------
# Main Execution Flow
#------------------------------------------------------------------------------

main() {
    echo "🚀 Starting Weave development environment setup..."
    echo "=================================================="
    echo ""
    
    # Run all installation steps sequentially for clear debugging
    echo "📦 Installing Python package manager..."
    install_uv
    echo ""
    
    echo "🛠️  Installing development tools..."
    install_global_tools
    echo ""
    
    echo "🧪 Installing test environments..."
    install_test_environments
    echo ""
    
    echo "🔍 Installing lint environment..."
    install_lint_environment
    echo ""
    
    echo "🔧 Setting up prek hooks..."
    setup_prek
    echo ""
    
    echo "=================================================="
    echo "🎉 All setup tasks completed successfully!"
    echo ""
    echo "📋 Your Weave development environment is ready!"
    echo ""
    echo "  🛠️  Development tools installed:"
    echo "     • uv (Python package manager)"
    echo "     • nox (testing automation)" 
    echo "     • prek (code quality hooks)"
    echo "     • Test environments for all shards"
    echo "     • Lint environment configured"
    echo ""
    echo "  🚀 Next steps:"
    echo "     • Run tests: nox -e tests"
    echo "     • Check code quality: prek run --all-files"
    echo "     • Start coding in your Weave development environment!"
    echo ""
    echo "Happy coding! 🎉"
}

# Script entry point
main "$@"
