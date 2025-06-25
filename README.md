# Buggd Audio Recording System

The Buggd system is an environmental audio monitoring device that can operate in multiple recording modes. It supports both online (cellular) and offline (SD card) recording capabilities.

## Recording Modes

The recording mode is configured in the `config.json` file under `device.mode`, located in `/mnt/sd` . There are four available modes:

### Mode 0: Default Waraki Mode (MODE_DEFAULT_WARAKI)
- **Description**: Records audio in fixed-length segments and uploads them periodically (from the original buggd code)
- **Behavior**: 
  - Records audio segments (default: 20 minutes)
  - Compresses audio to MP3 format (configurable)
  - Uploads files via HTTP POST to the configured server
  - Powers down modem between uploads to save battery
  - Supports offline mode - saves to SD card if no connection
- **Use Case**: Best for battery-powered deployments with periodic connectivity

### Mode 1: HTTP Mode (MODE_HTTP)
- **Description**: Similar to Default mode but maintains persistent connection
- **Behavior**:
  - Records and uploads audio segments continuously
  - Keeps modem powered on for faster uploads
  - No delay before upload attempt
  - Higher power consumption than Default mode
- **Use Case**: Suitable for powered installations requiring frequent uploads

### Mode 2: WebSocket Safe Mode (MODE_WEBSOCKET_SAFE)
- **Description**: Records complete audio files then uploads via WebSocket
- **Behavior**:
  - Records audio segments to disk
  - Queues completed files for upload
  - Maintains persistent WebSocket connection
  - Deletes files after successful upload
- **Use Case**: Good for reliable streaming with file backup

### Mode 3: Continuous Stream Mode (MODE_CONTINUOUS_STREAM)
- **Description**: Real-time audio streaming without file storage
- **Behavior**:
  - Continuously captures raw audio
  - Compresses audio chunks on-the-fly
  - Streams via WebSocket immediately
  - No local file storage
  - Requires constant internet connection
- **Use Case**: Live audio monitoring applications

### Notes

#### Popping sound
Modes 0, 1, and 2 are not truly continuous recordings: at the end of each segment, the microphone stops and restarts, causing a popping sound. This pop is removed during post-processing. As a result, the actual recording length in these modes is N + 1 seconds, where N is the duration specified in the `config.json` file.

Mode 3, however, supports true continuous recording without any interruptions or popping sounds.

#### Connection Mode
Modes 0 and 1 use HTTP requests to send data to the Waraki server.

Modes 2 and 3 use WebSockets for data transmission.

## LED colour codes

When the full test is triggered, its results are displayed as follows:

| Top LED | Middle LED | Description |
|---------|------------|-------------|
| Magenta | off        | Tests running|
| Green   | off        | All tests pass |
| White   | off        | Failures in multiple categories |
| Yellow  |            | Failure in modem category |
| Yellow  | Red        | Modem USB enumeration fails |
| Yellow  | Magenta    | Modem not responding to AT commands |
| Yellow  | Blue       | SIM card not responding |
| Yellow  | Yellow     | No cell towers found - perhaps antenna not connected |
| Red     |            | Failure in I2C category
| Red     | Red        | I2S bridge not responding - perhaps mic board not connected |
| Red     | Cyan       | RTC not responding |
| Red     | Magenta    | LED controller not responding|
| Blue    |            | Failure in recording category|
| Blue    | Red        | No variance on internal channel |
| Blue    | Yellow     | No variance on external channel |
| Blue    | White      | No variance on either channel |

On a normal boot (factory test not triggered), a simplified test status is displayed for four seconds as follows:

| Top LED | Middle LED | Description |
|---------|------------|-------------|
| Magenta | Green | Factory test passed OK |
| Magenta | Red | Factory test failed or hasn't run |

## Useful Bugg OS Utilities

### Viewing Logs

The buggd service logs can be viewed using `journalctl`:

```bash
# View all logs
sudo journalctl 

# View all buggd service logs
sudo journalctl -u buggd.service

# View live logs (follow mode)
sudo journalctl -u buggd.service -f
```

### Service Management

The buggd service runs automatically on boot. To manage it:

```bash
# Check service status
sudo systemctl status buggd.service

# Stop the service (recommended before reboot)
sudo systemctl stop buggd.service

# Start the service
sudo systemctl start buggd.service

# Restart the service
sudo systemctl restart buggd.service

# Disable automatic startup
sudo systemctl disable buggd.service

# Enable automatic startup
sudo systemctl enable buggd.service
```

### Safe Shutdown Procedure

To safely shut down the device:

```bash
# First, stop the buggd service
sudo systemctl stop buggd.service

# Then reboot the system
sudo reboot
```

This ensures that any ongoing recordings are properly terminated and files are saved.

### Manual Control Utilities

The buggd package includes command-line utilities for testing and debugging:

```bash
# Control the modem
modemctl power on
modemctl power off
modemctl get_signal_strength
modemctl get_sim_state

# Control the soundcard
soundcardctl power internal on
soundcardctl power external on
soundcardctl gain 10
soundcardctl phantom P48
soundcardctl variance
```

### File Locations

- **Buggd code**: `/opt/venv/`
- **Configuration**: `/mnt/sd/config.json`
- **Logs**: `/mnt/sd/audio/logs`
- **Audio data**: `/mnt/sd/audio/`
- **Factory test results**: `/home/bugg/factory_test_results.txt`

### Configuration File

The device behavior is controlled by `/mnt/sd/config.json`. Key parameters include:

- `device.mode`: Recording mode (0-3)
- `device.server_url`: Upload server URL
- `sensor.record_length`: Audio segment duration (seconds)
- `sensor.compress_data`: Enable MP3 compression
- `sensor.gain`: Microphone gain (0-20)

### Troubleshooting

1. **No audio recording**:
   - Check LED status
   - Verify microphone connections
   - Review logs: `sudo journalctl -u buggd.service -f`

2. **No uploads**:
   - Check cellular signal: `modemctl get_signal_strength`
   - Verify SIM card: `modemctl get_sim_state`
   - Check internet connectivity in logs

3. **Factory test**:
   - Create `/mnt/sd/factory-test-full.txt` on SD card
   - Reboot device
   - Check results in `/home/bugg/factory_test_results.txt`

### Development

To modify the buggd code:

1. Stop the service: `sudo systemctl stop buggd.service`
2. Navigate to code: `cd /opt/venv/`
3. Make changes
4. Test manually: `sudo /opt/venv/bin/python -m buggd`
5. Restart service: `sudo systemctl start buggd.service`