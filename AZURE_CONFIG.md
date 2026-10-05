# RSDN Bot - Azure Configuration

## Resource Details
- **Resource Group**: `rsdnbot-rg`
- **Location**: West Europe
- **App Service Plan**: `rsdnbot-plan`
- **Web App Name**: `rsdnbot-monitor`
- **Subscription**: Pay-As-You-Go (`nbelyh@hotmail.com`)

## Deployment
Every push to `master` on GitHub deploys via GitHub Actions (`.github/workflows/deploy.yml`):
the tracked files are zipped with `git archive` and zip-deployed with the publish profile stored in the
`AZURE_WEBAPP_PUBLISH_PROFILE` repository secret; App Service runs the Oryx build
(`SCM_DO_BUILD_DURING_DEPLOYMENT=true`). A deploy can also be started manually from the Actions tab.

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
- **Source Repository**: https://github.com/nbelyh/rsdn-monitor-bot

## Database Location
- **File**: `/home/data/rsdn_messages.db` (`DATABASE_FILE` app setting)
- Kept outside `/home/site/wwwroot` so deployments never touch it
- **To delete**: `rm /home/data/rsdn_messages.db` (via SSH or Kudu)

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