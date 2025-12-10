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

## CI/CD Release (GitHub Actions)

Releases are built automatically when a version tag is pushed.

### Required GitHub Secrets

Configure these in **Repository Settings → Secrets → Actions**:

| Secret | Description |
|--------|-------------|
| `MACOS_CERTIFICATE` | Base64-encoded Developer ID Application .p12 certificate |
| `MACOS_CERTIFICATE_PWD` | Password for the .p12 file |
| `APPLE_ID` | Apple Developer account email |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password for notarization |
| `APPLE_TEAM_ID` | 10-character Team ID from developer.apple.com |
| `CODESIGN_IDENTITY` | Full signing identity (e.g., `Developer ID Application: Name (TEAMID)`) |

### Setting Up the Certificate Secret

1. Export your Developer ID Application certificate from Keychain Access as a .p12 file
2. Base64 encode it:
   ```bash
   base64 -i certificate.p12 | pbcopy
   ```
3. Paste as `MACOS_CERTIFICATE` secret

### How It Works

1. Merge a "Version Packages" PR (created by Changesets)
2. The changeset workflow creates a version tag (e.g., `v0.2.0`)
3. The release workflow builds:
   - Chrome extension (ZIP)
   - macOS app (DMG, signed + notarized)
4. Artifacts are uploaded to a **draft** GitHub Release
5. Review and publish the release manually
