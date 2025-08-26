# Debugging and Troubleshooting Tools

This directory contains comprehensive debugging utilities for Docker-enabled kernel issues.

## 🔍 Available Tools

### 1. Comprehensive Debug Toolkit (`debug_toolkit.py`)
**Main debugging tool that runs all diagnostics**

```bash
# Run complete system diagnostics
python3 debug_toolkit.py

# Quick summary only
python3 debug_toolkit.py --summary-only

# Analyze last 12 hours of logs
python3 debug_toolkit.py --hours 12

# Save report to specific file
python3 debug_toolkit.py --output my_diagnostics.json
```

### 2. Log Analyzer (`log_analyzer.py`)
**Analyzes system logs for kernel and Docker issues**

```bash
# Analyze system logs (last 24 hours)
python3 log_analyzer.py

# Analyze specific container logs
python3 log_analyzer.py --container my_container

# Analyze last 6 hours only
python3 log_analyzer.py --hours 6

# Quiet mode (minimal output)
python3 log_analyzer.py --quiet
```

### 3. Network Debugger (`network_debugger.py`)
**Diagnoses network connectivity and Docker networking issues**

```bash
# Full network diagnostics
python3 network_debugger.py

# Check network interfaces only
python3 network_debugger.py --interfaces

# Check Docker networks only
python3 network_debugger.py --docker-networks

# Test container connectivity
python3 network_debugger.py --connectivity --container my_container

# Check iptables rules
python3 network_debugger.py --iptables
```

### 4. Storage Debugger (`storage_debugger.py`)
**Diagnoses storage, overlay filesystem, and volume issues**

```bash
# Full storage diagnostics
python3 storage_debugger.py

# Check storage drivers only
python3 storage_debugger.py --drivers

# Check overlay filesystem
python3 storage_debugger.py --overlay

# Check disk usage
python3 storage_debugger.py --disk

# Check container storage
python3 storage_debugger.py --containers

# Check volume usage
python3 storage_debugger.py --volumes
```

## 📊 What Each Tool Checks

### Log Analyzer
- ✅ System logs (journalctl, dmesg, syslog)
- ✅ Docker daemon logs
- ✅ Container logs
- ✅ Kernel error patterns
- ✅ Docker error patterns
- ✅ Network error patterns
- ✅ Storage error patterns
- ✅ Cgroup error patterns

### Network Debugger
- ✅ Network interfaces (including Docker bridges)
- ✅ Docker network configuration
- ✅ iptables rules for Docker
- ✅ Container connectivity tests
- ✅ Internet connectivity from containers
- ✅ DNS resolution in containers
- ✅ Container-to-container communication
- ✅ Port mapping functionality

### Storage Debugger
- ✅ Docker storage drivers
- ✅ Overlay filesystem support
- ✅ Disk usage and space
- ✅ Container storage configuration
- ✅ Volume usage and management
- ✅ Large file detection
- ✅ Storage performance issues

## 🚨 Common Issues and Solutions

### Docker Daemon Won't Start
```bash
# Check Docker health
python3 debug_toolkit.py --summary-only

# Analyze Docker logs
python3 log_analyzer.py --hours 2

# Check kernel configuration
python3 debug_toolkit.py | grep -A 10 "KERNEL"
```

### Container Networking Issues
```bash
# Full network diagnostics
python3 network_debugger.py

# Test specific container
python3 network_debugger.py --connectivity --container problem_container

# Check Docker bridge
python3 network_debugger.py --interfaces
```

### Storage/Overlay Issues
```bash
# Check overlay filesystem
python3 storage_debugger.py --overlay

# Check disk space
python3 storage_debugger.py --disk

# Check storage driver
python3 storage_debugger.py --drivers
```

### Kernel Configuration Issues
```bash
# Check kernel features
python3 debug_toolkit.py | grep -A 20 "missing_features"

# Analyze kernel logs
python3 log_analyzer.py --hours 1 | grep -i kernel
```

## 📁 Report Files

All tools save detailed reports to the `diagnostic_reports/` directory:

- `comprehensive_diagnostics_YYYYMMDD_HHMMSS.json` - Complete system report
- `log_analysis_YYYYMMDD_HHMMSS.json` - Log analysis report
- `network_diagnostics_YYYYMMDD_HHMMSS.json` - Network diagnostics report
- `storage_diagnostics_YYYYMMDD_HHMMSS.json` - Storage diagnostics report

## 🔧 Exit Codes

The tools use standard exit codes:
- `0` - No issues found
- `1` - Non-critical issues found
- `2` - Critical issues found

This allows for scripting and automation:

```bash
# Check if system is healthy
if python3 debug_toolkit.py --quiet; then
    echo "System is healthy"
else
    echo "Issues detected - check reports"
fi
```

## 💡 Tips

1. **Run comprehensive diagnostics first** to get an overview
2. **Use specific tools** to dive deeper into particular issues
3. **Check reports** for detailed information and recommendations
4. **Run tools as root** for complete system access (especially for iptables and kernel logs)
5. **Regular monitoring** helps catch issues early

## 🆘 Getting Help

If you encounter issues with the debugging tools themselves:

1. Check that all dependencies are installed
2. Ensure you have appropriate permissions
3. Verify Docker is installed (for Docker-specific checks)
4. Check the tool's help: `python3 tool_name.py --help`

For kernel or Docker issues found by the tools, refer to the recommendations in the generated reports.