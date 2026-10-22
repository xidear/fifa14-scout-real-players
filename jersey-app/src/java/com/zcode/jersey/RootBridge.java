package com.zcode.jersey;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * Root bridge used when the app itself cannot obtain su (Magisk refused it).
 *
 * The PC-side helper opens `adb forward tcp:27183 tcp:27183` and runs a tiny shell
 * server; the app sends one command per line and receives output terminated by a
 * sentinel. Nothing here grants the app more than the PC already has through adb.
 */
final class RootBridge {

    static final int PORT = 18081;
    private static final String END = "\u0001END";

    private RootBridge() {}

    static boolean alive() {
        try (Socket s = new Socket("127.0.0.1", PORT)) {
            s.setSoTimeout(800);
            OutputStream out = s.getOutputStream();
            out.write("echo ok\n".getBytes(StandardCharsets.UTF_8));
            out.flush();
            BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(),
                    StandardCharsets.UTF_8));
            String line;
            while ((line = r.readLine()) != null) if (line.equals(END)) return true;
        } catch (Exception e) {
            log("alive fail: " + e);
            return false;
        }
        return false;
    }

    static void log(String msg) {
        try {
            java.io.File f = new java.io.File("/sdcard/Android/data/com.ea.game.fifa14_row/files/app_bridge.log");
            java.io.FileWriter w = new java.io.FileWriter(f, true);
            w.write(System.currentTimeMillis() + " " + msg + String.valueOf((char) 10));
            w.close();
        } catch (Exception ignored) {}
    }

    /** Reads up to len bytes of process memory through the bridge (base64). */
    static byte[] readMem(int pid, long addr, int len) {
        String hex = String.format("%x", addr);
        String out = exec("dd if=/proc/" + pid + "/mem bs=65536 skip=$((0x" + hex + "/65536)) "
                + "iflag=skip_bytes,count_bytes count=" + len + " 2>/dev/null | base64 -w0");
        if (out == null) return null;
        out = out.trim();
        if (out.isEmpty()) return null;
        try {
            return android.util.Base64.decode(out, android.util.Base64.DEFAULT);
        } catch (Exception e) {
            return null;
        }
    }

    /** Runs a shell command on the PC side (where adb has already been given root). */
    static String exec(String cmd) {
        log("exec: " + cmd);
        try (Socket s = new Socket("127.0.0.1", PORT)) {
            s.setSoTimeout(15000);
            OutputStream out = s.getOutputStream();
            out.write((cmd.replace('\n', ' ') + "\n").getBytes(StandardCharsets.UTF_8));
            out.flush();
            BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(),
                    StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) {
                if (line.equals(END)) break;
                sb.append(line).append('\n');
            }
            return sb.toString();
        } catch (Exception e) {
            return null;
        }
    }
}