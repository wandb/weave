#!/bin/bash

set -e  # Exit on any error

#==============================================================================
# Weave Setup Runner for OpenAI Codex Universal Image
# 
# This script runs the Weave development environment setup inside the
# ghcr.io/openai/codex-universal:latest Docker container.
#==============================================================================

# Configuration
readonly CODEX_IMAGE="ghcr.io/openai/codex-universal:latest"
readonly CONTAINER_NAME="weave-setup-$(date +%s)"
readonly WORKSPACE_PATH="$(pwd)"

# Colors for output
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

check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed or not in PATH"
        log_info "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running or not accessible"
        log_info "Please start Docker daemon or check permissions"
        exit 1
    fi
    
    log_success "Docker is available"
}

pull_codex_image() {
    log_info "Pulling OpenAI Codex Universal image..."
    if docker pull "$CODEX_IMAGE"; then
        log_success "Codex image pulled successfully"
    else
        log_error "Failed to pull Codex image"
        log_info "You may need to authenticate with GitHub Container Registry:"
        log_info "docker login ghcr.io"
        exit 1
    fi
}

run_setup_in_container() {
    log_info "Starting setup container..."
    
    # Create a temporary script to run inside the container
    local temp_script=$(mktemp)
    cat > "$temp_script" << 'EOF'
#!/bin/sh
set -e
echo "🚀 Running Weave setup inside Codex Universal container..."
echo "=================================================="

# Wait for container to fully initialize
sleep 2

# Check if we have the setup script
if [ ! -f "./bin/codex_setup.sh" ]; then
    echo "❌ Setup script not found: ./bin/codex_setup.sh"
    exit 1
fi

# Make setup script executable
chmod +x ./bin/codex_setup.sh

# Run the setup script
echo "Starting setup script..."
./bin/codex_setup.sh

echo ""
echo "🎉 Setup completed inside container!"
echo "The development environment is now ready."
EOF
    
    # Make temp script executable
    chmod +x "$temp_script"
    
    # Create container with necessary mounts and privileges
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
        "$CODEX_IMAGE" \
        /tmp/run_setup.sh
    
    # Clean up temp script
    rm -f "$temp_script"
    
    log_success "Setup completed successfully!"
}

cleanup() {
    log_info "Cleaning up..."
    if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
        docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Run Weave development environment setup in OpenAI Codex Universal container"
    echo ""
    echo "Options:"
    echo "  -h, --help         Show this help message"
    echo "  --no-pull          Skip pulling the latest image"
    echo ""
    echo "Environment Variables:"
    echo "  CODEX_IMAGE        Override the default Codex image (default: $CODEX_IMAGE)"
    echo ""
    echo "Examples:"
    echo "  $0                        # Run setup with latest image"
    echo "  $0 --no-pull             # Run setup without pulling image"
    echo ""
}

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
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Set up cleanup trap
    trap cleanup EXIT
    
    echo "🐳 Weave Setup Runner for OpenAI Codex Universal"
    echo "================================================"
    echo ""
    
    # Check prerequisites
    check_docker
    
    # Pull image unless skipped
    if [ "$skip_pull" = false ]; then
        pull_codex_image
    else
        log_info "Skipping image pull (using local image)"
    fi
    
    # Verify setup script exists
    if [ ! -f "./bin/codex_setup.sh" ]; then
        log_error "Setup script not found: ./bin/codex_setup.sh"
        log_info "Please run this script from the project root directory"
        exit 1
    fi
    
    # Run setup
    run_setup_in_container
    
    echo ""
    echo "🎉 All done! Your Weave development environment is ready."
    echo ""
    echo "💡 Next steps:"
    echo "   • The setup ran inside the Codex Universal container"
    echo "   • Your workspace files were mounted and remain on your host"
    echo "   • You can now use the development tools in your environment"
    echo ""
}

# Execute main function with all arguments
main "$@" 