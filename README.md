<div align="center">

<img src="assets/icons/hicolor/scalable/apps/linuquendo.svg" alt="Linuquendo TTS" width="128" height="128"/>

# Linuquendo TTS

**Un frontend moderno en GTK4 para el motor de Loquendo TTS Director 7 en Linux.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform: Arch Linux](https://img.shields.io/badge/Platform-Arch%20Linux-1793D1?logo=arch-linux)](https://archlinux.org/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GTK4](https://img.shields.io/badge/GTK-4.0-4A86CF?logo=gtk)](https://www.gtk.org/)
[![Estado](https://img.shields.io/badge/Estado-Beta-yellow)]()

[Características](#-características) •
[Instalación](#-instalación) •
[Uso](#-uso) •
[Preguntas frecuentes](#-preguntas-frecuentes) •
[Contribuir](#-contribuir) •
[Apoyar](#-apoya-el-proyecto)

</div>

---

## ¿Qué es Linuquendo?

**Linuquendo TTS** es una interfaz gráfica moderna para el motor clásico de **Loquendo TTS Director 7** en Linux. Sustituye la anticuada interfaz Java del TTS Director original por una aplicación nativa basada en **GTK4 + libadwaita**, integrada con el escritorio GNOME y adaptable a cualquier entorno.

Originalmente, usar Loquendo en Linux requiere instalar Wine, configurar manualmente el WINEPREFIX, aplicar parches, copiar DLLs a `syswow64` y aprender la sintaxis de `TTSFileGenerator.exe`. **Linuquendo automatiza toda esa cadena** y te deja lo único importante: escribir y escuchar.
Se usó asistencia total de DeepSeek para poder crear esta aplicación.


> ⚠️ **Linuquendo no incluye, distribuye ni promueve el uso de Loquendo, sus voces, sus instaladores ni parches de licencia.** Es una herramienta de automatización e interfaz. El usuario es el único responsable de obtener los instaladores originales y cumplir con las licencias correspondientes.

---


### Motor y síntesis
- **Detección automática de voces** instaladas (Jorge, Carlos, Carmen, Soledad, Diego, Ludoviko…).
- **Control de velocidad y tono** independientes (0.5× a 2×).
- **Control de volumen** con post-procesado mediante `ffmpeg`.
- **Selección de idioma avanzada** (Español, Inglés, Francés, etc.) para voces multiidioma.
- **Caché de audio SHA-256** con evicción LRU (500 MB / 1000 archivos) para acelerar generaciones repetidas.

### Expresiones y frases
- Menú **dinámico** de sonidos (risa, tos, suspiro, etc.) y frases (saludos, disculpas, sorpresa…) extraído del archivo `.gde` de cada voz.
- Inserción con un clic en el cursor.
- **Pausas personalizadas** con precisión de 120 ms (unidad nativa de Loquendo `\pause`).

### Pronunciaciones personalizadas
- Editor de **lexicones** para corregir cómo se pronuncian palabras (ej. *Minecraft → Maincraft*).
- Reemplazo por palabra completa (regex `\b`), sin afectar subcadenas.

### Importación de documentos
- **PDF** (con `pypdf`).
- **DOCX** (con `python-docx`).
- **EPUB** (con `ebooklib`).
- Extracción de texto y carga directa en el editor.

### Interfaz
- **Tema claro/oscuro/sistema** con libadwaita.
- **Colores personalizables** por voz.
- **Layout responsivo** con `Adw.WrapBox` y breakpoints.
- **Reproductor integrado** con GStreamer (Play/Pausa/Stop).
- **Menú contextual** en el editor (cortar/copiar/pegar/pausa).
- **Icono propio** en el menú de aplicaciones, dock, AboutWindow y notificaciones.
- **Cierre limpio**: mata procesos Wine residuales con `wineserver -k`.

### Instalador y desinstalador
- **Instalador gráfico** con Zenity. Auto-relanzado en terminal si se abre desde el gestor de archivos.
- **Instala automáticamente** las dependencias (`wine`, `winetricks`, `ffmpeg`, `gtk4`, `libadwaita`, etc.).
- **Menú de opciones**: instalación completa, instalar solo voces extra, o desinstalar.
- **Desinstalador completo** que borra el WINEPREFIX, config, caché, logs, lanzadores e icono, con confirmación previa.
- **Lanzadores `.desktop`** para el menú de aplicaciones.

---

## Requisitos

### Sistema operativo
- **Arch Linux** o cualquier derivada: **CachyOS**, **EndeavourOS**, **Manjaro**, **ArcoLinux**, etc.
- Cualquier distro con `pacman`.

> Para Debian/Ubuntu/Fedora: consulta la sección [Otras distribuciones](#otras-distribuciones).

### Dependencias del sistema
El instalador las instala automáticamente:
- `wine`, `winetricks`, `cabextract` — Motor de Loquendo y SAPI5.
- `zenity` — Ventanas del instalador.
- `p7zip`, `unzip`, `unrar` — Extracción de instaladores comprimidos.
- `ffmpeg` — Control de volumen.
- `python`, `python-gobject` — Aplicación y binding GTK.
- `python-pypdf`, `python-docx`, `python-ebooklib` — Importación de documentos.
- `gtk4`, `libadwaita`, `gst-python`, `gst-plugins-base`, `gst-plugins-good` — Interfaz y reproducción.
- `hicolor-icon-theme` — Tema base de iconos.

### Lo que **tú** debes aportar
- Los **instaladores originales de Loquendo** (Engine, Spanish, SDK, voces).
- Opcionalmente, un parche de licencia si lo posees (**Linuquendo no lo incluye ni lo ejecuta automáticamente**; el instalador solo pregunta si deseas aplicarlo).

---

## Instalación

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/linuquendo.git
cd linuquendo
```

### Paso 2 — Dar permisos de ejecución

```bash
chmod +x instalar.sh desinstalar.sh
```

### Paso 3 — Ejecutar el instalador

Doble clic sobre `instalar.sh` desde tu gestor de archivos, o desde una terminal:

```bash
./instalar.sh
```

> Si lo abres desde el gestor de archivos, se abrirá automáticamente una terminal porque el instalador necesita pedir la contraseña de sudo para instalar dependencias.

### Paso 4 — Seguir el asistente

1. **Dependencias**: se instalan automáticamente.
2. **Detección previa**: si ya hay una instalación, ofrecerá desinstalarla primero.
3. **Menú principal**: elige **Instalación completa**.
4. **Ruta de instalación**: por defecto `~/linuquendo_env` (crea `$CARPETA/linuquendo_env`).
5. **Archivos de Loquendo**: selecciona la carpeta (o `.zip`/`.rar`) con los instaladores.
6. **Instalación visible**: se abrirán las ventanas de Windows; complétalas una a una.
   - `Engine.exe` → Motor.
   - `Spanish.exe` → Paquete de idioma.
   - `SDK.exe` → Necesario para `TTSFileGenerator.exe`.
   - `Patch.exe` → Opcional, solo si lo posees.
   - Voces → Selecciona las que quieras instalar.
7. **Lanzador**: acepta si quieres acceso directo en el menú.

### Paso 5 — Ejecutar Linuquendo

Desde el menú de aplicaciones (**Linuquendo TTS**) o por terminal:

```bash
~/linuquendo_env/linuquendo_app/gui/linuquendo-gui
```

---

## Desinstalación

Tres formas equivalentes:

1. Menú de aplicaciones → **Desinstalar Linuquendo**.
2. Terminal:
   ```bash
   ~/linuquendo_env/linuquendo_app/desinstalar.sh
   ```
3. Re-ejecutar el instalador y elegir **Desinstalar Linuquendo**.

El desinstalador pide confirmación y muestra un resumen de todo lo que va a borrar:

- WINEPREFIX (motor + voces + app).
- `~/.config/linuquendo/` (preferencias, colores, lexicones).
- `~/.cache/linuquendo/` (caché de audio).
- `~/.local/share/linuquendo/` (logs).
- Lanzadores `.desktop`.
- Icono del tema hicolor.

---

## Uso

### Reproducción básica

1. Escribe o pega texto en el área central.
2. Selecciona la voz en el desplegable.
3. Ajusta velocidad, tono y volumen.
4. Pulsa **Reproducir**.
5. Si tienes texto seleccionado, solo se lee la selección. Si no, se lee todo.

### Insertar expresiones

- Menú **Insertar** → **Expresiones** → Sonidos / Frases.
- O clic derecho en el editor → **Insertar pausa personalizada…**.

### Pausas

- Menú **Insertar** → **Insertar pausa personalizada…**.
- Opciones rápidas: 120, 240, 480, 1000 ms.
- Personalizado: cualquier valor entre 120 y 10000 ms (se redondea al múltiplo de 120 ms).

### Lexicones

- Menú **Ver** → **Editor de Lexicones**.
- Añade pares palabra → pronunciación.
- Se aplican automáticamente antes de enviar al motor.

### Exportar WAV

- Menú **Archivo** → **Exportar WAV…**.
- Selecciona frecuencia de muestreo (16 kHz a 48 kHz) y canales (mono/estéreo).
- Guarda el archivo donde quieras.

### Importar documentos

- Menú **Archivo** → **Importar desde PDF / DOCX / EPUB…**.

---

## Capturas

> (Sustituye estas rutas por capturas reales cuando las tengas. Formato sugerido: PNG, 1920×1080, tema oscuro y claro.)

| Ventana principal | Expresiones |
|---|---|
| `docs/screenshots/main-dark.png` | `docs/screenshots/expressions.png` |

| Preferencias | Lexicones |
|---|---|
| `docs/screenshots/preferences.png` | `docs/screenshots/lexicon.png` |

---

## Configuración

### Archivos de configuración

| Archivo | Propósito |
|---|---|
| `~/.config/linuquendo/config.json` | Rutas del WINEPREFIX y la app. |
| `~/.config/linuquendo/preferences.json` | Tema, idioma, volumen. |
| `~/.config/linuquendo/voices_colors.json` | Colores por voz. |
| `~/.config/linuquendo/pronunciations.json` | Lexicones. |
| `~/.cache/linuquendo/audio/` | Caché de WAVs. |
| `~/.local/share/linuquendo/linuquendo.log` | Log de la aplicación. |

### Variables de entorno

- `WINEPREFIX` — Se lee de `config.json`; el lanzador la exporta.
- `WINEDEBUG=-all` — Silencia los logs de Wine.

---

## ❓ Preguntas frecuentes

**¿Necesito tener Loquendo instalado en Windows antes?**
No. Linuquendo instala el motor de Windows dentro de Wine desde cero. Solo necesitas los instaladores originales (`.exe`).

**¿Funciona con otras voces (eSpeak, RHVoice, Piper)?**
No todavía. Está en el roadmap. Linuquendo actualmente solo soporta el motor de Loquendo.

**¿Necesito el parche de licencia?**
Depende de tu copia de Loquendo. El instalador no incluye ningún parche; si tienes uno, te preguntará si quieres aplicarlo, y tú decides.

**¿Por qué el instalador me pide la contraseña de sudo?**
Para instalar dependencias del sistema (`wine`, `gtk4`, etc.) vía `pacman`. Si ya las tienes, puedes saltarte ese paso con:

```bash
./instalar.sh --skip-deps
```

**¿Puedo usar el motor en otra distro que no sea Arch?**
Sí, pero tendrás que instalar las dependencias manualmente con tu gestor de paquetes y luego ejecutar `./instalar.sh --skip-deps`.

**El motor falla con "Error en TTSFileGenerator: None"**
Suele pasar si en **Preferencias → Idioma** elegiste un idioma cuyo paquete no está instalado. Vuelve a dejarlo en **Predeterminado**.

**La app se cierra al iniciar**
Revisa el log en `~/.local/share/linuquendo/linuquendo.log`. Las causas más comunes son:
- WINEPREFIX inválido (revisa `~/.config/linuquendo/config.json`).
- Falta alguna dependencia de GStreamer.
- El motor de Loquendo no está instalado.

**¿Cómo limpio el caché de audio?**
**Preferencias → Caché de audio → Limpiar caché de audio**.

---

## Solución de problemas

| Síntoma | Solución |
|---|---|
| El audio no se reproduce | Verifica `gst-python` y `gst-plugins-good`. Revisa el log. |
| Las tildes no se ven bien | El `.gde` de la voz puede estar en UTF-8 o CP1252; el parser intenta ambas. |
| Procesos de Wine residuales | Ejecuta `wineserver -k` o cierra la app correctamente. |
| El layout se corta | El tamaño mínimo es 600×450. Usa `Adw.WrapBox`. |
| Error al importar PDF/DOCX/EPUB | Instala `python-pypdf`, `python-docx`, `python-ebooklib`. |
| `Icon=linuquendo` no aparece | Ejecuta `gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor/`. |

---

## Roadmap

### v0.1.0 (actual)
- [x] Instalador y desinstalador gráficos.
- [x] Motor de Loquendo bajo Wine.
- [x] Expresiones y frases.
- [x] Lexicones.
- [x] Pausas personalizadas.
- [x] Importación PDF/DOCX/EPUB.
- [x] Control de volumen.
- [x] Caché de audio.
- [x] Icono propio.

### v0.2.0
- [ ] PKGBUILD para AUR.
- [ ] Botones de énfasis (sintaxis de Loquendo por confirmar).
- [ ] Soporte para Debian/Ubuntu/Fedora.

### v0.3.0
- [ ] Integración con voces libres (eSpeak NG, RHVoice, Piper).
- [ ] Modo SSML real (si `TTSFileGenerator.exe` lo soporta en otra modalidad).

### Backlog
- [ ] Hover para previsualizar expresiones.
- [ ] Editor visual de prosodia.
- [ ] Tests unitarios.
- [ ] Traducción de la interfaz a inglés.

---

## 🤝 Contribuir

Las contribuciones son bienvenidas. Antes de abrir un PR:

1. Abre un *issue* describiendo qué quieres cambiar.
2. Respeta el estilo del código existente (4 espacios, nombres en español en backend, comentarios claros).
3. Prueba los cambios en una instalación limpia.
4. Actualiza el `README.md` si tu cambio afecta al usuario.

### Reportar bugs

Abre un *issue* con:
- Versión de Linuquendo.
- Distro y versión de Python.
- Pasos para reproducir.
- Fragmento del log (`~/.local/share/linuquendo/linuquendo.log`).

### Pull requests

- Una rama por *feature*: `feature/enfasis`, `fix/icono-dock`.
- Commits atómicos con mensajes claros.
- No incluyas binarios ni instaladores de Loquendo en el PR.

---

## 📄 Licencia

Linuquendo es software libre bajo la **GNU General Public License v3.0**. Consulta `LICENSE` para más detalles.

> Linuquendo no es una reimplementación de Loquendo. Es una capa de automatización sobre un motor propietario que el usuario debe poseer legalmente.

---

## Créditos

- **Loquendo S.p.A.** por el motor TTS original.
- **Wine** por hacer posible ejecutar software Windows en Linux.
- **GNOME** por GTK4 y libadwaita.
- Comunidad de Loquendo en español por preservar el motor.

---

## 💖 Apoya el proyecto

Linuquendo es y será siempre software libre. Si te resulta útil y quieres apoyar su desarrollo, puedes hacerlo por cualquiera de estas vías:

<div align="center">

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Inv%C3%ADtame%20a%20un%20caf%C3%A9-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/thezeusplayer24)
[![PayPal](https://img.shields.io/badge/PayPal-Donar-00457C?logo=paypal&logoColor=white)](mailto:thezeusplayer@protonmail.com)

</div>

> Las donaciones son voluntarias y se destinan a mantener el proyecto (tiempo de desarrollo, pruebas y costes de infraestructura). Nunca incluyen Loquendo, voces, instaladores ni parches. Linuquendo seguirá siendo software libre siempre.

Otras formas de apoyar sin gastar dinero:

- ⭐ Dale una estrella al repo.
- 🐛 Reporta bugs.
- 📝 Mejora la documentación.
- 🌍 Traduce la interfaz.
- 🗣️ Comparte el proyecto con quien le pueda interesar.

<div align="center">

**Hecho con ❤️ por y para la comunidad de Loquendo.**

*Linuquendo no está afiliado, respaldado ni patrocinado por Loquendo S.p.A. ni por sus distribuidores.*

</div>
