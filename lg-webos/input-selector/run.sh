#!/bin/sh
exec >/tmp/overlay.log 2>&1
cd /media/developer/apps/usr/palm/applications/com.webosbrew.overlay
exec /usr/bin/python ./overlay.py
