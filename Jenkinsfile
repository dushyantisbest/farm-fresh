pipeline {
    agent any
    options { disableConcurrentBuilds() }
    triggers { pollSCM('H/5 * * * *') }
    stages {
        stage('Checkout') { steps { checkout scm } }
        stage('Build') { steps {
            bat 'python --version'
            bat 'python -m venv .venv'
            bat '.venv\\Scripts\\python -m pip install -r requirements-ci.txt bandit pip-audit'
            bat 'if not exist reports mkdir reports'
            bat 'del /q reports\\*.json reports\\*.xml 2>nul & exit /b 0'
        } }
        stage('Automated Testing') { steps {
            bat '.venv\\Scripts\\python -m pytest tests/ --junitxml=reports/tests.xml'
        } }
        stage('Static analysis') { steps {
            bat '.venv\\Scripts\\python tools/evaluate.py static'
            bat '.venv\\Scripts\\python -m bandit -ll app.py inventory.py forecast.py -f json -o reports/bandit.json'
        } }
        stage('Dependency audit') { steps {
            bat '.venv\\Scripts\\python tools/evaluate.py dependencies'
            bat '.venv\\Scripts\\python -m pip_audit -r requirements-ci.txt -f json -o reports/pip-audit.json'
            bat '.venv\\Scripts\\python tools/check_sqlite.py'
        } }
        stage('Secret detection') { steps {
            bat 'gitleaks dir . --redact --report-format json --report-path reports/gitleaks.json'
        } }
        stage('Performance evaluation') { steps {
            bat '.venv\\Scripts\\python tools/evaluate.py benchmark'
        } }
        stage('Docker Build') { steps {
            bat 'docker --version'
            bat 'docker build -t inventory-app:%BUILD_NUMBER% .'
        } }
        stage('Image vulnerability scan') { steps {
            bat 'trivy image --scanners vuln --severity HIGH,CRITICAL --exit-code 1 --format json --output reports/trivy.json inventory-app:%BUILD_NUMBER%'
            bat 'docker tag inventory-app:%BUILD_NUMBER% inventory-app:latest'
        } }
        stage('Deploy to local staging') { steps {
            withEnv(["IMAGE_TAG=${env.BUILD_NUMBER}"]) {
                bat 'docker compose -p fieldstock-staging up -d --wait --wait-timeout 90'
                bat 'powershell -NoProfile -Command "$r = Invoke-RestMethod http://127.0.0.1:8088/api/dashboard; if (-not $r.planning.plans.Diwali) {exit 1}"'
            }
        } }
    }
    post {
        always { archiveArtifacts artifacts: 'reports/*.json,reports/*.xml', allowEmptyArchive: true }
        success { echo 'Pipeline Successful!' }
        failure { echo 'Pipeline Failed! Check Console Output and archived reports.' }
    }
}
