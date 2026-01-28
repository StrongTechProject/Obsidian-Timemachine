#!/usr/bin/env bash
#
# Obsidian Timemachine - One-line Installation Script
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/StrongTechProject/Obsidian-TimeMachine/main/install.sh | bash
#
# Or with options:
#   curl -fsSL https://raw.githubusercontent.com/StrongTechProject/Obsidian-TimeMachine/main/install.sh | bash -s -- --no-wizard
#

set -e

# ============================================================================
# Configuration
# ============================================================================

GITHUB_REPO="StrongTechProject/Obsidian-TimeMachine"
GITHUB_URL="https://github.com/${GITHUB_REPO}.git"
MIN_PYTHON_VERSION="3.10"
INSTALL_DIR=""  # Empty means pip install from git directly

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ============================================================================
# Helper Functions
# ============================================================================

print_banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}     ${BOLD}🕰️  Obsidian Timemachine - Installation Script${NC}     ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}==>${NC} ${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# ============================================================================
# Prerequisite Checks
# ============================================================================

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

get_python_cmd() {
    # Try different Python commands
    for cmd in python3 python; do
        if command -v "$cmd" &> /dev/null; then
            # Check if it's Python 3.10+
            version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            if [ -n "$version" ]; then
                major=$(echo "$version" | cut -d. -f1)
                minor=$(echo "$version" | cut -d. -f2)
                if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                    echo "$cmd"
                    return 0
                fi
            fi
        fi
    done
    return 1
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    
    local missing=()
    
    # Check Python
    PYTHON_CMD=$(get_python_cmd)
    if [ -z "$PYTHON_CMD" ]; then
        missing+=("Python ${MIN_PYTHON_VERSION}+")
    else
        local version=$("$PYTHON_CMD" --version 2>&1 | awk '{print $2}')
        print_success "Python $version found"
    fi
    
    # Check pip
    if [ -n "$PYTHON_CMD" ]; then
        if "$PYTHON_CMD" -m pip --version &> /dev/null; then
            print_success "pip found"
        else
            missing+=("pip")
        fi
    fi
    
    # Check Git
    if check_command git; then
        local git_version=$(git --version | awk '{print $3}')
        print_success "Git $git_version found"
    else
        missing+=("git")
    fi
    
    # Check rsync
    if check_command rsync; then
        print_success "rsync found"
    else
        missing+=("rsync")
    fi
    
    # Report missing dependencies
    if [ ${#missing[@]} -gt 0 ]; then
        echo ""
        print_error "Missing required dependencies:"
        for dep in "${missing[@]}"; do
            echo -e "   - $dep"
        done
        echo ""
        print_info "Please install the missing dependencies and try again."
        
        # Provide installation hints
        if [[ "$OSTYPE" == "darwin"* ]]; then
            print_info "On macOS, you can install these using Homebrew:"
            echo -e "   ${CYAN}brew install python git rsync${NC}"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            print_info "On Ubuntu/Debian:"
            echo -e "   ${CYAN}sudo apt install python3 python3-pip git rsync${NC}"
        fi
        
        exit 1
    fi
    
    echo ""
}

# ============================================================================
# Installation
# ============================================================================

check_existing_installation() {
    if "$PYTHON_CMD" -c "import ot" &> /dev/null; then
        local current_version=$("$PYTHON_CMD" -c "from importlib.metadata import version; print(version('obsidian-timemachine'))" 2>/dev/null || echo "unknown")
        print_warning "Obsidian Timemachine is already installed (version: $current_version)"
        echo ""
        read -p "Do you want to upgrade/reinstall? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled. Run 'ot update' to check for updates."
            exit 0
        fi
        UPGRADE_MODE=true
    else
        UPGRADE_MODE=false
    fi
}

install_package() {
    print_step "Installing Obsidian Timemachine..."
    
    # Determine if we're in a virtual environment
    local in_venv=false
    if [ -n "$VIRTUAL_ENV" ] || "$PYTHON_CMD" -c "import sys; sys.exit(0 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 1)" 2>/dev/null; then
        in_venv=true
    fi
    
    # Build pip install command
    local pip_args=("install")
    
    if [ "$UPGRADE_MODE" = true ]; then
        pip_args+=("--upgrade")
    fi
    
    # Use --user if not in a virtual environment
    if [ "$in_venv" = false ]; then
        pip_args+=("--user")
        print_info "Installing to user space (--user flag)"
    else
        print_info "Installing into virtual environment"
    fi
    
    pip_args+=("git+https://github.com/${GITHUB_REPO}.git")
    
    echo ""
    echo -e "${CYAN}Running:${NC} $PYTHON_CMD -m pip ${pip_args[*]}"
    echo ""
    
    if "$PYTHON_CMD" -m pip "${pip_args[@]}"; then
        print_success "Installation completed successfully!"
    else
        print_error "Installation failed"
        exit 1
    fi
}

verify_installation() {
    print_step "Verifying installation..."
    
    # Try to import the module
    if "$PYTHON_CMD" -c "import ot" &> /dev/null; then
        local installed_version=$("$PYTHON_CMD" -c "from importlib.metadata import version; print(version('obsidian-timemachine'))" 2>/dev/null || echo "unknown")
        print_success "Obsidian Timemachine $installed_version installed"
    else
        print_error "Installation verification failed"
        exit 1
    fi
    
    # Check if 'ot' command is available
    if check_command ot; then
        print_success "'ot' command is available"
    else
        # It might be in ~/.local/bin which may not be in PATH
        local user_bin="$HOME/.local/bin"
        if [ -f "$user_bin/ot" ]; then
            print_warning "'ot' command installed but not in PATH"
            print_info "Add this to your shell profile (.bashrc, .zshrc, etc.):"
            echo -e "   ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
            echo ""
            print_info "Or run directly:"
            echo -e "   ${CYAN}$user_bin/ot${NC}"
        else
            print_warning "Could not find 'ot' command in PATH"
        fi
    fi
}

run_setup_wizard() {
    if [ "$NO_WIZARD" = true ]; then
        return
    fi
    
    echo ""
    print_step "Setup Wizard"
    read -p "Would you like to run the configuration wizard now? [Y/n] " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Skipping wizard. Run 'ot setup' later to configure."
        return
    fi
    
    echo ""
    
    # Try to run ot setup
    if check_command ot; then
        ot setup
    elif [ -f "$HOME/.local/bin/ot" ]; then
        "$HOME/.local/bin/ot" setup
    else
        "$PYTHON_CMD" -m ot.cli.main setup
    fi
}

print_next_steps() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                    ${BOLD}🎉 Installation Complete!${NC}              ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo -e "  1. ${BOLD}Configure:${NC}     ot setup"
    echo -e "  2. ${BOLD}Run sync:${NC}      ot sync"
    echo -e "  3. ${BOLD}Open menu:${NC}     ot menu"
    echo -e "  4. ${BOLD}Check status:${NC}  ot status"
    echo ""
    echo -e "For more information: ${CYAN}https://github.com/${GITHUB_REPO}${NC}"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    # Parse arguments
    NO_WIZARD=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-wizard)
                NO_WIZARD=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [--no-wizard]"
                echo ""
                echo "Options:"
                echo "  --no-wizard    Skip the configuration wizard after installation"
                echo "  --help, -h     Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    print_banner
    
    # Check prerequisites
    check_prerequisites
    
    # Check for existing installation
    check_existing_installation
    
    # Install the package
    install_package
    
    # Verify installation
    verify_installation
    
    # Run setup wizard (optional)
    run_setup_wizard
    
    # Print next steps
    print_next_steps
}

main "$@"
