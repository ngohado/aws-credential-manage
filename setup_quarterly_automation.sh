#!/bin/bash

# Setup Script for AWS Quarterly Credential Update Automation
# This script sets up the macOS Launch Agent for automatic quarterly updates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_FILE="$SCRIPT_DIR/com.resola.aws-credential-updater.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.resola.aws-credential-updater.plist"

echo "🔧 Setting up AWS Quarterly Credential Update Automation"
echo "======================================================="

# Check if Launch Agents directory exists
if [[ ! -d "$LAUNCH_AGENTS_DIR" ]]; then
    echo "📁 Creating Launch Agents directory..."
    mkdir -p "$LAUNCH_AGENTS_DIR"
fi

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p "$SCRIPT_DIR/logs"

# Make scripts executable
echo "🔐 Making scripts executable..."
chmod +x "$SCRIPT_DIR/aws_quarterly_update.sh"

# Copy plist to Launch Agents directory
echo "📋 Installing Launch Agent..."
cp "$PLIST_FILE" "$INSTALLED_PLIST"

# Load the Launch Agent
echo "🚀 Loading Launch Agent..."
launchctl load "$INSTALLED_PLIST"

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "📅 Schedule: Runs quarterly on Jan 1, Apr 1, Jul 1, Oct 1 at 9:00 AM"
echo "📂 Logs: $SCRIPT_DIR/logs/"
echo "⚙️  Configuration: $INSTALLED_PLIST"
echo ""

# Test the setup
echo "🧪 Testing the setup..."
echo "Running dry-run to verify everything works..."

if "$SCRIPT_DIR/aws_quarterly_update.sh" dry-run; then
    echo ""
    echo "✅ Test successful! The automation is ready to run."
    echo ""
    echo "📧 To enable email notifications, set the QUARTERLY_UPDATE_EMAIL environment variable:"
    echo "   Edit $INSTALLED_PLIST"
    echo "   Change: <string>your-email@example.com</string>"
    echo "   To:     <string>your-actual@email.com</string>"
    echo "   Then run: launchctl unload '$INSTALLED_PLIST' && launchctl load '$INSTALLED_PLIST'"
    echo ""
    echo "🎯 Manual commands:"
    echo "   Test:         $SCRIPT_DIR/aws_quarterly_update.sh test"
    echo "   Dry run:      $SCRIPT_DIR/aws_quarterly_update.sh dry-run"
    echo "   Run now:      $SCRIPT_DIR/aws_quarterly_update.sh"
    echo "   View logs:    tail -f $SCRIPT_DIR/logs/launchd.log"
    echo ""
    echo "🗂️ Management commands:"
    echo "   Unload:       launchctl unload '$INSTALLED_PLIST'"
    echo "   Reload:       launchctl load '$INSTALLED_PLIST'"
    echo "   Check status: launchctl list | grep com.resola.aws-credential-updater"
else
    echo ""
    echo "❌ Test failed! Please check the error messages above."
    echo ""
    echo "Common issues:"
    echo "• 1Password CLI not signed in: Run 'op signin'"
    echo "• AWS CLI not configured: Run 'aws configure'"
    echo "• Missing dependencies: Install 1Password CLI and AWS CLI"
fi