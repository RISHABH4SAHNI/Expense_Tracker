#!/bin/bash

# EAS Secrets Setup Script
# Run this script to set up all Firebase environment variables as EAS secrets

echo "🔐 Setting up EAS secrets for Expense Tracker..."

# Check if EAS CLI is installed
if ! command -v eas &> /dev/null; then
    echo "❌ EAS CLI is not installed. Please install it first:"
    echo "npm install -g @expo/eas-cli"
    exit 1
fi

# Check if user is logged in
if ! eas whoami &> /dev/null; then
    echo "❌ Please login to EAS first:"
    echo "eas login"
    exit 1
fi

echo "🔥 Setting Firebase configuration secrets..."
eas secret:create --scope project --name FIREBASE_API_KEY --value "AIzaSyBd4yYwTCpvc_3DCqKhcs6wppq9cSFM6NY" --force
eas secret:create --scope project --name FIREBASE_AUTH_DOMAIN --value "expense-tracker-45860.firebaseapp.com" --force
eas secret:create --scope project --name FIREBASE_PROJECT_ID --value "expense-tracker-45860" --force
eas secret:create --scope project --name FIREBASE_STORAGE_BUCKET --value "expense-tracker-45860.firebasestorage.app" --force
eas secret:create --scope project --name FIREBASE_MESSAGING_SENDER_ID --value "459767973678" --force
eas secret:create --scope project --name FIREBASE_APP_ID --value "1:459767973678:web:0c172117e0a8e0c6a29cbf" --force
eas secret:create --scope project --name FIREBASE_MEASUREMENT_ID --value "G-VVXQCLLZMC" --force

echo "🌐 Setting API configuration secrets..."
eas secret:create --scope project --name API_URL --value "https://your-production-api.com" --force

echo "✅ All secrets have been set up successfully!"
echo "📋 View your secrets with: eas secret:list"