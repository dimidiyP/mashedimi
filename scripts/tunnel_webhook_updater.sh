#!/bin/bash

# Cloudflare Tunnel Webhook Updater for Telegram Bot
# This script monitors Cloudflare tunnel URL changes and updates Telegram webhook

TELEGRAM_TOKEN="8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg"
LOG_FILE="/var/log/tunnel_webhook_updater.log"
URL_FILE="/tmp/current_tunnel_url.txt"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_current_tunnel_url() {
    # Extract URL from supervisor logs
    tail -n 100 /var/log/supervisor/cloudflare-tunnel.out.log 2>/dev/null | \
    grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' | \
    tail -1
}

get_current_webhook_url() {
    curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getWebhookInfo" | \
    jq -r '.result.url // empty' 2>/dev/null
}

update_webhook() {
    local new_url="$1"
    log "Updating webhook to: $new_url"
    
    local response=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook" \
        -H "Content-Type: application/json" \
        -d "{\"url\": \"${new_url}/api/webhook\"}")
    
    if echo "$response" | jq -e '.ok == true' >/dev/null 2>&1; then
        log "Webhook updated successfully"
        echo "$new_url" > "$URL_FILE"
        return 0
    else
        log "Failed to update webhook: $response"
        return 1
    fi
}

main() {
    log "Starting tunnel webhook updater..."
    
    while true; do
        # Get current tunnel URL
        tunnel_url=$(get_current_tunnel_url)
        
        if [ -z "$tunnel_url" ]; then
            log "No tunnel URL found, waiting..."
            sleep 30
            continue
        fi
        
        # Check if URL changed
        if [ -f "$URL_FILE" ]; then
            stored_url=$(cat "$URL_FILE" 2>/dev/null)
            if [ "$tunnel_url" = "$stored_url" ]; then
                # URL hasn't changed, check webhook status
                webhook_url=$(get_current_webhook_url)
                if [[ "$webhook_url" == *"$tunnel_url"* ]]; then
                    sleep 60
                    continue
                fi
            fi
        fi
        
        # URL changed or webhook not set, update it
        log "Detected tunnel URL: $tunnel_url"
        if update_webhook "$tunnel_url"; then
            log "Webhook monitoring active for: $tunnel_url"
        else
            log "Failed to update webhook, retrying in 30 seconds..."
            sleep 30
        fi
        
        sleep 60
    done
}

# Handle script termination
trap 'log "Tunnel webhook updater stopped"; exit 0' INT TERM

main "$@"