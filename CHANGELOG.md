# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y versionado [SemVer](https://semver.org/lang/es/).

## [0.1.0] - 2026-10-25

### Añadido
- Instalador gráfico automático para Arch Linux y derivadas.
- Desinstalador completo con confirmación previa.
- Detección automática de voces instaladas.
- Control de velocidad y tono.
- Control de volumen con `ffmpeg`.
- Menú dinámico de expresiones (sonidos y frases).
- Pausas personalizadas con precisión de 120 ms.
- Editor de lexicones (pronunciaciones personalizadas).
- Importación de PDF, DOCX y EPUB.
- Caché de audio SHA-256 con evicción LRU.
- Tema claro/oscuro/sistema con libadwaita.
- Reproductor integrado con GStreamer (Play/Pausa/Stop).
- Icono propio en el menú de aplicaciones y AboutWindow.
- Layout responsivo con `Adw.WrapBox`.
- Selector de idioma avanzado.
- Cierre limpio de procesos Wine residuales.

### Conocido
- El modo SSML no funciona (`TTSFileGenerator.exe` no interpreta etiquetas SSML).
- Solo probado en CachyOS/Arch Linux.
- Requiere `ffmpeg` para el control de volumen.
- No integra voces libres todavía (eSpeak, RHVoice, Piper).
- Sin botones de énfasis.
