# 🏗️ EAS Build Setup Guide

Complete guide to build your Expense Tracker app for iOS and Android using Expo Application Services (EAS).

## 📋 Prerequisites

1. **Expo Account**: Sign up at [expo.dev](https://expo.dev)
2. **EAS CLI**: Install globally
   ```bash
   npm install -g @expo/eas-cli
   ```
3. **Login to EAS**:
   ```bash
   eas login
   ```

## 🔧 Initial Setup

### 1. Install Dependencies
```bash
cd mobile
npm install expo-build-properties
```

### 2. Configure EAS Project
```bash
eas build:configure
```
This will:
- Create/update `eas.json` (already provided)
- Link your project to EAS
- Generate project ID

### 3. Set Environment Variables

Set your Firebase config as EAS secrets:

```bash
# Firebase Configuration
eas secret:create --scope project --name FIREBASE_API_KEY --value "AIzaSyBd4yYwTCpvc_3DCqKhcs6wppq9cSFM6NY"
eas secret:create --scope project --name FIREBASE_AUTH_DOMAIN --value "expense-tracker-45860.firebaseapp.com"
eas secret:create --scope project --name FIREBASE_PROJECT_ID --value "expense-tracker-45860"
eas secret:create --scope project --name FIREBASE_STORAGE_BUCKET --value "expense-tracker-45860.firebasestorage.app"
eas secret:create --scope project --name FIREBASE_MESSAGING_SENDER_ID --value "459767973678"
eas secret:create --scope project --name FIREBASE_APP_ID --value "1:459767973678:web:0c172117e0a8e0c6a29cbf"
eas secret:create --scope project --name FIREBASE_MEASUREMENT_ID --value "G-VVXQCLLZMC"

# API Configuration
eas secret:create --scope project --name API_URL --value "https://your-production-api.com"
```

View your secrets:
```bash
eas secret:list
```

## 🚀 Build Commands

### Development Build
```bash
npm run build:development
# or
eas build --profile development
```
**Use for**: Testing with Expo Dev Client, debugging

### Preview Build  
```bash
npm run build:preview
# or
eas build --profile preview
```
**Use for**: Internal testing, sharing with team

### Production Build
```bash
npm run build:production
# or
eas build --profile production
```
**Use for**: App Store/Play Store submission

### Platform-Specific Builds
```bash
# iOS only
npm run build:ios
eas build --platform ios --profile production

# Android only  
npm run build:android
eas build --platform android --profile production
```

## 📱 Build Profiles Explained

### 🛠️ Development Profile
- **Purpose**: Development and debugging
- **Output**: Development client app
- **Firebase**: Uses development config
- **Size**: Larger (includes debugging tools)
- **Install**: Via QR code or direct download

### 👀 Preview Profile  
- **Purpose**: Internal testing and demos
- **Output**: Standalone APK/IPA
- **Firebase**: Uses production config
- **Size**: Optimized but not store-ready
- **Install**: Direct install (no stores)

### 🏪 Production Profile
- **Purpose**: App Store/Play Store submission
- **Output**: AAB (Android) / IPA (iOS) 
- **Firebase**: Uses production config
- **Size**: Fully optimized
- **Install**: Through app stores only

## 🔐 Security Best Practices

1. **Never commit .env files** with real secrets
2. **Use EAS secrets** for sensitive data
3. **Different configs** for dev/staging/production
4. **Rotate API keys** regularly

## 📦 Build Process

1. **EAS receives** your code and config
2. **Environment variables** injected from secrets
3. **Native code generated** (iOS/Android)
4. **App compiled** on EAS servers
5. **Build artifacts** available for download

## 🐛 Troubleshooting

### Build Fails
```bash
# Check build logs
eas build:list
eas build:view [BUILD_ID]
```

### Environment Issues
```bash
# Verify secrets are set
eas secret:list

# Update secret
eas secret:create --scope project --name SECRET_NAME --value "new-value" --force
```

### Clear Build Cache
```bash
eas build --clear-cache
