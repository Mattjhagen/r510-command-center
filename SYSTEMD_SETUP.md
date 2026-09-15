# Systemd Service Setup for R510 Crime Camera Integration

This guide shows how to set up the Crime Camera Integration as systemd services that automatically start on boot and restart on crashes.

## Quick Install

```bash
cd /home/matt/r510-command-center
sudo ./install-systemd-services.sh
```

This will:
- ✅ Install systemd service files
- ✅ Create log files in `/var/log/`
- ✅ Enable auto-start on boot
- ✅ Start all services immediately

## Services Installed

### 1. crime-camera-bridge.service
- **Port**: 9000
- **Description**: Crime-Camera Bridge API server
- **Logs**: `/var/log/crime-camera-bridge.log`
- **Auto-restart**: Yes (on crash)
- **Resource limits**: 512MB RAM, 50% CPU

### 2. gods-eye-view.service
- **Port**: 4173
- **Description**: God's Eye View 3D globe interface
- **Logs**: `/var/log/gods-eye-view.log`
- **Auto-restart**: Yes (on crash)
- **Resource limits**: 1GB RAM, 100% CPU

### 3. r510-crime-camera.target
- **Description**: Combined target for both services
- **Use**: Control both services together

## Management Commands

### Control All Services

```bash
# Start all services
sudo systemctl start r510-crime-camera.target

# Stop all services
sudo systemctl stop r510-crime-camera.target

# Restart all services
sudo systemctl restart r510-crime-camera.target

# Check status
sudo systemctl status r510-crime-camera.target
```

### Individual Service Control

```bash
# Crime-Camera Bridge
sudo systemctl start crime-camera-bridge
sudo systemctl stop crime-camera-bridge
sudo systemctl restart crime-camera-bridge
sudo systemctl status crime-camera-bridge

# God's Eye View
sudo systemctl start gods-eye-view
sudo systemctl stop gods-eye-view
sudo systemctl restart gods-eye-view
sudo systemctl status gods-eye-view
```

### View Logs

```bash
# Live logs (follow mode)
sudo journalctl -u crime-camera-bridge -f
sudo journalctl -u gods-eye-view -f

# Last 50 lines
sudo journalctl -u crime-camera-bridge -n 50
sudo journalctl -u gods-eye-view -n 50

# Logs since boot
sudo journalctl -u crime-camera-bridge -b
sudo journalctl -u gods-eye-view -b

# Logs for specific time range
sudo journalctl -u crime-camera-bridge --since "1 hour ago"
sudo journalctl -u gods-eye-view --since "2026-09-15 00:00:00"

# Both services combined
sudo journalctl -u crime-camera-bridge -u gods-eye-view -f
```

### Log Files

Static log files are also available:
```bash
# Bridge logs
tail -f /var/log/crime-camera-bridge.log

# God's Eye View logs
tail -f /var/log/gods-eye-view.log
```

## Enable/Disable Auto-Start

### Enable (start on boot)

```bash
sudo systemctl enable crime-camera-bridge
sudo systemctl enable gods-eye-view
sudo systemctl enable r510-crime-camera.target
```

### Disable (don't start on boot)

```bash
sudo systemctl disable crime-camera-bridge
sudo systemctl disable gods-eye-view
sudo systemctl disable r510-crime-camera.target
```

## Check If Running

```bash
# Check if services are active
systemctl is-active crime-camera-bridge
systemctl is-active gods-eye-view

# Check if services are enabled
systemctl is-enabled crime-camera-bridge
systemctl is-enabled gods-eye-view

# List all R510 services
systemctl list-units | grep r510
```

## Verify URLs

After starting the services, verify they're accessible:

```bash
# Bridge status
curl http://localhost:9000/status | jq

# God's Eye View (should return HTML)
curl -I http://localhost:4173

# CCTV sources
curl http://localhost:4173/api/cctv/sources | jq '.sources | length'

# Crime incidents
curl http://localhost:9000/api/incidents | jq
```

## Troubleshooting

### Service Won't Start

