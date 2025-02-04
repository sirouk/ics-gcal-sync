# Calendar Sync Tool

This tool synchronizes events from an ICS calendar feed to a Google Calendar. It's particularly useful for keeping a Google Calendar updated with events from external calendar systems that provide ICS feeds.

## Setup

1. Clone the repository:

```bash
cd $HOME
git clone https://github.com/sirouk/ics-gcal-sync
cd ics-gcal-sync
```

2. Install Python 3.11:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
```

3. Create a Python virtual environment:

```bash
cd $HOME/ics-gcal-sync
python3.11 -m venv .venv
source .venv/bin/activate
```

4. Install required packages:

```bash
pip install -r requirements.txt
```

5. Set up Google Calendar API:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Enable the Google Calendar API
   - Create OAuth 2.0 credentials (Desktop application)
   - Download the client secret JSON file
   - Save it in your project directory

6. Run the script:

```bash
python sync_calendar.py
```

On first run, you'll be prompted for:
- The ICS calendar URL
- Your Google Calendar ID
- Path to your Google client secret JSON file

The script will save these settings for future use.

## Running as a Service with PM2

1. Install PM2 if not already installed:

```bash
# Install PM2 if not already installed
if command -v pm2 &> /dev/null
then
    pm2 startup && pm2 save --force
else
    sudo apt install jq npm -y
    sudo npm install pm2 -g && pm2 update
    npm install pm2@latest -g && pm2 update && pm2 save --force && pm2 startup && pm2 save
fi
```

2. Start the sync service:

```bash
cd $HOME/ics-gcal-sync
source .venv/bin/activate
pm2 start sync_calendar.py --name calendar-sync --interpreter python3
```

3. Ensure PM2 starts on system boot:

```bash
pm2 startup && pm2 save --force
```

### PM2 Log Management

Set up log rotation:

```bash
# Install pm2-logrotate module
pm2 install pm2-logrotate

# Configure log rotation
pm2 set pm2-logrotate:max_size 50M
pm2 set pm2-logrotate:retain 10
pm2 set pm2-logrotate:compress true
pm2 set pm2-logrotate:rotateInterval '0 0 * * *'  # Daily rotation
```

### Useful PM2 Commands

```bash
# View logs
pm2 logs calendar-sync

# Monitor processes
pm2 monit

# Restart service
pm2 restart calendar-sync

# Stop service
pm2 stop calendar-sync
```

## Security Note

Keep your client_secret.json and config.json files secure - they contain sensitive credentials. Never commit them to version control.