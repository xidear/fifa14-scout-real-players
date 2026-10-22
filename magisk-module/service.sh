#!/system/bin/sh
# Show the jersey-number floating button each time FIFA14 starts.
# The editor app must be installed and granted root in Magisk.
MODDIR=${0%/*}
PKG=com.ea.game.fifa14_row
APP=com.zcode.jersey
LOCK=/data/local/tmp/fifa14_jersey_auto.lock

[ -f "$LOCK" ] && exit 0
echo $$ > "$LOCK"

appops set $APP SYSTEM_ALERT_WINDOW allow 2>/dev/null

LAST=""
while true; do
    PID=$(pidof $PKG 2>/dev/null | awk '{print $1}')
    if [ -n "$PID" ] && [ "$PID" != "$LAST" ]; then
        LAST="$PID"
        am startservice -n $APP/.PanelService -a com.zcode.jersey.START >/dev/null 2>&1
    fi
    [ -z "$PID" ] && LAST=""
    sleep 5
done