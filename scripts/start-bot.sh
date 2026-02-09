#!/bin/bash
# Wrapper script for ClawCode bot — launched by launchd.
# bash is the responsible process for macOS TCC, which gives child
# processes (python, node, ruby/icalpal) Full Disk Access.
exec /Users/jsperson/clawcode/.venv/bin/python -m bot.main
