#!/usr/bin/env bash
# Push the real-player scout databases to a rooted Android device (macOS/Linux).
#   ADB=/path/to/adb PKG=com.ea.game.fifa14_row ./tools/push_db.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ADB="${ADB:-adb}"
PKG="${PKG:-com.ea.game.fifa14_row}"
MAIN="$HERE/../scout/main_fifa.db"
NEW="$HERE/../scout/newdb_fifa.db"

md5sum "$MAIN" "$NEW"
[ "$(md5sum "$MAIN" | cut -d' ' -f1)" = "3a8a4b70420f36e305009f2d02def18c" ] || { echo "main db md5 mismatch"; exit 1; }
[ "$(md5sum "$NEW"  | cut -d' ' -f1)" = "20492d18892da29e99bce4e8be9b2797" ] || { echo "new db md5 mismatch"; exit 1; }

"$ADB" shell am force-stop "$PKG" || true
"$ADB" push "$MAIN" /data/local/tmp/fifa_main.db
"$ADB" push "$NEW"  /data/local/tmp/fifa_new.db

cat > /tmp/rea_push_db.sh <<EOF
set -e
BASE="/sdcard/Android/data/$PKG/data"
DIR="\$BASE/cmn"
[ -d "\$DIR" ] || { echo "ERROR: \$DIR not found; launch the game once"; exit 3; }
TS=\$(date +%Y%m%d_%H%M%S)
mkdir -p "\$DIR/New DB"
[ -f "\$DIR/fifa.db" ] && cp -p "\$DIR/fifa.db" "\$DIR/fifa.db.bak_\$TS" || true
[ -f "\$DIR/New DB/fifa.db" ] && cp -p "\$DIR/New DB/fifa.db" "\$DIR/New DB/fifa.db.bak_\$TS" || true
cp /data/local/tmp/fifa_main.db "\$DIR/fifa.db"
cp /data/local/tmp/fifa_new.db  "\$DIR/New DB/fifa.db"
OWN=\$(stat -c '%u:%g' "\$BASE")
chown "\$OWN" "\$DIR/fifa.db" "\$DIR/New DB/fifa.db"
chmod 664 "\$DIR/fifa.db" "\$DIR/New DB/fifa.db"
md5sum "\$DIR/fifa.db" "\$DIR/New DB/fifa.db"
ls -l "\$DIR/fifa.db" "\$DIR/New DB/fifa.db"
EOF

"$ADB" push /tmp/rea_push_db.sh /data/local/tmp/rea_push_db.sh
"$ADB" shell su -c "sh /data/local/tmp/rea_push_db.sh"
echo "Done. Create a NEW career in game (old saves are incompatible)."