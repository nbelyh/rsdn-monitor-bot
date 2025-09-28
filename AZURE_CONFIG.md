# RSDN Bot - Azure Configuration

## Resource Details
- **Resource Group**: `rsdnbot-rg`
- **Location**: West Europe
- **App Service Plan**: `rsdnbot-plan`
- **Web App Name**: `rsdnbot-monitor`

## Monitoring Commands

### View Live Logs
```bash
az webapp log tail --name rsdnbot-monitor --resource-group rsdnbot-rg
```

### View Log Files
```bash
az webapp log download --name rsdnbot-monitor --resource-group rsdnbot-rg
```

### SSH into App Service
```bash
az webapp ssh --name rsdnbot-monitor --resource-group rsdnbot-rg
```

### Check App Status
```bash
az webapp show --name rsdnbot-monitor --resource-group rsdnbot-rg --query "state"
```

## Useful URLs
- **App URL**: https://rsdnbot-monitor.azurewebsites.net
- **Kudu Console**: https://rsdnbot-monitor.scm.azurewebsites.net
- **Git Repository**: https://rsdnbot-monitor.scm.azurewebsites.net/rsdnbot-monitor.git

## Database Location
- **File**: `/home/site/wwwroot/rsdn_messages.db`
- **To delete**: `rm /home/site/wwwroot/rsdn_messages.db` (via SSH or Kudu)

## Environment Variables
The app gets configuration from:
- `TELEGRAM_BOT_TOKEN` - Set in Azure App Service Configuration
- `CHECK_INTERVAL_MINUTES` - Default: 1
- `RSDN_URL` - Default: https://rsdn.org
- `DATABASE_FILE` - Default: rsdn_messages.db

## Multi-Chat Features
- Users can register with `/start` command
- Each chat maintains independent forum filtering
- No hardcoded chat IDs needed
- Commands automatically appear in Telegram UI