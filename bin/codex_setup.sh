#!/bin/bash

set -e  # Exit on any error

#==============================================================================
# Weave Development Environment Setup Script
# 
# This script sets up a complete development environment for Weave on Ubuntu 24.04
# It installs Docker, uv, development tools, and pre-configures test environments
# Many operations run in parallel for optimal performance.
#==============================================================================

#------------------------------------------------------------------------------
# Docker Installation Functions
#------------------------------------------------------------------------------

detect_environment() {
    # Check if we're in a container or limited environment
    if [ -f /.dockerenv ] || [ -n "${CONTAINER:-}" ] || [ -n "${CI:-}" ]; then
        echo "container"
    elif ! systemctl --version >/dev/null 2>&1; then
        echo "no-systemd"
    elif ! systemctl is-system-running >/dev/null 2>&1; then
        echo "systemd-limited"
    else
        echo "full-system"
    fi
}

install_docker_prerequisites() {
    echo "Installing Docker prerequisites..."
    sudo apt-get update
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
}

setup_docker_repository() {
    echo "Setting up Docker repository..."
    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Set up the repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
}

install_docker_engine() {
    echo "Installing Docker Engine..."
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Configure Docker for current user
    sudo usermod -aG docker $USER
    
    # Handle service management based on environment
    local env_type=$(detect_environment)
    echo "Detected environment: $env_type"
    
    case "$env_type" in
        "full-system")
            echo "Starting and enabling Docker service..."
            sudo systemctl start docker
            sudo systemctl enable docker
            echo "✓ Docker service started and enabled"
            ;;
        "systemd-limited"|"no-systemd")
            echo "⚠️  Limited systemd environment detected"
            echo "Attempting to start Docker daemon manually..."
            if sudo dockerd --version >/dev/null 2>&1; then
                # Try to start dockerd in background if not already running
                if ! pgrep -x "dockerd" > /dev/null; then
                    echo "Starting Docker daemon in background..."
                    sudo dockerd > /var/log/docker.log 2>&1 &
                    sleep 3
                    if pgrep -x "dockerd" > /dev/null; then
                        echo "✓ Docker daemon started manually"
                    else
                        echo "⚠️  Docker daemon may need manual start: sudo dockerd"
                    fi
                else
                    echo "✓ Docker daemon already running"
                fi
            fi
            ;;
        "container")
            echo "⚠️  Container environment detected"
            echo "Docker installed but service management skipped"
            echo "Note: You may need to mount Docker socket or use Docker-in-Docker"
            ;;
    esac
    
    echo "✓ Docker installation completed"
    
    # Test Docker access
    if command -v docker >/dev/null 2>&1; then
        if docker --version >/dev/null 2>&1; then
            echo "✓ Docker CLI is accessible"
        else
            echo "⚠️  Docker CLI installed but may need daemon restart"
        fi
    fi
}

install_docker() {
    echo "Installing Docker (required for ClickHouse container)..."
    install_docker_prerequisites
    setup_docker_repository
    install_docker_engine
}

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
# Container Setup Functions
#------------------------------------------------------------------------------

prefetch_containers() {
    echo "Pre-fetching required containers..."
    
    # Check if Docker is accessible
    if ! docker info >/dev/null 2>&1; then
        echo "⚠️  Docker daemon not accessible, skipping container prefetch"
        echo "You can manually pull containers later with: docker pull clickhouse/clickhouse-server"
        return 0
    fi
    
    echo "Pulling ClickHouse container..."
    if docker pull clickhouse/clickhouse-server; then
        echo "✓ ClickHouse container downloaded successfully"
    else
        echo "⚠️  Failed to pull ClickHouse container (this is non-critical)"
        echo "You can pull it manually later with: docker pull clickhouse/clickhouse-server"
    fi
}

#------------------------------------------------------------------------------
# Parallel Execution Orchestration
#------------------------------------------------------------------------------

run_uv_workflow() {
    echo "Starting uv-dependent workflow..."
    
    # Install uv first (required for subsequent steps)
    install_uv
    
    # Install global tools (depends on uv)
    install_global_tools
    
    # Now run uv-dependent parallel tasks
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

run_docker_workflow() {
    echo "Starting Docker-dependent workflow..."
    
    # Install Docker first (required for container operations)
    install_docker
    
    # Run Docker-dependent tasks
    prefetch_containers
    
    echo "✓ Docker workflow completed successfully"
}

#------------------------------------------------------------------------------
# Main Execution Flow
#------------------------------------------------------------------------------

main() {
    echo "🚀 Starting Weave development environment setup..."
    echo "=================================================="
    
    # Run completely independent workflows in parallel
    echo "Starting independent parallel workflows..."
    
    run_uv_workflow &
    local uv_workflow_pid=$!
    
    run_docker_workflow &
    local docker_workflow_pid=$!
    
    # Wait for both workflows to complete
    echo "Waiting for all workflows to complete..."
    wait $uv_workflow_pid
    wait $docker_workflow_pid
    
    echo "=================================================="
    echo "🎉 All setup tasks completed successfully!"
    echo ""
    
    # Provide environment-specific guidance
    local env_type=$(detect_environment)
    echo "📋 Next steps for your $env_type environment:"
    
    case "$env_type" in
        "full-system")
            echo "  ✅ Your development environment is fully ready!"
            echo "  • Log out and back in (or run 'newgrp docker') to use Docker without sudo"
            echo "  • All services should start automatically"
            ;;
        "systemd-limited"|"no-systemd")
            echo "  ⚠️  Limited systemd environment detected:"
            echo "  • Docker may need manual daemon start: sudo dockerd"
            echo "  • Check Docker status with: docker info"
            echo "  • Log out and back in (or run 'newgrp docker') for Docker group access"
            ;;
        "container")
            echo "  🐳 Container environment detected:"
            echo "  • Docker-in-Docker or socket mounting may be needed for containers"
            echo "  • Most development tools are ready to use"
            echo "  • Consider using bind mounts for persistent data"
            ;;
    esac
    
    echo ""
    echo "  🛠️  Development tools installed:"
    echo "  • uv (Python package manager)"
    echo "  • nox (testing automation)"
    echo "  • pre-commit (code quality hooks)"
    echo "  • Docker (containerization)"
    echo ""
    echo "Happy coding! 🚀"
}

# Execute main function
main "$@"
