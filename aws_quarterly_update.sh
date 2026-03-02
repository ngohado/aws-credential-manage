#!/bin/bash

# AWS Quarterly Credential Update Script
# This script runs the quarterly update with proper logging and error handling
# Designed to be run via macOS Launch Agent every 3 months

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/aws_credential_updater.py"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/quarterly_update_$(date +%Y%m%d_%H%M%S).log"
EMAIL_RECIPIENT="${QUARTERLY_UPDATE_EMAIL:-}" # Set this environment variable if you want email notifications

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to send email notification (if configured)
send_notification() {
    local subject="$1"
    local body="$2"
    
    if [[ -n "$EMAIL_RECIPIENT" ]]; then
        if command -v mail &> /dev/null; then
            echo "$body" | mail -s "$subject" "$EMAIL_RECIPIENT"
            log_message "Email notification sent to $EMAIL_RECIPIENT"
        else
            log_message "WARNING: 'mail' command not found. Email notification not sent."
        fi
    fi
}

# Function to check prerequisites
check_prerequisites() {
    log_message "Checking prerequisites..."
    
    # Check if Python script exists
    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        log_message "ERROR: Python script not found at $PYTHON_SCRIPT"
        return 1
    fi
    
    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        log_message "ERROR: Python 3 is not installed"
        return 1
    fi
    
    # Check if 1Password CLI is available
    if ! command -v op &> /dev/null; then
        log_message "ERROR: 1Password CLI is not installed"
        return 1
    fi
    
    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        log_message "ERROR: AWS CLI is not installed"
        return 1
    fi
    
    log_message "All prerequisites satisfied"
    return 0
}

# Function to ensure 1Password is signed in
ensure_1password_session() {
    log_message "Checking 1Password session..."
    
    if ! op account list &> /dev/null; then
        log_message "ERROR: 1Password CLI is not signed in"
        log_message "Please run 'op signin' before scheduling this script"
        return 1
    fi
    
    log_message "1Password session is active"
    return 0
}

# Main execution function
main() {
    local start_time=$(date)
    log_message "=== AWS Quarterly Credential Update Started ==="
    log_message "Start time: $start_time"
    log_message "Script: $PYTHON_SCRIPT"
    log_message "Log file: $LOG_FILE"
    
    # Check prerequisites
    if ! check_prerequisites; then
        local error_msg="Prerequisites check failed. See log for details."
        log_message "ERROR: $error_msg"
        send_notification "AWS Quarterly Update Failed - Prerequisites" "$error_msg"
        exit 1
    fi
    
    # Ensure 1Password session
    if ! ensure_1password_session; then
        local error_msg="1Password session check failed. Please ensure you're signed in."
        log_message "ERROR: $error_msg"
        send_notification "AWS Quarterly Update Failed - 1Password" "$error_msg"
        exit 1
    fi
    
    # Run the quarterly update
    log_message "Starting quarterly credential update..."
    cd "$SCRIPT_DIR"
    
    if python3 "$PYTHON_SCRIPT" quarterly-update --password-max-age 90 --access-key-max-age 90 >> "$LOG_FILE" 2>&1; then
        local end_time=$(date)
        local success_msg="AWS quarterly credential update completed successfully!"
        log_message "SUCCESS: $success_msg"
        log_message "End time: $end_time"
        
        # Send success notification
        local notification_body="Quarterly AWS credential update completed successfully.

Start time: $start_time
End time: $end_time
Log file: $LOG_FILE

Summary:
- Updated expired passwords (>90 days)
- Updated outdated access keys (>90 days)
- All profiles processed

Check the log file for detailed results."
        
        send_notification "AWS Quarterly Update Successful" "$notification_body"
        
    else
        local end_time=$(date)
        local error_msg="AWS quarterly credential update failed. Check log for details."
        log_message "ERROR: $error_msg"
        log_message "End time: $end_time"
        
        # Send failure notification with log excerpt
        local log_excerpt=$(tail -50 "$LOG_FILE")
        local notification_body="Quarterly AWS credential update failed.

Start time: $start_time
End time: $end_time
Log file: $LOG_FILE

Last 50 log lines:
$log_excerpt"
        
        send_notification "AWS Quarterly Update Failed" "$notification_body"
        exit 1
    fi
    
    log_message "=== AWS Quarterly Credential Update Completed ==="
}

# Handle script arguments
case "${1:-}" in
    "test")
        # Test mode - just check prerequisites and 1Password session
        log_message "=== Test Mode ==="
        check_prerequisites && ensure_1password_session
        exit $?
        ;;
    "dry-run")
        # Dry run mode
        log_message "=== Dry Run Mode ==="
        check_prerequisites && ensure_1password_session
        if [[ $? -eq 0 ]]; then
            cd "$SCRIPT_DIR"
            python3 "$PYTHON_SCRIPT" --dry-run quarterly-update --password-max-age 90 --access-key-max-age 90
        fi
        exit $?
        ;;
    *)
        # Normal execution
        main
        ;;
esac