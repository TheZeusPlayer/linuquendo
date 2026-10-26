import loquendo.tts.engine.*;
import java.io.*;
import java.net.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.*;

public class LoquendoDaemon {
    private static final int SOCKET_READ_TIMEOUT_MS = 60 * 1000;
    private static final long IDLE_TIMEOUT_MS = 5 * 60 * 1000;

    private TTSSession session;
    private final AtomicBoolean running = new AtomicBoolean(true);

    public static void main(String[] args) {
        int port = 0;
        if (args.length > 0) {
            try { port = Integer.parseInt(args[0]); } catch (NumberFormatException e) {}
        }
        new LoquendoDaemon().run(port);
    }

    private void initEngine() throws Exception {
        if (session == null) {
            session = new TTSSession();
        }
    }

    private void run(int requestedPort) {
        Runtime.getRuntime().addShutdownHook(new Thread() {
            public void run() {
                running.set(false);
                try { if (session != null) session.delete(); } catch (Exception e) {}
            }
        });

        ServerSocket server = null;
        try {
            server = new ServerSocket();
            server.setReuseAddress(true);
            server.bind(new InetSocketAddress("127.0.0.1", requestedPort));
            System.out.println("PORT:" + server.getLocalPort());
            System.out.flush();
        } catch (IOException e) {
            System.err.println("FATAL:bind:" + e.getMessage());
            System.exit(1);
        }

        long lastActivity = System.currentTimeMillis();

        try {
            server.setSoTimeout(5000);
            while (running.get()) {
                if (System.currentTimeMillis() - lastActivity > IDLE_TIMEOUT_MS) {
                    System.out.println("IDLE_TIMEOUT");
                    break;
                }
                Socket client = null;
                try {
                    client = server.accept();
                } catch (SocketTimeoutException e) {
                    continue;
                } catch (IOException e) {
                    if (running.get()) System.err.println("Accept: " + e.getMessage());
                    continue;
                }
                lastActivity = System.currentTimeMillis();
                try {
                    handleClient(client);
                } catch (Exception e) {
                    System.err.println("Client: " + e.getMessage());
                } finally {
                    try { client.close(); } catch (Exception e) {}
                }
                lastActivity = System.currentTimeMillis();
            }
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            try { server.close(); } catch (Exception e) {}
        }
    }

    private void handleClient(Socket client) throws Exception {
        client.setSoTimeout(SOCKET_READ_TIMEOUT_MS);
        client.setTcpNoDelay(true);
        BufferedReader in = new BufferedReader(new InputStreamReader(client.getInputStream(), "UTF-8"));
        PrintWriter out = new PrintWriter(new OutputStreamWriter(client.getOutputStream(), "UTF-8"), true);

        String line;
        while ((line = in.readLine()) != null) {
            String response;
            try {
                response = handleRequest(line);
            } catch (Exception e) {
                response = "{\"status\":\"error\",\"message\":\"" + escape(e.getMessage()) + "\"}";
            }
            out.println(response);
            if (response.contains("\"status\":\"shutdown\"")) {
                running.set(false);
                break;
            }
        }
    }

    private String handleRequest(String json) throws Exception {
        String action = getString(json, "action");
        if (action == null) return "{\"status\":\"error\",\"message\":\"missing action\"}";
        if ("ping".equals(action)) return "{\"status\":\"ok\",\"version\":\"1.0\"}";
        if ("shutdown".equals(action)) return "{\"status\":\"shutdown\"}";
        if ("synth".equals(action)) return handleSynth(json);
        return "{\"status\":\"error\",\"message\":\"unknown action\"}";
    }

    private String handleSynth(String json) throws Exception {
        String text = getString(json, "text");
        String voice = getString(json, "voice");
        String outPath = getString(json, "out");
        String mode = getString(json, "mode");
        int freq = getInt(json, "freq", 44100);
        int channels = getInt(json, "channels", 2);
        int speed = getInt(json, "speed", 50);
        int pitch = getInt(json, "pitch", 50);

        if (text == null || voice == null) {
            return "{\"status\":\"error\",\"message\":\"missing params\"}";
        }

        long start = System.currentTimeMillis();
        initEngine();

        TTSReader reqReader = new TTSReader(session);
        try {
            if ("preview".equals(mode)) {
                reqReader.setAudio("LTTS7AudioBoard", null, freq, "linear", channels);
            } else {
                if (outPath == null) {
                    return "{\"status\":\"error\",\"message\":\"missing out path for export\"}";
                }
                reqReader.setAudio("LTTS7AudioFile", outPath, freq, "linear", channels);
            }

            reqReader.loadPersona(voice, null, null);
            reqReader.setParam("TextEncoding", "utf-8");
            reqReader.setSpeed(speed);
            reqReader.setPitch(pitch);

            reqReader.read(text, true, false);

            long waitStart = System.currentTimeMillis();
            while (!reqReader.done()) {
                if (System.currentTimeMillis() - waitStart > 30000) {
                    throw new Exception("Timeout sintesis");
                }
                Thread.sleep(50);
            }
        } finally {
            try { reqReader.delete(); } catch (Exception e) {}
        }

        long elapsed = System.currentTimeMillis() - start;
        String path = (outPath != null) ? escape(outPath) : "";
        return "{\"status\":\"ok\",\"path\":\"" + path + "\",\"time_ms\":" + elapsed + "}";
    }

    private String getString(String json, String key) {
        Pattern p = Pattern.compile("\"" + Pattern.quote(key) + "\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"");
        Matcher m = p.matcher(json);
        return m.find() ? unescape(m.group(1)) : null;
    }

    private int getInt(String json, String key, int def) {
        Pattern p = Pattern.compile("\"" + Pattern.quote(key) + "\"\\s*:\\s*(-?\\d+)");
        Matcher m = p.matcher(json);
        return m.find() ? Integer.parseInt(m.group(1)) : def;
    }

    private String escape(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': sb.append("\\\\"); break;
                case '"': sb.append("\\\""); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 32 || c > 126) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
            }
        }
        return sb.toString();
    }

    private String unescape(String s) {
        if (s == null) return null;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\' && i + 1 < s.length()) {
                char n = s.charAt(i + 1);
                switch (n) {
                    case 'n': sb.append('\n'); i++; break;
                    case 'r': sb.append('\r'); i++; break;
                    case 't': sb.append('\t'); i++; break;
                    case '"': sb.append('"'); i++; break;
                    case '\\': sb.append('\\'); i++; break;
                    case 'u':
                        if (i + 5 < s.length()) {
                            try { sb.append((char) Integer.parseInt(s.substring(i + 2, i + 6), 16)); i += 5; }
                            catch (NumberFormatException e) { sb.append(c); }
                        } else sb.append(c);
                        break;
                    default: sb.append(c);
                }
            } else sb.append(c);
        }
        return sb.toString();
    }
}
