# Building for Distribution

## Prerequisites

You need an [Apple Developer Program](https://developer.apple.com/programs/) membership ($99/year) and a Developer ID certificate.

### Setting up your Developer ID Certificate

1. Open **Keychain Access** → Certificate Assistant → Request a Certificate From a Certificate Authority
2. Enter your email, select "Saved to disk", click Continue
3. Go to [Apple Developer Portal](https://developer.apple.com/account/resources/certificates/add)
4. Select **Developer ID Application**, upload your CSR
5. Download the certificate and double-click to install
6. Download the [Developer ID - G2 intermediate cert](https://www.apple.com/certificateauthority/) and install it
7. Verify: `security find-identity -v -p codesigning`

## Development Build

Fast builds for internal testing. Signed but not notarized—recipients need to right-click → Open on first launch.

```bash
pnpm build:all
```

## Release Build

For external distribution. Signed and notarized—opens without warnings.

1. Copy `.env.example` to `.env.local`
2. Fill in your credentials:
   - `CODESIGN_IDENTITY` - From `security find-identity -v -p codesigning`
   - `APPLE_ID` - Your Apple Developer email
   - `APPLE_APP_SPECIFIC_PASSWORD` - Generate at [appleid.apple.com](https://appleid.apple.com/account/manage) → Security → App-Specific Passwords
   - `APPLE_TEAM_ID` - Your 10-character Team ID

3. Build:
   ```bash
   pnpm build:all:release
   ```

Output: `app/release/Think-{version}.dmg`
