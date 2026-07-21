// Strip common mistake: parameter value "OPENROUTER_CREDENTIALS_ID = OPENROUTER_API_KEY" (Jenkins would look up that full string as credential ID).
def normalizeOpenRouterCredsId = { Object raw ->
    if (raw == null) {
        return ''
    }
    def s = raw.toString().trim()
    if (!s) {
        return ''
    }
    if (s.contains('=')) {
        def parts = s.split('=', 2)
        if (parts.length == 2) {
            s = parts[1].trim()
        }
    }
    s = s.replaceAll('(?i)^OPENROUTER_CREDENTIALS_ID\\s*', '').trim()
    return s
}

// Bind Jenkins Secret text → OPENROUTER_API_KEY for Python / Maestro (optional).
def withOpenRouterCredentials = { Object credsId, Closure action ->
    def id = normalizeOpenRouterCredsId(credsId)
    if (!id) {
        action()
        return
    }
    try {
        withCredentials([string(credentialsId: id, variable: 'OPENROUTER_API_KEY')]) {
            action()
        }
    } catch (hudson.AbortException ex) {
        // Do not confuse Maestro/ATP step failures with missing OpenRouter credentials.
        throw ex
    } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException ex) {
        throw ex
    } catch (Exception ex) {
        def msg = ex.message ?: ex.getClass().name
        if (msg.contains('Could not find credentials') || msg.toLowerCase().contains('credential') && msg.toLowerCase().contains('not found')) {
            echo "[WARN] OpenRouter credential '${id}' not found in Jenkins. Continuing without AI key: ${msg}"
            action()
        } else {
            throw ex
        }
    }
}

/**
 * ATP modules: stage name, Jenkins boolean param, folder for jenkins_atp_stage.py.
 * Kept as one list so Declarative stages stay small (avoids CPS MethodTooLargeException).
 */
def atpModuleDefs() {
    return [
        [n: 'Splash', p: 'RUN_ATP_SPLASH', f: 'splash'],
        [n: 'Onboarding', p: 'RUN_ATP_ONBOARDING', f: 'onboarding'],
        [n: 'SignUp', p: 'RUN_ATP_SIGNUP', f: 'signup'],
        [n: 'Login', p: 'RUN_ATP_LOGIN', f: 'login'],
        [n: 'SignUp_Later', p: 'RUN_ATP_SIGNUP_LATER', f: 'signup-later'],
        [n: 'Connection', p: 'RUN_ATP_CONNECTION', f: 'connection'],
        [n: 'Permission', p: 'RUN_ATP_PERMISSION', f: 'permission'],
        [n: 'Gallery', p: 'RUN_ATP_GALLERY', f: 'gallery'],
        [n: 'Quick_Print', p: 'RUN_ATP_QUICK_PRINT', f: 'quick-print'],
        [n: 'Collage', p: 'RUN_ATP_COLLAGE', f: 'collage'],
        [n: 'Home', p: 'RUN_ATP_HOME', f: 'home'],
        [n: 'Camera', p: 'RUN_ATP_CAMERA', f: 'camera'],
        [n: 'Editor', p: 'RUN_ATP_EDITOR', f: 'editor'],
        [n: 'Printing', p: 'RUN_ATP_PRINTING', f: 'printing'],
        [n: 'PreCut', p: 'RUN_ATP_PRECUT', f: 'precut'],
        [n: 'Video', p: 'RUN_ATP_VIDEO', f: 'video'],
        [n: 'Tile Print', p: 'RUN_ATP_TILE_PRINT', f: 'tile-print'],
        [n: 'Settings', p: 'RUN_ATP_SETTINGS', f: 'settings'],
        [n: 'Firmware', p: 'RUN_ATP_FIRMWARE', f: 'firmware'],
        [n: 'AI', p: 'RUN_ATP_AI', f: 'ai'],
        [n: 'Alerts', p: 'RUN_ATP_ALERTS', f: 'alerts'],
        [n: 'General', p: 'RUN_ATP_GENERAL', f: 'general'],
        [n: 'Photo ID', p: 'RUN_ATP_PHOTO_ID', f: 'photo-id'],
        [n: 'Photobooth', p: 'RUN_ATP_PHOTOBOOTH', f: 'photobooth'],
        [n: 'Custom SDK', p: 'RUN_ATP_CUSTOM_SDK', f: 'custom-sdk'],
        [n: 'Onboarding Splash', p: 'RUN_ATP_ONBOARDING_SPLASH', f: 'onboarding-splash'],
    ]
}

