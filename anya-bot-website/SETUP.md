# 🚀 Firebase Setup Guide for Anya Bot Website

## Prerequisites

- Node.js 18+ installed
- Firebase CLI installed globally
- Firebase project created (ID: `anya-bot-1fe76`)

## Step-by-Step Setup

### 1. Install Dependencies

```bash
cd character-hosting
npm install
```

### 2. Install Firebase CLI (if not already installed)

```bash
npm install -g firebase-tools
```

### 3. Login to Firebase

```bash
firebase login
```

This will open a browser window for you to authenticate with your Google account.

### 4. Verify Project Configuration

The project is already configured for `anya-bot-1fe76`. Verify with:

```bash
firebase projects:list
```

You should see `anya-bot-1fe76` in the list.

### 5. Initialize Firebase (if needed)

If you need to reinitialize:

```bash
firebase init
```

Select:
- ✅ Hosting
- ✅ Firestore
- ✅ Storage

When prompted:
- **Public directory**: `dist`
- **Configure as single-page app**: `Yes`
- **Set up automatic builds**: `No`
- **Overwrite index.html**: `No`

### 6. Set Environment Variables

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your Firebase config:

```env
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=anya-bot-1fe76.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=anya-bot-1fe76
VITE_FIREBASE_STORAGE_BUCKET=anya-bot-1fe76.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
```

Get these values from:
Firebase Console → Project Settings → General → Your apps → Web app

### 7. Deploy Firestore Rules

```bash
firebase deploy --only firestore:rules
```

### 8. Deploy Storage Rules

```bash
firebase deploy --only storage:rules
```

### 9. Build the Website

```bash
npm run build
```

This creates optimized production files in the `dist/` folder.

### 10. Deploy to Firebase Hosting

```bash
firebase deploy --only hosting
```

Or deploy everything at once:

```bash
npm run deploy
```

### 11. View Your Website

After deployment, your site will be available at:
- **Live URL**: `https://anya-bot-1fe76.web.app`
- **Alternative**: `https://anya-bot-1fe76.firebaseapp.com`

## 🔧 Development Commands

### Local Development

```bash
npm run dev
```

Opens at `http://localhost:3000`

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

### Parse Bot Commands

```bash
npm run parse-cogs
```

Extracts commands from Python cogs in `../bot/cogs/`

## 🐛 Troubleshooting

### Error: "Permission denied"

```bash
firebase login --reauth
```

### Error: "Project not found"

Verify project ID:

```bash
firebase use anya-bot-1fe76
```

### Error: "Build failed"

Clear cache and rebuild:

```bash
rm -rf node_modules dist
npm install
npm run build
```

### Error: "Firebase rules deployment failed"

Check syntax:

```bash
firebase deploy --only firestore:rules --debug
```

### Port 3000 already in use

Change port in `vite.config.ts`:

```typescript
server: {
  port: 3001,  // Change to any available port
}
```

## 📊 Firebase Console

Access your Firebase console:
https://console.firebase.google.com/project/anya-bot-1fe76

### Useful Console Sections

- **Hosting**: View deployments and rollback if needed
- **Firestore**: View/edit database
- **Storage**: Manage uploaded images
- **Analytics**: Track website usage
- **Performance**: Monitor load times

## 🔄 Continuous Deployment

### GitHub Actions (Optional)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Firebase

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run build
      - uses: FirebaseExtended/action-hosting-deploy@v0
        with:
          repoToken: '${{ secrets.GITHUB_TOKEN }}'
          firebaseServiceAccount: '${{ secrets.FIREBASE_SERVICE_ACCOUNT }}'
          projectId: anya-bot-1fe76
```

## 📝 Post-Deployment Checklist

- [ ] Website loads at production URL
- [ ] All images display correctly
- [ ] Command showcase works
- [ ] Navigation functions properly
- [ ] Mobile responsive
- [ ] Error boundaries catch errors
- [ ] Firebase rules are secure
- [ ] Environment variables set correctly

## 🆘 Need Help?

- Firebase Docs: https://firebase.google.com/docs
- Vite Docs: https://vitejs.dev
- React Docs: https://react.dev

## 🎉 Success!

Your Anya Bot website is now live at:
**https://anya-bot-1fe76.web.app**

Share it with your community! 🚀
