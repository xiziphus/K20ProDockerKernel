#!/bin/bash
# Docker Kernel Monitoring Launcher
# Quick access to all monitoring tools

set -e

SCRIPT_DIR="kernel_build/scripts"

show_help() {
    echo "🚀 Docker Kernel Monitoring Tools"
    echo "=================================="
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  dashboard          Launch interactive monitoring dashboard"
    echo "  system             Check system and build environment status"
    echo "  docker             Monitor Docker daemon health"
    echo "  containers         Diagnose container issues"
    echo "  health             Generate comprehensive health report"
    echo "  watch              Start continuous monitoring"
    echo ""
    echo "Options:"
    echo "  --help, -h         Show this help message"
    echo "  --config FILE      Use custom configuration file"
    echo "  --output FILE      Save report to specific file"
    echo "  --html             Export HTML dashboard (dashboard command)"
    echo "  --quiet, -q        Quiet mode - minimal output"
    echo ""
    echo "Examples:"
    echo "  $0 dashboard                    # Launch interactive dashboard"
    echo "  $0 system --quiet              # Quick system check"
    echo "  $0 docker --check-once         # Single Docker health check"
    echo "  $0 containers --container abc123 # Diagnose specific container"
    echo "  $0 health --output report.json # Save health report"
    echo "  $0 watch                       # Start continuous monitoring"
    echo ""
    echo "Intel Mac Setup:"
    echo "  If you're on Intel Mac and getting Python errors:"
    echo "  ./fix_python.sh                # Fix Python symlink issue"
    echo ""
}

check_python() {
    # Use system Python3 to avoid ARM64/Intel issues on Mac
    PYTHON_CMD="/usr/bin/python3"
    
    if [ ! -f "$PYTHON_CMD" ]; then
        # Fallback to python3 in PATH
        if command -v python3 &> /dev/null; then
            PYTHON_CMD="python3"
        else
            echo "❌ Python 3 not found. Please install Python 3."
            exit 1
        fi
    fi
    
    # Test Python command works
    if ! "$PYTHON_CMD" --version &> /dev/null; then
        echo "❌ Python 3 not working. Trying to fix..."
        if [ -f "./fix_python.sh" ]; then
            ./fix_python.sh
            PYTHON_CMD="python3"
        else
            echo "❌ Python 3 issues detected. Please run: ./fix_python.sh"
            exit 1
        fi
    fi
    
    # Check if our monitoring scripts exist
    if [ ! -f "$SCRIPT_DIR/system_monitor.py" ]; then
        echo "❌ Monitoring scripts not found in $SCRIPT_DIR"
        echo "Please ensure you're running this from the project root directory."
        exit 1
    fi
}

run_dashboard() {
    echo "🚀 Launching monitoring dashboard..."
    "$PYTHON_CMD" "$SCRIPT_DIR/monitoring_dashboard.py" "$@"
}

run_system_check() {
    echo "🔧 Checking system and build environment..."
    "$PYTHON_CMD" "$SCRIPT_DIR/system_monitor.py" "$@"
}

run_docker_monitor() {
    echo "🐳 Monitoring Docker daemon health..."
    "$PYTHON_CMD" "$SCRIPT_DIR/docker_health_monitor.py" "$@"
}

run_container_diagnostics() {
    echo "🔍 Running container diagnostics..."
    "$PYTHON_CMD" "$SCRIPT_DIR/container_diagnostics.py" "$@"
}

run_health_report() {
    echo "🏥 Generating comprehensive health report..."
    "$PYTHON_CMD" "$SCRIPT_DIR/system_monitor.py" --output "health_report_$(date +%Y%m%d_%H%M%S).json" "$@"
    echo "✅ Health report generated"
}

run_continuous_monitoring() {
    echo "📊 Starting continuous monitoring..."
    echo "This will run system checks, Docker monitoring, and diagnostics"
    echo "Press Ctrl+C to stop"
    echo ""
    
    # Start Docker health monitor in background
    "$PYTHON_CMD" "$SCRIPT_DIR/docker_health_monitor.py" --daemon &
    DOCKER_PID=$!
    
    # Start dashboard in foreground
    "$PYTHON_CMD" "$SCRIPT_DIR/monitoring_dashboard.py" --refresh 30 --html
    
    # Clean up background process
    kill $DOCKER_PID 2>/dev/null || true
}

# Main script logic
case "${1:-help}" in
    dashboard)
        check_python
        shift
        run_dashboard "$@"
        ;;
    system)
        check_python
        shift
        run_system_check "$@"
        ;;
    docker)
        check_python
        shift
        run_docker_monitor "$@"
        ;;
    containers)
        check_python
        shift
        run_container_diagnostics "$@"
        ;;
    health)
        check_python
        shift
        run_health_report "$@"
        ;;
    watch)
        check_python
        shift
        run_continuous_monitoring "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac