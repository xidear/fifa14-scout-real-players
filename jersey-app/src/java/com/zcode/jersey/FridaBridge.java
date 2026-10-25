package com.zcode.jersey;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * Calls the game's own DB setter through a small helper on the PC:
 *   python jersey_lib_setter.py     (listens on 18082, uses frida-server on the device)
 * The helper runs the equivalent of MGRSetPlayerJerseyNumber(playerid, jersey) in-process,
 * which is what the game UI would do, so the number survives wherever the game reloads it.
 */
final class FridaBridge {

    private static final int PORT = 18082;
    private static final String END = "DONE";

    private FridaBridge() {}

    static boolean available() {
        try (Socket s = new Socket("127.0.0.1", PORT)) {
            s.setSoTimeout(1200);
            OutputStream out = s.getOutputStream();
            out.write(("ping" + String.valueOf((char) 10)).getBytes(StandardCharsets.UTF_8));
            out.flush();
            BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(),
                    StandardCharsets.UTF_8));
            String line = r.readLine();
            return line != null && line.contains("pong");
        } catch (Exception e) {
            return false;
        }
    }

    static boolean setJersey(int pid, int playerId, int jersey) {
        try (Socket s = new Socket("127.0.0.1", PORT)) {
            s.setSoTimeout(8000);
            OutputStream out = s.getOutputStream();
            out.write(("set " + playerId + " " + jersey + String.valueOf((char) 10)).getBytes(StandardCharsets.UTF_8));
            out.flush();
            BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(),
                    StandardCharsets.UTF_8));
            String line;
            while ((line = r.readLine()) != null) {
                if (line.startsWith("ok")) return true;
                if (line.startsWith("err")) return false;
            }
            return false;
        } catch (Exception e) {
            return false;
        }
    }
}