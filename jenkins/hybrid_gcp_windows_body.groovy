// Loaded by Jenkinsfile.hybrid.gcp-windows (separate Groovy class → avoids MethodTooLarge on WorkflowScript).
// Hybrid: GCP orchestrator + Windows USB Maestro. See docs/DISTRIBUTED_GCP_WINDOWS_ARCHITECTURE.md

def runHybrid() {
    // Job parameters are set in Jenkinsfile.hybrid.gcp-windows (do not call properties() here —
    // mid-run properties() can leave Blue Ocean stuck on "Waiting for run to start").
    timeout(time: 180, unit: 'MINUTES') {
        stageFetch()
        stageInstallGcp()
        stageInstallWindows()
        stagePrecheck()
        stageDetectDevices()
        stageAtpModules()
        stageAiProbe()
        stageAiAnalysis()
        stageStashOutputs()
        stageGcpPost()
        stageEmail()
        stageArchive()
        stageFinalize()
        stageCleanup()
    }
}

def p(String name, String fallback = '') {
    try {
        def v = params[name]
        if (v == null) {
            return fallback
        }
        def s = v.toString().trim()
        return s ?: fallback
    } catch (Throwable t) {
        return fallback
    }
}

/**
 * Run sh/Linux stages on the controller only — never on Windows USB agents.
 * Unlabeled node{} can schedule on 'devices' and then fail with CreateProcess "sh".
 */
def withOrch(Closure body) {
    def label = p('GCP_ORCHESTRATOR_AGENT', '')
    if (!label || label.equalsIgnoreCase('any') || label.equalsIgnoreCase('master')) {
        label = 'built-in'
    }
    echo "[orch] waiting for Linux/controller label=${label}"
    node(label) {
        echo "[orch] NODE_NAME=${env.NODE_NAME} isUnix=${isUnix()}"
        if (!isUnix()) {
            error "[orch] Node ${env.NODE_NAME} is Windows; GCP stages need Linux (label built-in). Set GCP_ORCHESTRATOR_AGENT=built-in and ensure the controller has a free executor."
        }
        body()
    }
}

def withDevices(Closure body) {
    def label = p('DEVICES_AGENT', 'devices')
    echo "[devices] waiting for Windows agent label=${label}"
    node(label) {
        echo "[devices] NODE_NAME=${env.NODE_NAME}"
        if (isUnix()) {
            error "[devices] Node ${env.NODE_NAME} is Unix; device stages need the Windows USB agent label (${label})."
        }
        body()
    }
}

def flag(String name) {
    try {
        def v = params[name]
        return v == true || v?.toString()?.equalsIgnoreCase('true')
    } catch (Throwable t) {
        return false
    }
}

/** Folders from RUN_ATP_* checkboxes, or ATP_MODULES override if that text is non-empty. */
def selectedAtpFolders() {
    def raw = p('ATP_MODULES', '')
    if (raw) {
        echo "[atp] using ATP_MODULES override: ${raw}"
        return raw.toLowerCase().split(/[,;\s]+/).findAll { it }
    }
    def legacy = [
        'RUN_ATP_SPLASH': 'splash',
        'RUN_ATP_ONBOARDING': 'onboarding',
        'RUN_ATP_SIGNUP': 'signup',
        'RUN_ATP_LOGIN': 'login',
        'RUN_ATP_SIGNUP_LATER': 'signup-later',
        'RUN_ATP_CONNECTION': 'connection',
        'RUN_ATP_PERMISSION': 'permission',
        'RUN_ATP_GALLERY': 'gallery',
        'RUN_ATP_QUICK_PRINT': 'quick-print',
        'RUN_ATP_COLLAGE': 'collage',
        'RUN_ATP_HOME': 'home',
        'RUN_ATP_CAMERA': 'camera',
        'RUN_ATP_EDITOR': 'editor',
        'RUN_ATP_PRINTING': 'printing',
        'RUN_ATP_PRECUT': 'precut',
        'RUN_ATP_VIDEO': 'video',
        'RUN_ATP_TILE_PRINT': 'tile-print',
        'RUN_ATP_SETTINGS': 'settings',
        'RUN_ATP_FIRMWARE': 'firmware',
        'RUN_ATP_AI': 'ai',
        'RUN_ATP_ALERTS': 'alerts',
        'RUN_ATP_GENERAL': 'general',
        'RUN_ATP_PHOTO_ID': 'photo-id',
        'RUN_ATP_PHOTOBOOTH': 'photobooth',
        'RUN_ATP_CUSTOM_SDK': 'custom-sdk',
        'RUN_ATP_ONBOARDING_SPLASH': 'onboarding-splash',
    ]
    def out = []
    legacy.each { k, folder ->
        if (flag(k)) {
            out << folder
        }
    }
    echo "[atp] selected via RUN_ATP_* checkboxes: ${out}"
    return out
}

