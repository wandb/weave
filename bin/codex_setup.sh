#!/bin/bash

set -e  # Exit on any error

#==============================================================================
# Weave Development Environment Setup Script
# 
# This script sets up a complete development environment for Weave
# It installs uv, development tools, and pre-configures test environments
# Many operations run in parallel for optimal performance.
#==============================================================================

#------------------------------------------------------------------------------
# Development Tools Installation Functions
#------------------------------------------------------------------------------

install_uv() {
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✓ uv installed successfully"
}

install_global_tools() {
    echo "Installing global development tools..."
    # Run tool installations in parallel since they're independent
    uv tool install nox &
    uv tool install pre-commit &
    wait  # Wait for both installations to complete
    echo "✓ Global tools installed successfully"
}

setup_precommit() {
    echo "Setting up pre-commit hooks..."
    # Dry-run precommit on a single file (forces dependencies to be installed)
    pre-commit run --hook-stage pre-push --files ./weave/__init__.py
    echo "✓ Pre-commit setup completed"
}

#------------------------------------------------------------------------------
# Test Environment Setup Functions
#------------------------------------------------------------------------------

install_test_environments() {
    echo "Installing test environment shards in parallel..."
    
    # Start all test shard installations in parallel
    nox --install-only -e "tests-3.12(shard='custom')" &
    local custom_pid=$!
    
    nox --install-only -e "tests-3.12(shard='trace')" &
    local trace_pid=$!
    
    nox --install-only -e "tests-3.12(shard='flow')" &
    local flow_pid=$!
    
    nox --install-only -e "tests-3.12(shard='trace_server')" &
    local server_pid=$!
    
    nox --install-only -e "tests-3.12(shard='trace_server_bindings')" &
    local bindings_pid=$!
    
    # Wait for each shard and provide feedback
    wait $custom_pid && echo "  ✓ Custom shard installed"
    wait $trace_pid && echo "  ✓ Trace shard installed"
    wait $flow_pid && echo "  ✓ Flow shard installed"
    wait $server_pid && echo "  ✓ Trace server shard installed"
    wait $bindings_pid && echo "  ✓ Trace server bindings shard installed"
    
    echo "✓ All test environments installed successfully"
}

install_lint_environment() {
    echo "Installing lint environment..."
    nox -e lint -- dry-run &
    local lint_pid=$!
    wait $lint_pid && echo "✓ Lint environment installed"
}

#------------------------------------------------------------------------------
# ClickHouse Installation Functions
#------------------------------------------------------------------------------

install_clickhouse_prerequisites() {
    echo "Installing ClickHouse prerequisites..."
    sudo apt-get update
    sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
    echo "✓ ClickHouse prerequisites installed"
}

setup_clickhouse_repository() {
    echo "Setting up ClickHouse repository..."
    # Download the ClickHouse GPG key and store it in the keyring
    curl -fsSL 'https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml.key' | sudo gpg --dearmor -o /usr/share/keyrings/clickhouse-keyring.gpg
    
    # Get the system architecture
    local arch=$(dpkg --print-architecture)
    
    # Add the ClickHouse repository to apt sources
    echo "deb [signed-by=/usr/share/keyrings/clickhouse-keyring.gpg arch=${arch}] https://packages.clickhouse.com/deb stable main" | sudo tee /etc/apt/sources.list.d/clickhouse.list
    
    # Update apt package lists
    sudo apt-get update
    echo "✓ ClickHouse repository configured"
}

install_clickhouse_packages() {
    echo "Installing ClickHouse server and client..."
    
    # Use the official ClickHouse installation script with stdin feeding
    echo "Installing via official ClickHouse script..."
    printf '\n\n\n\n\n' | DEBIAN_FRONTEND=noninteractive curl -sSL https://install.clickhouse.com/ | sh -s -- server client
    
    echo "✓ ClickHouse packages installed"
}

install_clickhouse() {
    echo "Installing ClickHouse database..."
    
    # install_clickhouse_prerequisites
    setup_clickhouse_repository
    install_clickhouse_packages
    
    echo "✓ ClickHouse installation completed"
}

#------------------------------------------------------------------------------
# Parallel Workflow Functions
#------------------------------------------------------------------------------

run_uv_workflow() {
    echo "Starting uv-dependent workflow..."
    
    # Install uv first (required for subsequent steps)
    install_uv
    
    # Install global tools (depends on uv)
    install_global_tools
    
    # Run uv-dependent parallel tasks
    echo "Starting uv-dependent parallel tasks..."
    
    install_test_environments &
    local test_envs_pid=$!
    
    install_lint_environment &
    local lint_env_pid=$!
    
    setup_precommit &
    local precommit_pid=$!
    
    # Wait for uv-dependent tasks
    wait $test_envs_pid
    wait $lint_env_pid
    wait $precommit_pid
    
    echo "✓ uv workflow completed successfully"
}

run_clickhouse_workflow() {
    echo "Starting ClickHouse workflow..."
    
    # Install ClickHouse (independent of uv workflow)
    install_clickhouse
    
    echo "✓ ClickHouse workflow completed successfully"
}

#------------------------------------------------------------------------------
# Main Execution Flow
#------------------------------------------------------------------------------

main() {
    echo "🚀 Starting Weave development environment setup..."
    echo "=================================================="
    
    # Run completely independent workflows in parallel
    echo "Starting parallel workflows..."
    
    run_uv_workflow &
    local uv_workflow_pid=$!
    
    run_clickhouse_workflow &
    local clickhouse_workflow_pid=$!
    
    # Wait for both workflows to complete
    echo "Waiting for all workflows to complete..."
    wait $uv_workflow_pid
    wait $clickhouse_workflow_pid
    
    echo "=================================================="
    echo "🎉 All setup tasks completed successfully!"
    echo ""
    echo "📋 Your development environment is ready!"
    echo ""
    echo "  🛠️  Development tools installed:"
    echo "  • uv (Python package manager)"
    echo "  • nox (testing automation)"
    echo "  • pre-commit (code quality hooks)"
    echo "  • Test environments for all shards"
    echo "  • Lint environment configured"
    echo "  • ClickHouse database server"
    echo ""
    echo "  🗃️  ClickHouse quick start:"
    echo "  • Connect: clickhouse-client"
    echo "  • Default user: default (no password set)"
    echo ""
    echo "Happy coding! 🚀"
}

# Execute main function
main "$@"
