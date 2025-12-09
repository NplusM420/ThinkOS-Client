#!/usr/bin/env node

/**
 * Sync version from app/package.json to:
 * - backend/pyproject.toml
 * - extension/public/manifest.json
 *
 * Run this after changesets updates the JS package versions.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

function getAppVersion() {
  const appPkg = JSON.parse(
    fs.readFileSync(path.join(ROOT, 'app', 'package.json'), 'utf8')
  );
  return appPkg.version;
}

function updatePyproject(version) {
  const pyprojectPath = path.join(ROOT, 'backend', 'pyproject.toml');
  let content = fs.readFileSync(pyprojectPath, 'utf8');

  const updated = content.replace(
    /^version\s*=\s*"[^"]+"/m,
    `version = "${version}"`
  );

  if (updated !== content) {
    fs.writeFileSync(pyprojectPath, updated);
    console.log(`Updated backend/pyproject.toml to version ${version}`);
    return true;
  }
  return false;
}

function updateManifest(version) {
  const manifestPath = path.join(ROOT, 'extension', 'public', 'manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

  if (manifest.version !== version) {
    manifest.version = version;
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
    console.log(`Updated extension/public/manifest.json to version ${version}`);
    return true;
  }
  return false;
}

function main() {
  const version = getAppVersion();
  console.log(`Syncing version ${version} across all packages...`);

  const pyprojectUpdated = updatePyproject(version);
  const manifestUpdated = updateManifest(version);

  if (pyprojectUpdated || manifestUpdated) {
    console.log('Version sync complete.');
  } else {
    console.log('All versions already in sync.');
  }
}

main();
