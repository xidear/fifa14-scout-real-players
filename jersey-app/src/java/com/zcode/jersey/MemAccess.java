package com.zcode.jersey;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Read/write access to another process's memory (root via su, or PC bridge). */
final class MemAccess {

    private MemAccess() {}

    static byte[] read(int pid, long addr, int len) {
        if (addr <= 0 || len <= 0) return null;
        try {
            java.io.RandomAccessFile f = new java.io.RandomAccessFile("/proc/" + pid + "/mem", "r");
            try {
                f.seek(addr);
                byte[] b = new byte[len];
                f.readFully(b);
                return b;
            } finally {
                f.close();
            }
        } catch (Exception e) {
            // fall through to the bridge
        }
        if (RootBridge.alive()) {
            byte[] b = RootBridge.readMem(pid, addr, len);
            if (b != null && b.length == len) return b;
        }
        return null;
    }

    static boolean write(int pid, long addr, int flags) {
        byte[] le = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(flags).array();
        // 1) direct write (works when this process is root: su session / adb root)
        try {
            java.io.RandomAccessFile f = new java.io.RandomAccessFile("/proc/" + pid + "/mem", "rw");
            try {
                f.seek(addr);
                f.write(le);
                return true;
            } finally {
                f.close();
            }
        } catch (Exception ignored) {
        }
        // 2) PC-side root bridge (adb forward), used when the app has no su itself
        if (RootBridge.alive()) {
            String hex = String.format("%02x%02x%02x%02x", le[0] & 0xff, le[1] & 0xff, le[2] & 0xff, le[3] & 0xff);
            String out = RootBridge.exec("printf '\\x" + hex.substring(0, 2) + "\\x" + hex.substring(2, 4)
                    + "\\x" + hex.substring(4, 6) + "\\x" + hex.substring(6, 8)
                    + "' | dd of=/proc/" + pid + "/mem bs=1 seek=" + addr + " conv=notrunc 2>&1; echo WRITTEN");
            if (out != null && out.contains("WRITTEN")) return true;
        }
        // 3) root shell dd
        try {
            String hex = String.format("%02x%02x%02x%02x", le[0] & 0xff, le[1] & 0xff, le[2] & 0xff, le[3] & 0xff);
            String cmd = "printf '\\x" + hex.substring(0, 2) + "\\x" + hex.substring(2, 4) + "\\x"
                    + hex.substring(4, 6) + "\\x" + hex.substring(6, 8) + "' | dd of=/proc/" + pid
                    + "/mem bs=1 seek=" + addr + " conv=notrunc 2>/dev/null";
            Process p = RootUtil.sh(cmd);
            p.waitFor();
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}