/** True when any ATP TestCase Flows module checkbox is enabled. */
def anyAtpModuleEnabled = {
    for (def m in atpModuleDefs()) {
        if (params[m.p]) {
            return true
        }
    }
    return false
}

/** Suite ids for finalize flag checks (must match jenkins_atp_stage.py folder_to_suite_id). */
def atpSuiteIdsList = {
    def ids = []
    for (def m in atpModuleDefs()) {
        ids << ('atp_' + m.f.replaceAll('[^a-zA-Z0-9]+', '_').toLowerCase())
    }
    return ids
}

/**
 * First existing directory/file path on the CURRENT agent.
 * Skips stale job params from another machine (e.g. C:\Users\HP\... on a different PC).
 */
def firstExistingPath(List candidates) {
    for (def raw in candidates) {
        if (raw == null) {
            continue
        }
        def p = raw.toString().trim()
        if (!p) {
            continue
        }
        if (fileExists(p)) {
            return p
        }
    }
    return ''
}

/**
 * Shared Maestro/Java/ADB env — portable across Windows agents.
 * Prefer non-empty job params only when that path exists on this machine; else agent env / per-user defaults.
 */
def maestroEnvList() {
    def up = env.USERPROFILE ?: ''
    def la = env.LOCALAPPDATA ?: (up ? "${up}\\AppData\\Local" : '')
    def envList = []

    def javaHome = firstExistingPath([
        params.JAVA_HOME_OVERRIDE,
        env.MAESTRO_JAVA_HOME,
        env.JAVA_HOME,
        up ? "${up}\\.jdks\\jbr-17.0.8" : '',
        up ? "${up}\\.jdks\\jbr-17.0.14" : '',
        up ? "${up}\\.jdks\\jbr-21.0.2" : '',
        'C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.8-hotspot',
        'C:\\Program Files\\Microsoft\\jdk-17.0.8.7-hotspot',
        'C:\\Program Files\\Java\\jdk-17',
    ])
    if (javaHome) {
        envList << "MAESTRO_JAVA_HOME=${javaHome}"
        envList << "JAVA_HOME=${javaHome}"
        envList << "PATH+JAVA=${javaHome}\\bin"
    }

    def maestroHome = firstExistingPath([
        params.MAESTRO_HOME,
        env.MAESTRO_HOME,
        up ? "${up}\\maestro\\maestro\\bin" : '',
        up ? "${up}\\maestro\\bin" : '',
        'C:\\maestro\\maestro\\bin',
    ])
    if (maestroHome) {
        envList << "MAESTRO_HOME=${maestroHome}"
        envList << "PATH+MAESTRO=${maestroHome}"
    }

    def androidHome = firstExistingPath([
        params.ANDROID_HOME,
        env.ANDROID_HOME,
        env.ANDROID_SDK_ROOT,
        la ? "${la}\\Android\\Sdk" : '',
        up ? "${up}\\AppData\\Local\\Android\\Sdk" : '',
    ])
    if (androidHome) {
        envList << "ANDROID_HOME=${androidHome}"
        envList << "ANDROID_SDK_ROOT=${androidHome}"
        envList << "ADB_HOME=${androidHome}\\platform-tools"
        envList << "PATH+ADB=${androidHome}\\platform-tools"
    }

    echo "[maestroEnvList] JAVA_HOME=${javaHome ?: '(agent default)'} MAESTRO_HOME=${maestroHome ?: '(agent default)'} ANDROID_HOME=${androidHome ?: '(agent default)'}"
    return envList
}

