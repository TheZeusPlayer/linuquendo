import loquendo.tts.engine.*;

public class LoquendoTTS {
    public static void main(String[] args) {
        if (args.length < 6) {
            System.err.println("Uso: LoquendoTTS <texto> <voz> <archivo_salida> <frecuencia> <canales> <velocidad> <tono>");
            System.exit(1);
        }

        String texto = args[0];
        String voz = args[1];
        String archivoSalida = args[2];
        int frecuencia = Integer.parseInt(args[3]);
        int canales = Integer.parseInt(args[4]);
        int velocidad = Integer.parseInt(args[5]);
        int tono = (args.length > 6) ? Integer.parseInt(args[6]) : 50;

        TTSSession session = null;
        TTSReader reader = null;

        try {
            session = new TTSSession();
            reader = new TTSReader(session);
            reader.setAudio("LTTS7AudioFile", archivoSalida, frecuencia, "linear", canales);
            reader.loadPersona(voz, null, null);
            reader.setParam("TextEncoding", "utf-8");
            reader.setSpeed(velocidad);
            reader.setPitch(tono);
            reader.read(texto, true, false);

            while (!reader.done()) {
                Thread.sleep(100);
            }
            System.out.println("Síntesis completada: " + archivoSalida);
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        } finally {
            try { if (reader != null) reader.delete(); } catch (Exception e) {}
            try { if (session != null) session.delete(); } catch (Exception e) {}
        }
    }
}
