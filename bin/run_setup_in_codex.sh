#!/bin/bash

set -e  # Exit on any error

#==============================================================================
# Weave Setup Runner for OpenAI Codex Universal Container
#
# PURPOSE:
#   This script runs the Weave development environment setup inside the
#   OpenAI Codex Universal Docker container. It provides a containerized
#   development environment setup that's isolated from the host system.
#
# USAGE:
#   ./bin/run_setup_in_codex.sh [OPTIONS]
#
# OPTIONS:
#   -h, --help      Show help message
#   --no-pull       Skip pulling the latest container image
#
# REQUIREMENTS:
#   - Docker installed and running on the host system
#   - Access to ghcr.io/openai/codex-universal:latest image
#   - Internet connection for pulling container image
#   - The setup script (bin/codex_setup.sh) in the current directory
#
# FEATURES:
#   - Runs setup in isolated container environment
#   - Mounts current workspace into container
#   - Handles container lifecycle automatically
#   - Provides colorized output and progress feedback
#   - Graceful error handling and cleanup
#
# ENVIRONMENT VARIABLES:
#   CODEX_IMAGE     Override the default Codex container image
#
# EXAMPLES:
#   ./bin/run_setup_in_codex.sh              # Run with latest image
#   ./bin/run_setup_in_codex.sh --no-pull   # Skip image pull
#   CODEX_IMAGE=custom:tag ./bin/run_setup_in_codex.sh  # Use custom image
#
# AUTHOR: AI Assistant
# VERSION: 1.0
# LAST UPDATED: 2024
#==============================================================================

#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------

readonly CODEX_IMAGE="${CODEX_IMAGE:-ghcr.io/openai/codex-universal:latest}"
readonly CONTAINER_NAME="weave-setup-$(date +%s)"
readonly WORKSPACE_PATH="$(pwd)"

#------------------------------------------------------------------------------
# Output Formatting
#------------------------------------------------------------------------------

# ANSI color codes for formatted output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

#------------------------------------------------------------------------------
# Docker Environment Validation
#------------------------------------------------------------------------------

check_docker() {
    log_info "Checking Docker availability..."
    
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed or not in PATH"
        log_info "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running or not accessible"
        log_info "Please start Docker daemon or check permissions"
        log_info "You may need to run: sudo systemctl start docker"
        exit 1
    fi
    
    log_success "Docker is available and running"
}

#------------------------------------------------------------------------------
# Container Image Management
#------------------------------------------------------------------------------

pull_codex_image() {
    log_info "Pulling OpenAI Codex Universal image: $CODEX_IMAGE"
    
    if docker pull "$CODEX_IMAGE"; then
        log_success "Container image pulled successfully"
    else
        log_error "Failed to pull container image"
        log_warning "You may need to authenticate with GitHub Container Registry:"
        log_info "  docker login ghcr.io"
        log_info "  # Use your GitHub username and a personal access token"
        exit 1
    fi
}

#------------------------------------------------------------------------------
# Container Execution
#------------------------------------------------------------------------------

run_setup_in_container() {
    log_info "Starting setup container..."
    
    # Create temporary script to run inside container
    local temp_script=$(mktemp)
    cat > "$temp_script" << 'EOF'
#!/bin/sh
set -e

echo "🚀 Running Weave setup inside Codex Universal container..."
echo "=================================================="
echo "Container environment: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "Working directory: $(pwd)"
echo "=================================================="

# Allow container to fully initialize
sleep 2

# Verify setup script exists
if [ ! -f "./bin/codex_setup.sh" ]; then
    echo "❌ Setup script not found: ./bin/codex_setup.sh"
    echo "Please ensure you're running this from the project root directory"
    exit 1
fi

# Make setup script executable and run it
chmod +x ./bin/codex_setup.sh
echo "Starting Weave development environment setup..."
echo ""
./bin/codex_setup.sh

echo ""
echo "🎉 Setup completed successfully inside container!"
echo "The development environment is now ready for use."
EOF
    
    # Make temporary script executable
    chmod +x "$temp_script"
    
    # Run container with proper configuration
    log_info "Executing setup inside container..."
    docker run \
        --name "$CONTAINER_NAME" \
        --rm \
        --interactive \
        --tty \
        --privileged \
        --volume "$WORKSPACE_PATH:/workspace" \
        --volume "$temp_script:/tmp/run_setup.sh" \
        --workdir "/workspace" \
        --env "DEBIAN_FRONTEND=noninteractive" \
        --env "TERM=xterm-256color" \
        "$CODEX_IMAGE" \
        /tmp/run_setup.sh
    
    # Clean up temporary script
    rm -f "$temp_script"
    
    log_success "Container setup completed successfully!"
}