```bash
# Check detailed status
sudo systemctl status crime-camera-bridge -l

# Check recent logs
sudo journalctl -u crime-camera-bridge -n 50 --no-pager

# Check if port is already in use
sudo lsof -i :9000
sudo lsof -i :4173
```

### Service Keeps Crashing

```bash
# Check restart count
sudo systemctl show crime-camera-bridge | grep NRestarts

# Check failure reason
sudo systemctl status crime-camera-bridge | grep -A 5 "Main PID"

# View crash logs
sudo journalctl -u crime-camera-bridge --since "10 minutes ago"
```

### Reset Service After Changes

If you modify the service files:

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Restart the service
sudo systemctl restart crime-camera-bridge
sudo systemctl restart gods-eye-view
```

### Check Resource Usage

```bash
# Show memory and CPU usage
systemctl status crime-camera-bridge
systemctl status gods-eye-view

# Or use systemd-cgtop
sudo systemd-cgtop
```

## Manual Uninstall

If you need to remove the systemd services:

```bash
# Stop services
sudo systemctl stop r510-crime-camera.target

# Disable services
sudo systemctl disable crime-camera-bridge
sudo systemctl disable gods-eye-view
sudo systemctl disable r510-crime-camera.target

# Remove service files
sudo rm /etc/systemd/system/crime-camera-bridge.service
sudo rm /etc/systemd/system/gods-eye-view.service
sudo rm /etc/systemd/system/r510-crime-camera.target

# Reload systemd
sudo systemctl daemon-reload

# Remove logs (optional)
sudo rm /var/log/crime-camera-bridge.log
sudo rm /var/log/gods-eye-view.log
```

## Monitoring Tips

### Set Up Email Alerts on Failure

Edit the service files to add:

```ini
[Unit]
OnFailure=status-email@%n.service
```

### Set Up Health Checks

Create a cron job to check health:

```bash
# Add to crontab
*/5 * * * * curl -f http://localhost:9000/status || systemctl restart crime-camera-bridge
*/5 * * * * curl -f http://localhost:4173 || systemctl restart gods-eye-view
```

### Monitor with systemd timer

Create a health check service that runs periodically using systemd timers.

## Security Notes

The service files include security hardening:
- ✅ Runs as user `matt` (not root)
- ✅ `NoNewPrivileges=true` - prevents privilege escalation
- ✅ `PrivateTmp=true` - isolated /tmp directory
- ✅ `ProtectSystem=strict` - read-only system directories
- ✅ `ProtectHome=read-only` - read-only home directories
- ✅ `ReadWritePaths` limited to app directory only
- ✅ Memory and CPU limits enforced

## Performance Tuning

### Increase Memory Limits

Edit service file and increase `MemoryMax`:

```ini
[Service]
MemoryMax=2G
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gods-eye-view
```

### Adjust Restart Policy

If service crashes frequently, adjust restart timing:

```ini
[Service]
Restart=always
RestartSec=30s
StartLimitInterval=10min
StartLimitBurst=10
```

## Integration with Other Services

### Start After Database

If you add a database, make services wait for it:

```ini
[Unit]
After=postgresql.service
Requires=postgresql.service
```

### Start With Nginx

```ini
[Unit]
BindsTo=nginx.service
After=nginx.service
```

## Quick Reference Card

```bash
# START
sudo systemctl start r510-crime-camera.target

# STOP
sudo systemctl stop r510-crime-camera.target

# RESTART
sudo systemctl restart r510-crime-camera.target

# STATUS
sudo systemctl status r510-crime-camera.target

# LOGS
sudo journalctl -u crime-camera-bridge -f
sudo journalctl -u gods-eye-view -f

# URLS
http://localhost:4173  # God's Eye View
http://localhost:9000  # Bridge API
```

## Support

If services fail to start after following this guide:
1. Check logs: `sudo journalctl -u [service-name] -n 50`
2. Verify file permissions: `ls -l /home/matt/r510-command-center/`
3. Check port availability: `sudo lsof -i :4173 -i :9000`
4. Verify Node.js/Python are installed
5. Test manual start: `cd /home/matt/r510-command-center && ./start-crime-camera-integration.sh`
