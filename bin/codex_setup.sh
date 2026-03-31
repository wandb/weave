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
#   - ClickHouse database server
#   - Test environments for all shards
#   - Lint environment
#
# USAGE:
#   ./bin/codex_setup.sh
#
# REQUIREMENTS:
#   - Ubuntu 24.04 or compatible Linux distribution
#   - sudo access for package installation
#   - Internet connection for downloading packages
#
# FEATURES:
#   - Sequential execution for easier debugging
#   - Robust ClickHouse installation with expect automation
#   - Clear progress feedback and error handling
#   - Development-ready configuration with empty passwords
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
    
    echo "  Installing trace server shard..."
    nox --install-only -e "tests-3.12(shard='trace_server')"
    echo "  ✓ Trace server shard installed"
    
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
# ClickHouse Database Installation
#------------------------------------------------------------------------------

install_clickhouse_prerequisites() {
    echo "Installing ClickHouse prerequisites..."
    sudo apt-get update
    sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
    echo "✓ ClickHouse prerequisites installed"
}

setup_clickhouse_repository() {
    echo "Setting up ClickHouse repository..."
    
    # Download and install ClickHouse GPG key
    curl -fsSL 'https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml.key' | \
        sudo gpg --dearmor -o /usr/share/keyrings/clickhouse-keyring.gpg
    
    # Add ClickHouse repository to apt sources
    local arch=$(dpkg --print-architecture)
    echo "deb [signed-by=/usr/share/keyrings/clickhouse-keyring.gpg arch=${arch}] https://packages.clickhouse.com/deb stable main" | \
        sudo tee /etc/apt/sources.list.d/clickhouse.list
    
    # Update package lists
    sudo apt-get update
    echo "✓ ClickHouse repository configured"
}

install_clickhouse_packages() {
    echo "Installing ClickHouse server and client..."
    
    # Install expect if not available (needed for handling interactive prompts)
    if ! command -v expect >/dev/null 2>&1; then
        echo "  Installing expect for prompt automation..."
        sudo apt-get update
        DEBIAN_FRONTEND=noninteractive sudo apt-get install -y expect
    fi
    
    # Use expect to handle interactive password prompts automatically
    echo "  Installing ClickHouse packages with automated prompt handling..."
    expect -c "
        set timeout 300
        spawn sudo apt-get install -y clickhouse-server clickhouse-client
        expect {
            \"*password for the default user*\" { send \"\r\"; exp_continue }
            \"*Password*\" { send \"\r\"; exp_continue }  
            \"*password*\" { send \"\r\"; exp_continue }
            \"*Enter*\" { send \"\r\"; exp_continue }
            \"*Press*\" { send \"\r\"; exp_continue }
            \"*(y/N)*\" { send \"y\r\"; exp_continue }
            \"*Continue*\" { send \"\r\"; exp_continue }
            eof
        }
    "
    
    echo "✓ ClickHouse packages installed"
}

install_clickhouse() {
    echo "Installing ClickHouse database..."
    
    # Note: Prerequisites installation is commented out as it may not be needed
    # in container environments where basic packages are already available
    # install_clickhouse_prerequisites
    
    setup_clickhouse_repository
    install_clickhouse_packages
    
    echo "✓ ClickHouse installation completed"
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
    
    echo "🗃️  Installing ClickHouse database..."
    install_clickhouse
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
    echo "     • ClickHouse database server"
    echo ""
    echo "  🗃️  ClickHouse quick start:"
    echo "     • Connect: clickhouse-client"
    echo "     • Default user: default (no password required)"
    echo "     • HTTP interface: http://localhost:8123"
    echo "     • TCP interface: localhost:9000"
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
