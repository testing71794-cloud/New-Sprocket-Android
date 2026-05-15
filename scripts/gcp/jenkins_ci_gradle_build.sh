#!/usr/bin/env bash
# Placeholder for Android app Gradle build on GCP (external app repository).
# This Maestro flow repo does not contain Gradle sources.
#
# Usage (example, in Jenkins hybrid pipeline):
#   export APP_REPO_URL=...
#   export APP_REPO_BRANCH=main
#   bash scripts/gcp/jenkins_ci_gradle_build.sh /path/to/checkout
#
# After build, stash APK:
#   stash name: 'app-apk', includes: '**/outputs/**/*.apk'
#
set -euo pipefail
echo "[gcp-gradle] ERROR: Gradle build not configured in this repository."
echo "[gcp-gradle] Point Jenkins to your Android app repo and invoke gradlew there."
echo "[gcp-gradle] See docs/DISTRIBUTED_GCP_WINDOWS_ARCHITECTURE.md"
exit 2
