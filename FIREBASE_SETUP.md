# 🔥 Firebase Setup Guide

This guide will help you complete the Firebase setup for your Expense Tracker app.

## 📋 Current Status

✅ Firebase Admin SDK installed  
✅ Mobile app Firebase configuration ready  
✅ Authentication routes configured  
❌ **Missing: Service Account Key** (Required)

## 🔑 Step 1: Get Firebase Service Account Key

### Go to Firebase Console
1. Visit [Firebase Console](https://console.firebase.google.com/)
2. Select your project: `expense-tracker-45860`

### Generate Service Account Key
1. Click **Project Settings** (gear icon)
2. Go to **Service accounts** tab
3. Scroll to **Firebase Admin SDK** section
4. Click **"Generate new private key"**
5. Click **"Generate key"** to confirm
6. Download the JSON file (e.g., `expense-tracker-45860-firebase-adminsdk-xxxxx.json`)

## 📁 Step 2: Place Service Account File

1. Rename the downloaded file to: `firebase-service-account.json`
2. Place it in: `server/firebase-service-account.json`

```bash
# Your project structure should look like:
server/
├── firebase-service-account.json  # ← Place here
├── .env
├── app/
└── ...
```

## 🔧 Step 3: Verify Configuration

### Check Environment Variables
Make sure your `server/.env` file contains:
```bash
DEV_MODE=true
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json
```

### Test Firebase Connection
```bash
cd server
source venv/bin/activate
python -c "from app.services.firebase_admin import initialize_firebase; print('✅ Success!' if initialize_firebase() else '❌ Failed!')"
```

## 🚀 Step 4: Start Your Server

```bash
cd server
source venv/bin/activate
uvicorn main:app --reload --port 8000
