package com.zcode.jersey;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;

/**
 * Reads and writes the career save (SAVECAREER.*) through root.
 *
 * The save contains a flat roster table: 16-byte rows (teamid, playerid, flags, alt),
 * jersey = ((flags & 0xFF) >> 1) + 1. Rows are grouped per team; the table starts at a
 * 4-byte aligned offset (offset % 16 == 4 on this build), so discovery scans every
 * alignment and keeps runs of >= 5 rows that share a team id.
 */
final class SaveBackend {

    static final String DIR = "/data/media/0/Android/data/com.ea.game.fifa14_row/";
    static final int ROW = 16;

    static final class Row {
        int pid;
        int flags;
        int alt;
        int offset;
        int jersey() { return ((flags & 0xFF) >> 1) + 1; }
    }

    static final class Block {
        int offset;
        int team;
        int rows;
        final List<Row> list = new ArrayList<>();
    }

    private SaveBackend() {}

    static String newestPath() {
        String out = RootUtil.shRead("ls -t " + DIR + "SAVECAREER* 2>/dev/null | head -1", 3).trim();
        return out.isEmpty() ? null : out;
    }

    static byte[] read(Context ctx, String path) {
        File cache = new File(ctx.getCacheDir(), "save_read.bin");
        String cmd = "cp '" + path + "' '" + cache.getAbsolutePath() + "' && chmod 644 '"
                + cache.getAbsolutePath() + "'";
        RootUtil.shRead(cmd, 2);
        if (!cache.exists() || cache.length() == 0) return null;
        try {
            InputStream in = new FileInputStream(cache);
            ByteArrayOutputStream bo = new ByteArrayOutputStream((int) cache.length());
            byte[] buf = new byte[1 << 16];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            in.close();
            return bo.toByteArray();
        } catch (Exception e) {
            return null;
        }
    }

    static boolean write(Context ctx, String path, byte[] data) {
        fixChecksum(data);
        File f = new File(ctx.getCacheDir(), "save_write.bin");
        try (FileOutputStream out = new FileOutputStream(f)) {
            out.write(data);
        } catch (Exception e) {
            return false;
        }
        String own = RootUtil.shRead("stat -c '%u %g' '" + path + "'", 2).trim();
        String[] og = own.split("\\s+");
        if (og.length != 2) return false;
        String tmp = path + ".app_tmp";
        String bak = path + ".bak_jersey";
        // Keep one untouched copy of the save from before the first edit.
        String cmd = "cp '" + f.getAbsolutePath() + "' '" + tmp + "'"
                + " && chown " + og[0] + ":" + og[1] + " '" + tmp + "'"
                + " && chmod 660 '" + tmp + "'"
                + " && { [ -f '" + bak + "' ] || { cp '" + path + "' '" + bak + "'"
                + " && chown " + og[0] + ":" + og[1] + " '" + bak + "'"
                + " && chmod 660 '" + bak + "'; } }"
                + " && mv -f '" + tmp + "' '" + path + "'";
        RootUtil.shRead(cmd, 3);
        String check = RootUtil.shRead("stat -c '%u %g %a' '" + path + "'", 2).trim();
        return check.equals(og[0] + " " + og[1] + " 660");
    }

    /** Restores the untouched copy saved by write(); false when there is none. */
    static boolean restoreBackup(String path) {
        String bak = path + ".bak_jersey";
        String own = RootUtil.shRead("stat -c '%u %g' '" + path + "'", 2).trim();
        String[] og = own.split("\\s+");
        if (og.length != 2) return false;
        String cmd = "[ -f '" + bak + "' ] && cp '" + bak + "' '" + path + "'"
                + " && chown " + og[0] + ":" + og[1] + " '" + path + "'"
                + " && chmod 660 '" + path + "' && echo OK";
        return RootUtil.shRead(cmd, 2).trim().equals("OK");
    }

    /**
     * The last 4 bytes of SAVECAREER are a CRC-32 over every byte before them:
     * polynomial 0x04C11DB7, non-reflected, init 0xFFFFFFFF, final xor 0xFFFFFFFF.
     * The game refuses the save when it does not match.
     */
    static int checksum(byte[] d, int len) {
        int c = 0xFFFFFFFF;
        for (int i = 0; i < len; i++) {
            c ^= (d[i] & 0xFF) << 24;
            for (int k = 0; k < 8; k++) {
                c = (c & 0x80000000) != 0 ? (c << 1) ^ 0x04C11DB7 : c << 1;
            }
        }
        return c ^ 0xFFFFFFFF;
    }

    static void fixChecksum(byte[] d) {
        if (d.length < 8) return;
        int n = d.length - 4;
        int c = checksum(d, n);
        d[n] = (byte) c;
        d[n + 1] = (byte) (c >>> 8);
        d[n + 2] = (byte) (c >>> 16);
        d[n + 3] = (byte) (c >>> 24);
    }

    static boolean checksumOk(byte[] d) {
        if (d.length < 8) return false;
        int n = d.length - 4;
        int stored = (d[n] & 0xFF) | ((d[n + 1] & 0xFF) << 8)
                | ((d[n + 2] & 0xFF) << 16) | ((d[n + 3] & 0xFF) << 24);
        return stored == checksum(d, n);
    }

    static List<Block> parse(byte[] d) {
        List<Block> out = new ArrayList<>();
        int n = d.length;
        ByteBuffer b = ByteBuffer.wrap(d).order(ByteOrder.LITTLE_ENDIAN);
        for (int align = 0; align < 16; align += 4) {
            int i = align;
            while (i + ROW <= n) {
                int t = b.getInt(i);
                int p = b.getInt(i + 4);
                if (p > 0 && p < 30_000_000 && t > 0 && t < 10_000_000) {
                    int j = i + ROW;
                    while (j + ROW <= n) {
                        int t2 = b.getInt(j);
                        int p2 = b.getInt(j + 4);
                        if (t2 != t || p2 <= 0 || p2 >= 30_000_000) break;
                        j += ROW;
                    }
                    int cnt = (j - i) / ROW;
                    if (cnt >= 5) {
                        Block bl = new Block();
                        bl.offset = i;
                        bl.team = t;
                        bl.rows = cnt;
                        for (int k = 0; k < cnt; k++) {
                            int o = i + k * ROW;
                            Row r = new Row();
                            r.pid = b.getInt(o + 4);
                            r.flags = b.getInt(o + 8);
                            r.alt = b.getInt(o + 12);
                            r.offset = o;
                            bl.list.add(r);
                        }
                        out.add(bl);
                    }
                    i = j;
                } else {
                    i += ROW;
                }
            }
        }
        return out;
    }

    static Block teamBlock(List<Block> blocks, int team) {
        Block best = null;
        for (Block b : blocks) {
            if (b.team == team && (best == null || b.rows > best.rows)) best = b;
        }
        return best;
    }

    static int setJersey(byte[] data, int rowOffset, int jersey) {
        ByteBuffer b = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        int flags = b.getInt(rowOffset + 8);
        int nf = (flags & ~0xFF) | (((jersey - 1) * 2) & 0xFE);
        b.putInt(rowOffset + 8, nf);
        return nf;
    }

    static Row find(List<Block> blocks, int pid) {
        for (Block b : blocks) {
            for (Row r : b.list) if (r.pid == pid) return r;
        }
        return null;
    }
}