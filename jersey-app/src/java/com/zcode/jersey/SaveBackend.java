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
 * Reads and writes SAVECAREER.* through root.
 *
 * Roster rows are 16 bytes (team, player, flags, alt); jersey = ((flags & 0xFF) >> 1) + 1.
 * The last 4 bytes hold a CRC-32 over the rest of the file; the game rejects a save whose
 * checksum does not match, so every write recomputes it and then reads the file back to
 * confirm the bytes really landed.
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
        String out = RootUtil.shRead("ls -t " + DIR + "SAVECAREER* 2>/dev/null | grep -v '\\.bak' | grep -v '\\.app_' | head -1", 3).trim();
        return out.isEmpty() ? null : out;
    }

    static byte[] read(Context ctx, String path) {
        long t0 = System.currentTimeMillis();
        File cache = new File(ctx.getCacheDir(), "save_read.bin");
        if (cache.exists()) cache.delete();
        String cmd = "cp '" + path + "' '" + cache.getAbsolutePath() + "' && chmod 644 '"
                + cache.getAbsolutePath() + "'";
        RootUtil.shRead(cmd, 2);
        if (!cache.exists() || cache.length() == 0) {
            Log.e("read: root cp failed for " + path + " cmd=" + cmd);
            return null;
        }
        try {
            InputStream in = new FileInputStream(cache);
            ByteArrayOutputStream bo = new ByteArrayOutputStream((int) cache.length());
            byte[] buf = new byte[1 << 16];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            in.close();
            byte[] out = bo.toByteArray();
            Log.i("read: " + out.length + " bytes in " + (System.currentTimeMillis() - t0) + "ms");
            return out;
        } catch (Exception e) {
            Log.e("read: cache read failed: " + e, e);
            return null;
        }
    }

    /** Result of a write attempt; {@link #ok} is only true after a verified read-back. */
    static final class WriteResult {
        boolean ok;
        String error = "";
        static WriteResult fail(String why) {
            WriteResult r = new WriteResult();
            r.error = why;
            return r;
        }
    }

    static WriteResult write(Context ctx, String path, byte[] data) {
        long t0 = System.currentTimeMillis();
        fixChecksum(data);
        int crc = (data[data.length - 4] & 0xFF) | ((data[data.length - 3] & 0xFF) << 8)
                | ((data[data.length - 2] & 0xFF) << 16) | ((data[data.length - 1] & 0xFF) << 24);
        Log.i("write: start path=" + path + " bytes=" + data.length + " crc=0x" + Integer.toHexString(crc));
        File f = new File(ctx.getCacheDir(), "save_write.bin");
        try (FileOutputStream out = new FileOutputStream(f)) {
            out.write(data);
        } catch (Exception e) {
            return WriteResult.fail("写临时文件失败: " + e.getMessage());
        }
        String own = RootUtil.shRead("stat -c '%u %g %a' '" + path + "'", 2).trim();
        String[] og = own.split("\\s+");
        Log.i("write: stat=" + own);
        if (og.length != 3) {
            Log.e("write: stat failed, out=" + own);
            return WriteResult.fail("读不到原存档属主（root 失败？）");
        }

        String tmp = path + ".app_tmp";
        String bak = path + ".bak_jersey";
        String cmd = "cp '" + f.getAbsolutePath() + "' '" + tmp + "'"
                + " && chown " + og[0] + ":" + og[1] + " '" + tmp + "'"
                + " && chmod " + og[2] + " '" + tmp + "'"
                + " && { [ -f '" + bak + "' ] || { cp '" + path + "' '" + bak + "'"
                + " && chown " + og[0] + ":" + og[1] + " '" + bak + "'"
                + " && chmod " + og[2] + " '" + bak + "'; } }"
                + " && mv -f '" + tmp + "' '" + path + "'"
                + " && echo APPLIED";
        String out = RootUtil.shRead(cmd, 5).trim();
        Log.i("write: install out=" + out);
        if (!out.contains("APPLIED")) {
            Log.e("write: install failed, cmd=" + cmd + " out=" + out);
            return WriteResult.fail("root 命令未成功: " + out);
        }

        // Verify: read the file back and compare every byte with what we meant to write.
        byte[] back = read(ctx, path);
        if (back == null) {
            Log.e("write: read-back failed");
            return WriteResult.fail("写入后回读失败");
        }
        if (back.length != data.length) {
            Log.e("write: read-back length " + back.length + " != " + data.length);
            return WriteResult.fail("回读长度不符 " + back.length + " != " + data.length);
        }
        int firstDiff = -1;
        for (int i = 0; i < back.length; i++) {
            if (back[i] != data[i]) { firstDiff = i; break; }
        }
        if (firstDiff >= 0) {
            Log.e("write: read-back mismatch at 0x" + Integer.toHexString(firstDiff)
                    + " expected=" + String.format("%02x", data[firstDiff])
                    + " actual=" + String.format("%02x", back[firstDiff]));
            return WriteResult.fail("回读内容不符，首个差异 @" + Integer.toHexString(firstDiff));
        }
        Log.i("write: verified OK in " + (System.currentTimeMillis() - t0) + "ms");
        WriteResult r = new WriteResult();
        r.ok = true;
        return r;
    }

    /** Restores the untouched copy saved by write(); false when there is none. */
    static boolean restoreBackup(String path) {
        Log.i("restore: start path=" + path);
        String bak = path + ".bak_jersey";
        String own = RootUtil.shRead("stat -c '%u %g %a' '" + path + "'", 2).trim();
        String[] og = own.split("\\s+");
        if (og.length != 3) return false;
        String cmd = "[ -f '" + bak + "' ] && cp '" + bak + "' '" + path + "'"
                + " && chown " + og[0] + ":" + og[1] + " '" + path + "'"
                + " && chmod " + og[2] + " '" + path + "' && echo OK";
        String out = RootUtil.shRead(cmd, 2).trim();
        Log.i("restore: out=" + out);
        return out.equals("OK");
    }

    static boolean hasBackup(String path) {
        String cmd = "[ -f '" + path + ".bak_jersey' ] && echo Y";
        return RootUtil.shRead(cmd, 1).trim().equals("Y");
    }

    /**
     * The last 4 bytes of SAVECAREER are a CRC-32 over every byte before them:
     * polynomial 0x04C11DB7, non-reflected, init 0xFFFFFFFF, final xor 0xFFFFFFFF.
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

    /** The managed club id is stored at offset 8 of the save header. */
    static int headerTeam(byte[] d) {
        if (d.length < 12) return -1;
        int t = (d[8] & 0xFF) | ((d[9] & 0xFF) << 8) | ((d[10] & 0xFF) << 16) | ((d[11] & 0xFF) << 24);
        return (t > 0 && t < 10_000_000) ? t : -1;
    }

    static Block blockContaining(List<Block> blocks, int offset) {
        for (Block b : blocks) {
            if (offset >= b.offset && offset < b.offset + b.rows * ROW) return b;
        }
        return null;
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