pipeline {
    agent none

    parameters {
        string(
            name: 'DEVICES_AGENT',
            defaultValue: 'devices',
            description: 'Jenkins agent LABEL for the USB-phone machine (examples: devices, my-pc-devices). Set to the label of whichever PC is running this build.'
        )
        string(name: 'APP_PACKAGE', defaultValue: 'com.hp.impulse.sprocket', description: 'App package id for Maestro/app launch checks')
        string(name: 'MAESTRO_CMD', defaultValue: 'maestro.bat', description: 'Maestro launcher (e.g. maestro.bat).')
        string(name: 'MAESTRO_HOME', defaultValue: '', description: 'Optional. Folder with maestro.bat. Leave empty to auto-detect on the agent (%%USERPROFILE%%\\maestro\\... or PATH). Stale paths from another PC are ignored.')
        string(name: 'ANDROID_HOME', defaultValue: '', description: 'Optional. Android SDK root. Leave empty to use agent ANDROID_HOME or %%LOCALAPPDATA%%\\Android\\Sdk.')
        string(name: 'JAVA_HOME_OVERRIDE', defaultValue: '', description: 'Optional. JDK for Maestro. Leave empty to use agent JAVA_HOME or %%USERPROFILE%%\\.jdks\\jbr-*.')
        booleanParam(name: 'RUN_ATP_SPLASH', defaultValue: true, description: 'ATP TestCase Flows/splash')
        booleanParam(name: 'RUN_ATP_ONBOARDING', defaultValue: true, description: 'ATP TestCase Flows/onboarding')
        booleanParam(name: 'RUN_ATP_SIGNUP', defaultValue: true, description: 'ATP TestCase Flows/signup')
        booleanParam(name: 'RUN_ATP_LOGIN', defaultValue: true, description: 'ATP TestCase Flows/login')
        booleanParam(name: 'RUN_ATP_SIGNUP_LATER', defaultValue: true, description: 'ATP TestCase Flows/signup-later')
        booleanParam(name: 'RUN_ATP_CONNECTION', defaultValue: false, description: 'ATP TestCase Flows/connection')
        booleanParam(name: 'RUN_ATP_PERMISSION', defaultValue: false, description: 'ATP TestCase Flows/permission')
        booleanParam(name: 'RUN_ATP_GALLERY', defaultValue: false, description: 'ATP TestCase Flows/gallery')
        booleanParam(name: 'RUN_ATP_QUICK_PRINT', defaultValue: false, description: 'ATP TestCase Flows/quick-print')
        booleanParam(name: 'RUN_ATP_COLLAGE', defaultValue: false, description: 'ATP TestCase Flows/collage')
        booleanParam(name: 'RUN_ATP_HOME', defaultValue: false, description: 'ATP TestCase Flows/home')
        booleanParam(name: 'RUN_ATP_CAMERA', defaultValue: false, description: 'ATP TestCase Flows/camera')
        booleanParam(name: 'RUN_ATP_EDITOR', defaultValue: false, description: 'ATP TestCase Flows/editor')
        booleanParam(name: 'RUN_ATP_PRINTING', defaultValue: false, description: 'ATP TestCase Flows/printing')
        booleanParam(name: 'RUN_ATP_PRECUT', defaultValue: false, description: 'ATP TestCase Flows/precut')
        booleanParam(name: 'RUN_ATP_VIDEO', defaultValue: false, description: 'ATP TestCase Flows/video')
        booleanParam(name: 'RUN_ATP_TILE_PRINT', defaultValue: false, description: 'ATP TestCase Flows/tile-print')
        booleanParam(name: 'RUN_ATP_SETTINGS', defaultValue: false, description: 'ATP TestCase Flows/settings')
        booleanParam(name: 'RUN_ATP_FIRMWARE', defaultValue: false, description: 'ATP TestCase Flows/firmware')
        booleanParam(name: 'RUN_ATP_AI', defaultValue: false, description: 'ATP TestCase Flows/ai')
        booleanParam(name: 'RUN_ATP_ALERTS', defaultValue: false, description: 'ATP TestCase Flows/alerts')
        booleanParam(name: 'RUN_ATP_GENERAL', defaultValue: false, description: 'ATP TestCase Flows/general')
        booleanParam(name: 'RUN_ATP_PHOTO_ID', defaultValue: false, description: 'ATP TestCase Flows/photo-id')
        booleanParam(name: 'RUN_ATP_PHOTOBOOTH', defaultValue: false, description: 'ATP TestCase Flows/photobooth')
        booleanParam(name: 'RUN_ATP_CUSTOM_SDK', defaultValue: false, description: 'ATP TestCase Flows/custom-sdk')
        booleanParam(name: 'RUN_ATP_ONBOARDING_SPLASH', defaultValue: false, description: 'ATP TestCase Flows/onboarding-splash (Excel ONBOARDING SPLASH SCREEN)')
        booleanParam(name: 'RUN_AI_ANALYSIS', defaultValue: true, description: 'Test OpenRouter + run intelligent_platform failure analysis')
        booleanParam(name: 'SEND_FINAL_EMAIL', defaultValue: false, description: 'Send final summary email')
        booleanParam(name: 'CLEAR_STATE', defaultValue: true, description: 'Clear app state in suite runners')
        booleanParam(name: 'RETRY_FAILED', defaultValue: false, description: 'Reserved for future retry logic')
        string(
            name: 'OPENROUTER_CREDENTIALS_ID',
            defaultValue: 'OPENROUTER_API_KEY',
            description: 'Jenkins "Secret text" credential ID only (e.g. OPENROUTER_API_KEY). Injects as OPENROUTER_API_KEY. Do not paste the whole parameter line. Leave empty to use env already set on the agent.'
        )
    }

    options {
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        // Keep stash copies low: full repo stashes are large; excludes shrink controller disk use.
        preserveStashes(buildCount: 2)
        buildDiscarder(
            logRotator(
                numToKeepStr: '10',
                // Fewer archived copies of execution_logs.zip / screenshots / Excel on Jenkins home disk.
                artifactNumToKeepStr: '3',
            )
        )
        timeout(time: 180, unit: 'MINUTES')
    }

    triggers {
        cron('H 9 * * *')
        githubPush()
    }

    stages {
        stage('Fetch Code from GitHub') {
            agent { label 'built-in' }
            steps {
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    deleteDir()
                    checkout scm
                    // Stash sources only: exclude .git, deps, workspace screenshots (.maestro), generated dirs (docs/disk_cleanup_guide.md).
                    stash name: 'repo', includes: '**/*', excludes: '**/.git/**,**/node_modules/**,**/.maestro/**,**/reports/**,**/build-summary/**,**/status/**,**/logs/**,**/collected-artifacts/**,**/test-results/**,**/maestro-report/**,**/*.zip', useDefaultExcludes: false
                }
            }
        }

        stage('Install Dependencies') {
            agent { label params.DEVICES_AGENT }
            steps {
                // Windows locks (Maestro/ADB/AV): wipe best-effort; never hard-fail before unstash.
                // Keep this block tiny — large inline bat caused CPS MethodTooLargeException.
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    powershell '''
$ws = $env:WORKSPACE
if (-not (Test-Path $ws)) { exit 0 }
Get-Process maestro,adb -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
cmd /c "attrib -R -S -H `"$ws\\*.*`" /S /D" | Out-Null
$empty = Join-Path $env:TEMP ("jenkins_empty_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $empty -Force | Out-Null
cmd /c "robocopy `"$empty`" `"$ws`" /MIR /R:2 /W:2 /NFL /NDL /NJH /NJS /NC /NS >nul"
Remove-Item $empty -Force -ErrorAction SilentlyContinue
Get-ChildItem $ws -Force -ErrorAction SilentlyContinue | ForEach-Object {
  Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}
exit 0
'''
                }
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    deleteDir()
                }
                unstash 'repo'
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    bat """call scripts\\resolve_windows_tools.bat "${params.JAVA_HOME_OVERRIDE}" "${params.MAESTRO_HOME}" "${params.ANDROID_HOME}" "${env.WORKSPACE}" """
                }
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    bat """call scripts\\jenkins_ci_install.bat "${env.WORKSPACE}" """
                }
            }
        }

        stage('Environment Precheck') {
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    script {
                        withEnv(maestroEnvList()) {
                            bat """call scripts\\jenkins_ci_precheck.bat "${env.WORKSPACE}" "${params.MAESTRO_CMD}" "${params.APP_PACKAGE}" """
                        }
                    }
                }
            }
        }

        stage('Detect Connected Devices') {
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    script {
                        withEnv(maestroEnvList()) {
                            bat """call scripts\\jenkins_ci_devices.bat "${env.WORKSPACE}" """
                        }
                    }
                }
            }
        }

        // One declarative stage + nested stages keeps CPS bytecode under the 64KB method limit.
        stage('ATP Modules') {
            when { expression { return anyAtpModuleEnabled() } }
            agent { label params.DEVICES_AGENT }
            steps {
                script {
                    for (def m in atpModuleDefs()) {
                        if (!params[m.p]) {
                            continue
                        }
                        stage(m.n) {
                            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                                withEnv(maestroEnvList()) {
                                    bat """cd /d "${env.WORKSPACE}" && python scripts/jenkins_atp_stage.py all ${m.f} "${params.APP_PACKAGE}" "${params.CLEAR_STATE.toString()}" "${params.MAESTRO_CMD}" """
                                }
                            }
                        }
                    }
                }
            }
        }

        stage('Test AI Connection') {
            when { expression { return params.RUN_AI_ANALYSIS } }
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    script {
                        withOpenRouterCredentials(params.OPENROUTER_CREDENTIALS_ID) {
                            bat """call scripts\\jenkins_ci_ai_probe.bat "${env.WORKSPACE}" """
                        }
                    }
                }
            }
        }

        stage('AI Failure Analysis + Smart Retry') {
            when { expression { return params.RUN_AI_ANALYSIS } }
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    script {
                        withOpenRouterCredentials(params.OPENROUTER_CREDENTIALS_ID) {
                            bat """call scripts\\jenkins_ci_ai_analysis.bat "${env.WORKSPACE}" """
                        }
                    }
                }
            }
        }

        stage('Build Summary') {
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    bat """call scripts\\jenkins_ci_build_summary.bat "${env.WORKSPACE}" """
                }
            }
        }

        stage('Materialize execution_logs.zip for archive and email') {
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    bat """call scripts\\jenkins_ci_zip_logs.bat "${env.WORKSPACE}" """
                }
            }
        }

        // mailout/send_email.py — user/pass from Jenkins credential "gmail-smtp-kodak" (Gmail + App Password). No secrets in this file.
        stage('Send Final Email') {
            when { expression { return params.SEND_FINAL_EMAIL } }
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    script {
                        withCredentials([usernamePassword(credentialsId: 'gmail-smtp-kodak', usernameVariable: 'B_SMTP_USER', passwordVariable: 'B_SMTP_PASS')]) {
                            withEnv([
                                'SMTP_SERVER=smtp.gmail.com',
                                'SMTP_HOST=smtp.gmail.com',
                                'SMTP_PORT=587',
                                "SMTP_USER=${env.B_SMTP_USER}",
                                "SMTP_PASS=${env.B_SMTP_PASS}",
                                "SENDER_EMAIL=${env.B_SMTP_USER}",
                                "RECEIVER_EMAIL=${env.B_SMTP_USER}",
                                "MAIL_TO=${env.B_SMTP_USER}",
                                'PYTHONIOENCODING=utf-8',
                                'ORCH_EMAIL_STRICT=1',
                                "FINAL_EXECUTION_REPORT_XLSX=${env.WORKSPACE}\\build-summary\\final_execution_report.xlsx",
                                "BRANCH_NAME=${env.BRANCH_NAME}",
                                "GIT_BRANCH=${env.BRANCH_NAME}",
                            ]) {
                                bat """call scripts\\jenkins_ci_send_email.bat "${env.WORKSPACE}" """
                            }
                        }
                    }
                }
            }
        }

        stage('Archive Reports & Artifacts') {
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    archiveArtifacts artifacts: 'build-summary/final_execution_report.xlsx, build-summary/execution_logs.zip, .maestro/screenshots/**, detected_devices.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Finalize Build Result') {
            agent { label params.DEVICES_AGENT }
            steps {
                script {
                    def atpSuiteIds = atpSuiteIdsList()
                    def atpFlags = []
                    atpSuiteIds.each { s ->
                        atpFlags.add("${s}_failed.flag")
                        atpFlags.add("${s}_no_results.flag")
                        atpFlags.add("${s}_report_failed.flag")
                    }
                    def unstableFlags = [
                        'atp_report_failed.flag',
                        'summary_failed.flag', 'ai_failed.flag', 'email_failed.flag', 'pipeline_failed.flag',
                    ] + atpFlags
                    def u = false
                    unstableFlags.each { f -> if (fileExists(f)) { u = true } }
                    if (fileExists('install_failed.flag') || fileExists('precheck_failed.flag') || fileExists('device_detection_failed.flag')) {
                        currentBuild.result = 'FAILURE'
                    } else if (u) {
                        currentBuild.result = 'UNSTABLE'
                    } else {
                        currentBuild.result = 'SUCCESS'
                    }
                }
            }
        }

        // Runs after archiveArtifacts: frees agent workspace only (Jenkins archived builds unchanged).
        stage('Post-build workspace cleanup (C: agent disk)') {
            agent { label params.DEVICES_AGENT }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    bat """call scripts\\jenkins_ci_cleanup_post.bat "${env.WORKSPACE}" """
                }
            }
        }
    }

    post {
        always { echo "Build: ${currentBuild.currentResult}" }
    }
}