def suiteIdForFolder(String folder) {
    def t = folder.replaceAll(/[^a-zA-Z0-9]+/, '_').replaceAll(/^_+|_+$/, '').toLowerCase()
    return t ? "atp_${t}" : 'atp_unknown'
}

def firstExisting(List candidates) {
    for (def raw in candidates) {
        if (raw == null) {
            continue
        }
        def path = raw.toString().trim()
        if (path && fileExists(path)) {
            return path
        }
    }
    return ''
}

def maestroEnvList() {
    def up = env.USERPROFILE ?: ''
    def la = env.LOCALAPPDATA ?: (up ? "${up}\\AppData\\Local" : '')
    def envList = []
    def javaHome = firstExisting([
        p('JAVA_HOME_OVERRIDE'), env.MAESTRO_JAVA_HOME,
        'C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.19.10-hotspot',
        'C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.8-hotspot',
        up ? "${up}\\.jdks\\jbr-17.0.8" : '', up ? "${up}\\.jdks\\jbr-17.0.14" : '',
        'C:\\Program Files\\Eclipse Adoptium\\jdk-21.0.11.10-hotspot',
        'C:\\Program Files\\Java\\jdk-17',
        env.JAVA_HOME,
    ])
    if (javaHome) {
        envList << "MAESTRO_JAVA_HOME=${javaHome}"
        envList << "JAVA_HOME=${javaHome}"
        envList << "PATH+JAVA=${javaHome}\\bin"
    }
    def maestroHome = firstExisting([
        p('MAESTRO_HOME'), env.MAESTRO_HOME,
        up ? "${up}\\maestro\\maestro\\bin" : '', up ? "${up}\\maestro\\bin" : '',
        'C:\\maestro\\maestro\\bin',
        'C:\\Tools\\maestro-parallel\\bin',
    ])
    if (maestroHome) {
        envList << "MAESTRO_HOME=${maestroHome}"
        envList << "PATH+MAESTRO=${maestroHome}"
    }
    def androidHome = firstExisting([
        p('ANDROID_HOME'), env.ANDROID_HOME, env.ANDROID_SDK_ROOT,
        la ? "${la}\\Android\\Sdk" : '',
    ])
    if (androidHome) {
        envList << "ANDROID_HOME=${androidHome}"
        envList << "ANDROID_SDK_ROOT=${androidHome}"
        envList << "ADB_HOME=${androidHome}\\platform-tools"
        envList << "PATH+ADB=${androidHome}\\platform-tools"
    }
    echo "[maestroEnvList] JAVA=${javaHome ?: '-'} MAESTRO=${maestroHome ?: '-'} ANDROID=${androidHome ?: '-'}"
    return envList
}

def openRouterId() {
    def s = p('OPENROUTER_CREDENTIALS_ID', 'OPENROUTER_API_KEY')
    if (s.contains('=')) {
        s = s.split('=', 2)[1].trim()
    }
    return s.replaceAll('(?i)^OPENROUTER_CREDENTIALS_ID\\s*', '').trim()
}

