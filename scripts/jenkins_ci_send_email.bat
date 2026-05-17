@echo off
setlocal EnableExtensions
cd /d "%~1"
if defined BRANCH_NAME if not defined ATP_GIT_BRANCH set "ATP_GIT_BRANCH=%BRANCH_NAME%"
if defined GIT_BRANCH if not defined ATP_GIT_BRANCH set "ATP_GIT_BRANCH=%GIT_BRANCH%"
echo Running send_email with Jenkins credential gmail-smtp-kodak ...
python mailout\send_email.py || (echo 1> email_failed.flag)