#------------------------------------------------------------------------------
# Cleanup and Error Handling
#------------------------------------------------------------------------------

cleanup() {
    if [ -n "${CONTAINER_NAME:-}" ]; then
        log_info "Cleaning up container resources..."
        if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
            docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
        fi
    fi
}

#------------------------------------------------------------------------------
# Help and Usage Information
#------------------------------------------------------------------------------

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Run Weave development environment setup in OpenAI Codex Universal container.

This script provides a containerized setup experience that isolates the
installation process from your host system while setting up a complete
Weave development environment.

OPTIONS:
  -h, --help         Show this help message and exit
  --no-pull          Skip pulling the latest container image

ENVIRONMENT VARIABLES:
  CODEX_IMAGE        Override the default Codex image
                     (default: $CODEX_IMAGE)

EXAMPLES:
  $0                        # Run setup with latest image
  $0 --no-pull             # Run setup without pulling image
  $0 --help               # Show this help message

REQUIREMENTS:
  - Docker installed and running
  - Access to OpenAI Codex Universal container image
  - Internet connection for container and package downloads
  - Project must contain bin/codex_setup.sh script

For more information about Weave development, visit:
https://github.com/wandb/weave
EOF
}

#------------------------------------------------------------------------------
# Main Execution Logic
#------------------------------------------------------------------------------

main() {
    local skip_pull=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            --no-pull)
                skip_pull=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                echo ""
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Set up automatic cleanup on script exit
    trap cleanup EXIT
    
    # Display header
    echo "🐳 Weave Setup Runner for OpenAI Codex Universal"
    echo "================================================"
    echo "Container Image: $CODEX_IMAGE"
    echo "Workspace: $WORKSPACE_PATH"
    echo "================================================"
    echo ""
    
    # Validate environment
    check_docker
    
    # Handle container image
    if [ "$skip_pull" = false ]; then
        pull_codex_image
    else
        log_info "Skipping image pull (using existing local image)"
    fi
    
    # Verify setup script exists
    if [ ! -f "./bin/codex_setup.sh" ]; then
        log_error "Setup script not found: ./bin/codex_setup.sh"
        log_info "Please run this script from the Weave project root directory"
        log_info "Expected directory structure:"
        log_info "  ./bin/codex_setup.sh     # Main setup script"
        log_info "  ./bin/run_setup_in_codex.sh  # This script"
        exit 1
    fi
    
    # Execute setup in container
    run_setup_in_container
    
    # Success message
    echo ""
    echo "🎉 Weave development environment setup completed!"
    echo ""
    echo "📋 What happened:"
    echo "   • Setup ran inside OpenAI Codex Universal container"
    echo "   • Your workspace files were mounted and remain on your host"
    echo "   • Development tools are now installed and configured"
    echo ""
    echo "🚀 Next steps:"
    echo "   • Your development environment is ready to use"
    echo "   • Run tests with: nox -e tests"
    echo "   • Check code quality with: pre-commit run --all-files"
    echo "   • Start developing with Weave!"
    echo ""
    echo "Happy coding! 🎉"
}

#------------------------------------------------------------------------------
# Script Entry Point
#------------------------------------------------------------------------------

# Execute main function with all command line arguments
main "$@" 