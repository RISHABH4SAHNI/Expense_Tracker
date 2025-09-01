# Production API URL
eas secret:create --scope project --name API_URL --value "https://your-production-api.com"
```

### TestFlight Tester Management

Once your iOS build is uploaded to TestFlight, follow these steps to invite testers:

#### Step 1: Access TestFlight in App Store Connect
1. Go to [App Store Connect](https://appstoreconnect.apple.com)
2. Navigate to **My Apps** → **ExpenseTrackerTest** → **TestFlight** tab
3. Select your uploaded build from the list

#### Step 2: Internal Testing (Up to 100 testers)
**Internal testers** are members of your Apple Developer team and can test immediately without Apple review.

1. **Add Internal Testers**:
   - Click **Internal Testing** in the sidebar
   - Click the **+** button next to "Testers and Groups"
   - Add individual testers by email or create tester groups
   - Select your build and click **Save**

2. **Send Invitations**:
   - Internal testers receive email invitations automatically
   - They can install TestFlight app and accept the invitation
   - **No Apple review required** - instant access

#### Step 3: External Testing (Up to 10,000 testers)
**External testers** are not part of your development team and require Apple review.

1. **Create External Testing Group**:
   - Click **External Testing** in the sidebar
   - Click **Create Group** and name it (e.g., "Beta Testers")
   - Add build information and testing notes

2. **Add External Testers**:
   - Click **Add Testers** in your group
   - Add testers by email address or import from CSV
   - Set maximum number of testers for the group

3. **Submit for Review**:
   - Add **App Review Information**:
     - Demo account credentials (if app requires login)
     - Review notes explaining app functionality
     - Contact information for reviewer questions
   - Click **Submit for Review**
   - **Review time**: Usually 1-3 business days

4. **Distribute After Approval**:
   - Once approved, testers receive email invitations
   - Share the **public TestFlight link** for easy distribution

#### Step 4: Managing Test Information

**Required Information for External Testing**:
```
App Name: ExpenseTrackerTest
App Description: Personal finance tracker with AI-powered insights
What to Test: 
- Manual transaction entry and categorization
- Analytics dashboard and spending insights  
- AI-powered financial Q&A features
- Firebase authentication and data sync

Demo Account (if needed):
Email: demo@expensetracker.com
Password: DemoPass123

Feedback Instructions:
- Test core transaction management features
- Verify charts and analytics accuracy
- Try AI chat for financial questions
- Report any crashes or UI issues
```

#### Step 5: TestFlight Distribution Links

**Internal Link**: Sent via email to internal testers
**External Public Link**: `https://testflight.apple.com/join/[PUBLIC_LINK_CODE]`

#### Step 6: Monitoring and Feedback

1. **View Test Metrics**:
   - Install rates and active testers
   - Crash reports and feedback
   - App usage analytics

2. **Collect Feedback**:
   - Testers can provide feedback directly in TestFlight
   - Screenshot feedback with annotations
   - Crash logs automatically collected

#### Build Artifacts and Expo Integration

**EAS Build automatically**:
- ✅ Compiles your React Native app for iOS
- ✅ Signs the app with your Apple Developer certificates
- ✅ Uploads the `.ipa` file to Expo's build servers
- ✅ Provides download links and build logs
- ✅ Optionally auto-submits to TestFlight (when configured)

**Build Artifacts Storage**:
- All builds are stored on Expo's servers for 30 days
- Download `.ipa` files from the EAS Build dashboard
- Access build logs and metadata
- Share direct download links with your team

**Quick Commands Summary**:
```bash
# Build iOS app (uploads to Expo automatically)
npm run build:ios

# Build production iOS for TestFlight
npm run build:prod:ios

# Submit to TestFlight after build
npm run submit:ios

# Build and submit in one command
npm run deploy:ios
```

You have reached the end of the file.
```