def withOpenRouter(Closure action) {
    def id = openRouterId()
    if (!id) {
        action()
        return
    }
    try {
        withCredentials([string(credentialsId: id, variable: 'OPENROUTER_API_KEY')]) {
            action()
        }
    } catch (hudson.AbortException ex) {
        throw ex
    } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException ex) {
        throw ex
    } catch (Exception ex) {
        def msg = ex.message ?: ex.getClass().name
        if (msg.toLowerCase().contains('credential') && msg.toLowerCase().contains('not found')) {
            echo "[WARN] OpenRouter credential '${id}' missing; continuing without AI key"
            action()
        } else {
            throw ex
        }
    }
}

def stageFetch() {
    stage('Fetch Code from GitHub') {
        withOrch {
            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                deleteDir()
                checkout scm
                stash name: 'repo', includes: '**/*', excludes: '**/.git/**,**/node_modules/**,**/.maestro/**,**/reports/**,**/build-summary/**,**/status/**,**/logs/**,**/collected-artifacts/**,**/test-results/**,**/maestro-report/**,**/*.zip', useDefaultExcludes: false
            }
        }
    }
}

def stageInstallGcp() {
    stage('Install GCP orchestrator dependencies') {
        withOrch {
            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                unstash 'repo'
                sh """
                    chmod +x scripts/gcp/*.sh 2>/dev/null || true
                    bash scripts/gcp/jenkins_ci_install.sh "${env.WORKSPACE}"
                """
            }
        }
    }
}

def stageInstallWindows() {
    stage('Install Windows device dependencies (light)') {
        withDevices {
            // Do NOT call scripts\\jenkins_safe_wipe_workspace.bat here — leftover workspace
            // still has the OLD script (with timeout.exe) until after unstash.
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                bat '''
@echo off
setlocal EnableExtensions
set "WS=%WORKSPACE%"
echo [wipe-inline] workspace=%WS%
if not exist "%WS%" exit /b 0
taskkill /F /IM maestro.exe /T >nul 2>&1
taskkill /F /IM adb.exe /T >nul 2>&1
REM Never use timeout.exe under Jenkins (non-TTY aborts the whole bat with exit 1).
ping 127.0.0.1 -n 2 >nul 2>&1
attrib -R -S -H "%WS%\\*.*" /S /D >nul 2>&1
for /d %%D in ("%WS%\\*") do rmdir /s /q "%%~fD" >nul 2>&1
del /f /q "%WS%\\*" >nul 2>&1
echo [wipe-inline] done
exit /b 0
'''
            }
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                deleteDir()
            }
            unstash 'repo'
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                bat "call scripts\\resolve_windows_tools.bat \"${p('JAVA_HOME_OVERRIDE')}\" \"${p('MAESTRO_HOME')}\" \"${p('ANDROID_HOME')}\" \"${env.WORKSPACE}\" & exit /b 0"
            }
            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                bat "call scripts\\jenkins_ci_install_windows_device.bat \"${env.WORKSPACE}\""
            }
        }
    }
}

def stagePrecheck() {
    stage('Environment Precheck') {
        withDevices {
            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                withEnv(maestroEnvList()) {
                    bat "call scripts\\jenkins_ci_precheck.bat \"${env.WORKSPACE}\" \"${p('MAESTRO_CMD', 'maestro.bat')}\" \"${p('APP_PACKAGE', 'com.hp.impulse.sprocket')}\""
                }
            }
        }
    }
}

def stageDetectDevices() {
    stage('Detect Connected Devices') {
        withDevices {
            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                withEnv(maestroEnvList()) {
                    bat "call scripts\\jenkins_ci_devices.bat \"${env.WORKSPACE}\""
                }
            }
        }
    }
}

def stageAtpModules() {
    stage('ATP Modules') {
        def folders = selectedAtpFolders()
        if (!folders) {
            echo 'No ATP modules selected (ATP_MODULES empty and no legacy RUN_ATP_* flags).'
            return
        }
        withDevices {
            folders.each { folder ->
                stage(folder) {
                    catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                        withEnv(maestroEnvList()) {
                            bat "cd /d \"${env.WORKSPACE}\" && python scripts/jenkins_atp_stage.py all ${folder} \"${p('APP_PACKAGE', 'com.hp.impulse.sprocket')}\" \"${flag('CLEAR_STATE')}\" \"${p('MAESTRO_CMD', 'maestro.bat')}\""
                        }
                    }
                }
            }
        }
    }
}

