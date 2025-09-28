#!/bin/bash

# Azure App Service startup script for RSDN Bot
echo "Starting RSDN Bot..."

# Make sure we're in the right directory
cd /home/site/wwwroot

# Start with gunicorn (Azure's preferred method)
gunicorn --bind 0.0.0.0:$PORT app:application --timeout 300 --workers 1