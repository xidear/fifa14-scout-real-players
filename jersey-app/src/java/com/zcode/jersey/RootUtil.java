package com.zcode.jersey;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;

/** Thin wrapper around root shell commands and /proc access. */
final class RootUtil {

    private RootUtil() {}

    static Process sh(String cmd) throws IOException {
        return new ProcessBuilder("su", "-c", cmd).redirectErrorStream(true).start();
    }

    /** True when the PC-side bridge answers (adb forward + root helper on the PC). */
    static boolean bridgeAlive() {
        return RootBridge.alive();
    }

    static String shRead(String cmd, int maxLines) {
        String out = shReadLocal(cmd, maxLines);
        if (out != null && !out.isEmpty()) {
            Log.i("su: " + brief(cmd) + " -> " + brief(out));
            return out;
        }
        if (RootBridge.alive()) {
            String b = RootBridge.exec(cmd);
            if (b != null) {
                Log.i("su(bridge): " + brief(cmd) + " -> " + brief(b));
                return b;
            }
        }
        Log.w("su: " + brief(cmd) + " -> (empty)");
        return out == null ? "" : out;
    }

    private static String brief(String s) {
        if (s == null) return "null";
        String t = s.replace("\n", " | ").replace("\r", "");
        return t.length() > 300 ? t.substring(0, 300) + "..." : t;
    }

    private static String shReadLocal(String cmd, int maxLines) {
        try {
            Process p = sh(cmd);
            BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            int n = 0;
            while ((line = r.readLine()) != null && n++ < maxLines) sb.append(line).append('\n');
            p.waitFor();
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    private static volatile Boolean rootCache = null;
    private static volatile long rootAt = 0;

    static boolean hasRoot() {
        long now = System.currentTimeMillis();
        if (rootCache != null && now - rootAt < 5000) return rootCache;
        if (!checkRoot()) {
            boolean viaBridge = RootBridge.alive();
            rootCache = viaBridge;
            rootAt = now;
            return viaBridge;
        }
        boolean r = checkRoot();
        rootCache = r;
        rootAt = now;
        return r;
    }

    private static boolean checkRoot() {
        Process p = null;
        try {
            p = sh("id; cat /proc/self/status | grep -E \"Uid\"");
            BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()));
            String line;
            boolean uid0 = false;
            while ((line = r.readLine()) != null) {
                // "uid=0(root) gid=..." or "	Uid:	0	0	0	0"
                if (line.startsWith("uid=0") || line.contains("Uid:	0	0")) uid0 = true;
            }
            p.waitFor();
            return uid0;
        } catch (Exception e) {
            return false;
        } finally {
            if (p != null) p.destroy();
        }
    }

    static boolean hasMagisk() {
        return new File("/data/adb/magisk").exists() || new File("/sbin/magisk").exists();
    }

    private static volatile int fifaPidCache = -1;
    private static volatile long fifaPidAt = 0;

    static int fifaPid() {
        long now = System.currentTimeMillis();
        if (now - fifaPidAt < 2000) return fifaPidCache;
        fifaPidAt = now;
        fifaPidCache = fifaPidUncached();
        return fifaPidCache;
    }

    private static int fifaPidUncached() {
        String out = shRead("pidof com.ea.game.fifa14_row", 5).trim();
        if (out.isEmpty()) {
            try {
                Process p = new ProcessBuilder("pidof", "com.ea.game.fifa14_row")
                        .redirectErrorStream(true).start();
                BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()));
                out = r.readLine();
                p.waitFor();
            } catch (Exception e) {
                out = null;
            }
        }
        if (out == null) return -1;
        out = out.trim();
        if (out.isEmpty()) return -1;
        try {
            return Integer.parseInt(out.split("\\s+")[0]);
        } catch (Exception e) {
            return -1;
        }
    }

    /** Maps of the FIFA process as read by root (fallback for non-root app). */
    static List<String> mapsRoot(int pid) {
        List<String> out = new ArrayList<>();
        String txt = shRead("cat /proc/" + pid + "/maps", 20000);
        for (String line : txt.split("\n")) if (!line.isEmpty()) out.add(line);
        return out;
    }
}