def stageAiProbe() {
    stage('Test AI Connection') {
        if (!flag('RUN_AI_ANALYSIS')) {
            return
        }
        withDevices {
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                withOpenRouter {
                    bat "call scripts\\jenkins_ci_ai_probe.bat \"${env.WORKSPACE}\""
                }
            }
        }
    }
}

def stageAiAnalysis() {
    stage('AI Failure Analysis + Smart Retry') {
        if (!flag('RUN_AI_ANALYSIS')) {
            return
        }
        withDevices {
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                withOpenRouter {
                    bat "call scripts\\jenkins_ci_ai_analysis.bat \"${env.WORKSPACE}\""
                }
            }
        }
    }
}

def stageStashOutputs() {
    stage('Stash device run outputs for GCP post-processing') {
        withDevices {
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                stash name: 'run-outputs', includes: 'reports/**,status/**,build-summary/**,.maestro/**,detected_devices.txt,*.flag', allowEmpty: true
            }
        }
    }
}

def stageGcpPost() {
    stage('GCP post-processing (Excel, summary, zip)') {
        withOrch {
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                deleteDir()
                unstash 'repo'
                unstash 'run-outputs'
                sh """
                    chmod +x scripts/gcp/*.sh 2>/dev/null || true
                    bash scripts/gcp/jenkins_ci_post_reports.sh "${env.WORKSPACE}"
                """
            }
        }
    }
}

def stageEmail() {
    stage('Send Final Email') {
        if (!flag('SEND_FINAL_EMAIL')) {
            return
        }
        withOrch {
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
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
                        "FINAL_EXECUTION_REPORT_XLSX=${env.WORKSPACE}/build-summary/final_execution_report.xlsx",
                        "BRANCH_NAME=${env.BRANCH_NAME}",
                        "GIT_BRANCH=${env.BRANCH_NAME}",
                    ]) {
                        sh """
                            chmod +x scripts/gcp/*.sh 2>/dev/null || true
                            bash scripts/gcp/jenkins_ci_send_email.sh "${env.WORKSPACE}"
                        """
                    }
                }
            }
        }
    }
}

def stageArchive() {
    stage('Archive Reports & Artifacts') {
        withOrch {
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                archiveArtifacts artifacts: 'build-summary/final_execution_report.xlsx, build-summary/execution_logs.zip, .maestro/screenshots/**, detected_devices.txt', allowEmptyArchive: true
            }
        }
    }
}

def stageFinalize() {
    stage('Finalize Build Result') {
        withOrch {
            def unstable = false
            selectedAtpFolders().each { folder ->
                def sid = suiteIdForFolder(folder)
                ["${sid}_failed.flag", "${sid}_no_results.flag", "${sid}_report_failed.flag"].each { f ->
                    if (fileExists(f)) {
                        unstable = true
                    }
                }
            }
            ['atp_report_failed.flag', 'summary_failed.flag', 'ai_failed.flag', 'email_failed.flag', 'pipeline_failed.flag'].each { f ->
                if (fileExists(f)) {
                    unstable = true
                }
            }
            if (fileExists('install_failed.flag') || fileExists('precheck_failed.flag') || fileExists('device_detection_failed.flag')) {
                currentBuild.result = 'FAILURE'
            } else if (unstable) {
                currentBuild.result = 'UNSTABLE'
            } else {
                currentBuild.result = 'SUCCESS'
            }
            echo "Build: ${currentBuild.currentResult}"
        }
    }
}

def stageCleanup() {
    stage('Post-build workspace cleanup (C: agent disk)') {
        withDevices {
            catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                bat "call scripts\\jenkins_ci_cleanup_post.bat \"${env.WORKSPACE}\""
            }
        }
    }
}

return this
