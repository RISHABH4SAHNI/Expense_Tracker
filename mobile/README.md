# 📱 Expense Tracker Mobile App

React Native (Expo) mobile application for personal finance tracking with AI-powered insights.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm start

# Run on specific platforms
npm run ios          # iOS simulator
npm run android      # Android emulator
npm run web          # Web browser
```

## 📦 Tech Stack

- **Framework**: React Native with Expo SDK 53
- **Navigation**: React Navigation 7
- **State Management**: React Context + Local Storage
- **Database**: SQLite (expo-sqlite) with Secure Storage
- **UI Components**: Custom components with React Native elements
- **Charts**: react-native-chart-kit + react-native-svg
- **Authentication**: Firebase Auth
- **Storage**: AsyncStorage + Expo SecureStore

## 🏗️ Architecture

### Folder Structure
```
src/
├── screens/              # Main app screens
│   ├── HomeScreen.js        # Dashboard overview
│   ├── TransactionsScreen.js # Transaction list & management
│   ├── AnalyticsScreen.js   # Charts and insights
│   ├── ChatScreen.js        # AI-powered Q&A
│   └── ...
├── components/           # Reusable UI components
│   ├── transactions/        # Transaction-specific components
│   │   ├── TransactionCard.js
│   │   ├── TransactionForm.js
│   │   └── TransactionList.js
│   └── ...
├── services/            # API and external service integrations
│   ├── api.js              # Backend API client
│   ├── auth.js             # Authentication service
│   ├── storage.js          # Local storage wrapper
│   └── transactions/       # Transaction services
├── features/            # Feature-specific logic
│   ├── manual/             # Manual transaction entry
│   └── ...
├── integrations/        # External integrations
│   └── aa/                 # Account Aggregator (disabled)
├── storage/             # Database layer
│   ├── db.js               # SQLite wrapper
│   └── types.js            # Data models
└── config/              # App configuration
    └── firebaseConfig.js   # Firebase setup
```

### Key Features

- ✅ **Manual Transaction Entry** - Add income/expenses with categories
- ✅ **Local SQLite Storage** - Offline-first with data persistence
- ✅ **Firebase Authentication** - Secure user accounts
- ✅ **Analytics Dashboard** - Visual charts and spending insights
- ✅ **AI-Powered Q&A** - Ask questions about your finances
- 🔄 **Account Aggregator Integration** - Bank sync (pending regulatory approval)
- 📊 **Export Capabilities** - CSV export functionality
- 🔒 **Secure Storage** - Encrypted local data storage

## 🔧 Development

### Environment Setup

1. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Configure Firebase** (required):
   ```env
   EXPO_PUBLIC_FIREBASE_API_KEY=your_firebase_api_key
   EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
   EXPO_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
   EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET=your_project.firebasestorage.app
   EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=123456789
   EXPO_PUBLIC_FIREBASE_APP_ID=1:123456789:web:abcdef
   EXPO_PUBLIC_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX
   ```

3. **Configure API endpoint**:
   ```env
   EXPO_PUBLIC_API_URL=http://localhost:8000  # Development
   # EXPO_PUBLIC_API_URL=https://your-api.com  # Production
   ```

### Available Scripts

#### Development
```bash
npm start                # Start Expo dev server
npm run ios             # Run on iOS simulator
npm run android         # Run on Android emulator
npm run web             # Run on web browser
```

#### Building (EAS Build)
```bash
# Development builds
npm run build:dev       # All platforms
npm run build:dev:ios   # iOS only

# Preview builds  
npm run build:preview   # All platforms
npm run build:preview:ios # iOS only

# Production builds
npm run build:production  # All platforms
npm run build:prod:ios   # iOS production
npm run build:ios:prod   # Alternative iOS production
```

#### iOS Deployment
```bash
npm run submit:ios      # Submit to TestFlight
npm run deploy:ios      # Build + Submit in one command
```

## 🍎 iOS Distribution

### Prerequisites
- Apple Developer Account ($99/year)
- EAS CLI: `npm install -g @expo/eas-cli`
- Configured `eas.json` with your Apple credentials

### Build for iOS
```bash
# Production build for TestFlight
eas build -p ios --profile production

# Or using npm script
npm run build:ios:prod
```

### TestFlight Distribution
```bash
# Auto-submit to TestFlight after build
eas submit --platform ios --latest

# Or using npm script
npm run submit:ios
```

### Apple Developer Configuration
Update `eas.json` with your details:
```json
"submit": {
  "production": {
    "ios": {
      "appleId": "your-apple-id@example.com",
      "ascAppId": "1234567890",
      "appleTeamId": "ABCDEFGHIJ"
    }
  }
}
