# Gunicorn configuration for Azure App Service
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
workers = 1

# Application
module = "app:application"
worker_class = "sync"
timeout = 300
keepalive = 2
max_requests = 1000