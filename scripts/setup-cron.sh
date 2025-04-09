#!/bin/bash

# Create the crontab file
cat > /etc/cron.d/scheduler-cron << EOF
# Run random_sampling.py at 2:00 AM daily
0 2 * * * root python /app/scripts/random_sampling.py >> /var/log/cron.log 2>&1

# Run sync_script.py at 3:00 AM daily
0 3 * * * root python /app/scripts/sync_script.py >> /var/log/cron.log 2>&1

# Run process_outputs.py at 4:00 AM daily
0 4 * * * root python /app/scripts/process_outputs.py >> /var/log/cron.log 2>&1

# Empty line at the end is required
EOF

# Give execution rights on the cron job
chmod 0644 /etc/cron.d/scheduler-cron

# Apply crontab file
crontab /etc/cron.d/scheduler-cron

# Create the log file to be able to run tail
touch /var/log/cron.log

# Start cron daemon
cron

# Follow the logs to keep the container running
tail -f /var/log/cron.log