#!/usr/bin/env bash
# Linuquendo - Instalador Gráfico Completo

# --- Verificar que se está ejecutando con bash ---
if [ -z "$BASH_VERSION" ]; then
    echo "Error: este script requiere bash, no sh. Ejecútalo con: bash $0"
    exit 1
fi

# --- AUTO-RELANZAR EN TERMINAL SI NO HAY TTY ---
# Si el script se lanza desde un gestor de archivos (sin terminal),
# lo reabrimos dentro de una terminal para que sudo funcione y los
# mensajes sean visibles.
if [ ! -t 0 ] && [ ! -t 1 ]; then
    SELF_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

    TERMINAL=""
    for t in x-terminal-emulator gnome-terminal konsole xfce4-terminal mate-terminal tilix kitty alacritty wezterm foot xterm; do
        if command -v "$t" &>/dev/null; then
            TERMINAL="$t"
            break
        fi
    done

    if [ -z "$TERMINAL" ]; then
        MSG="No se pudo abrir una terminal automáticamente.\n\nEste instalador necesita ejecutarse en una terminal para pedir la contraseña de administrador.\n\nAbre una terminal y ejecuta:\n\n<b>bash $SELF_PATH</b>"
        if command -v zenity &>/dev/null; then
            zenity --error --title="Linuquendo - Error" --text="$MSG" --width=600
        else
            echo -e "$MSG" >&2
        fi
        exit 1
    fi

    # Comando escapado (para terminales que exigen un único string, como xfce4-terminal)
    ESCAPED_CMD=""
    for arg in bash "$SELF_PATH" "$@"; do
        ESCAPED_CMD+="$(printf '%q' "$arg") "
    done
    ESCAPED_CMD="${ESCAPED_CMD% }"

    case "$TERMINAL" in
        gnome-terminal|mate-terminal|tilix)
            exec "$TERMINAL" -- bash "$SELF_PATH" "$@"
            ;;
        konsole)
            exec "$TERMINAL" -e bash "$SELF_PATH" "$@"
            ;;
        xfce4-terminal)
            exec "$TERMINAL" -e "$ESCAPED_CMD"
            ;;
        kitty|alacritty|wezterm|foot)
            exec "$TERMINAL" bash "$SELF_PATH" "$@"
            ;;
        *)
            exec "$TERMINAL" -e bash "$SELF_PATH" "$@"
            ;;
    esac
fi

# --- Configuración de rutas y logs ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/.local/share/linuquendo"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/instalacion.log"
exec > >(tee -a "$LOG_FILE") 2>&1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# --- Funciones de ayuda ---
mostrar_error() {
    echo -e "${RED}[ERROR] $1${NC}"
    if command -v zenity &> /dev/null; then
        zenity --error --title="Linuquendo - Error" --text="$1" --width=500
    fi
    exit 1
}

cancelar_instalacion() {
    zenity --question --title="Cancelar Instalación" \
        --text="¿Estás seguro de que deseas cancelar la instalación?" \
        --ok-label="Sí, cancelar" --cancel-label="No, continuar" --width=450
    if [ $? -eq 0 ]; then
        pkill -f "wine" 2>/dev/null || true
        pkill -f "winetricks" 2>/dev/null || true
        wineserver -k 2>/dev/null || true
        zenity --info --title="Instalación Cancelada" --text="La instalación ha sido cancelada." --width=400
        exit 0
    fi
}

mensaje_paso() {
    zenity --question --title="$1" --text="$2" \
        --ok-label="Continuar" --cancel-label="Cancelar instalación" --width=550
    if [ $? -ne 0 ]; then cancelar_instalacion; fi
}

extraer_comprimido() {
    local archivo="$1"; local destino="$2"; local exito=1
    if command -v 7z &> /dev/null; then 7z x "$archivo" -o"$destino" -y &> /dev/null && exito=0; fi
    if [ $exito -ne 0 ] && [[ "$archivo" == *.zip ]] && command -v unzip &> /dev/null; then unzip -q "$archivo" -d "$destino" && exito=0; fi
    if [ $exito -ne 0 ] && [[ "$archivo" == *.rar ]] && command -v unrar &> /dev/null; then unrar x -inul "$archivo" "$destino/" && exito=0; fi
    if [ $exito -ne 0 ]; then mostrar_error "No se pudo extraer: $archivo"; fi
}

buscar_engine_inteligente() {
    local ruta="$1"; local encontrado
    encontrado=$(find "$ruta" -iname "Engine.exe" -print -quit 2>/dev/null)
    if [ -n "$encontrado" ]; then dirname "$encontrado"; return 0; fi
    local comprimidos=$(find "$ruta" -type f \( -iname "*.zip" -o -iname "*.rar" \) 2>/dev/null)
    if [ -n "$comprimidos" ]; then
        local temp_dir=$(mktemp -d)
        while IFS= read -r archivo; do extraer_comprimido "$archivo" "$temp_dir"; done <<< "$comprimidos"
        encontrado=$(find "$temp_dir" -iname "Engine.exe" -print -quit 2>/dev/null)
        if [ -n "$encontrado" ]; then dirname "$encontrado"; return 0; fi
    fi
    return 1
}

# --- 1. DETECCIÓN DE DISTRIBUCIÓN Y VERIFICACIÓN DE DEPENDENCIAS ---
echo -e "${GREEN}=== Verificando Sistema y Dependencias ===${NC}"

if ! command -v pacman &> /dev/null; then
    mostrar_error "Este instalador está diseñado para distribuciones basadas en Arch Linux (CachyOS, EndeavourOS, Manjaro, etc.).\n\nTu sistema no usa 'pacman'.\n\nConsulta el README para instalar las dependencias manualmente y luego ejecuta el instalador con --skip-deps."
fi

# Comprobar si el usuario quiere saltar la instalación de dependencias
SKIP_DEPS=0
for arg in "$@"; do
    if [ "$arg" = "--skip-deps" ]; then
        SKIP_DEPS=1
    fi
done

if [ $SKIP_DEPS -eq 0 ]; then
    zenity --info --title="Dependencias" \
        --text="Se instalarán las dependencias necesarias para Linuquendo.\n\n<b>Esto puede pedirte la contraseña de administrador.</b>" \
        --width=450
    echo -e "${YELLOW}Instalando dependencias del sistema...${NC}"
    sudo pacman -S --needed --noconfirm \
        wine winetricks zenity cabextract p7zip unzip unrar ffmpeg \
        python python-gobject python-pypdf python-docx python-ebooklib \
        gtk4 libadwaita gst-python gst-plugins-base gst-plugins-good \
        hicolor-icon-theme \
        2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        mostrar_error "No se pudieron instalar todas las dependencias.\n\nRevisa el log en:\n$LOG_FILE"
    fi
    echo -e "${GREEN}Dependencias instaladas correctamente.${NC}"
else
    echo -e "${YELLOW}Saltando instalación de dependencias (--skip-deps).${NC}"
fi

# Verificación final de dependencias críticas
for cmd in wine winetricks zenity python3; do
    if ! command -v $cmd &> /dev/null; then
        mostrar_error "La dependencia '$cmd' no se encontró. Abortando."
    fi
done

# --- 2. DETECTAR INSTALACIÓN PREVIA ---
CONFIG_FILE="$HOME/.config/linuquendo/config.json"
if [ -f "$CONFIG_FILE" ]; then
    RESPUESTA=$(zenity --question --title="Linuquendo ya instalado" \
        --text="Se ha detectado una instalación previa de Linuquendo.\n\n¿Deseas desinstalarla primero y hacer una instalación limpia?" \
        --ok-label="Desinstalar y reinstalar" \
        --cancel-label="Cancelar" --width=500)
    if [ $? -ne 0 ]; then
        exit 0
    fi
    # Ejecutar el desinstalador (desde el proyecto o desde la instalación previa)
    if [ -x "$PROJECT_DIR/desinstalar.sh" ]; then
        "$PROJECT_DIR/desinstalar.sh"
    else
        mostrar_error "No se encontró el desinstalador. No se puede continuar con una instalación limpia."
    fi
fi

# --- 3. MENÚ PRINCIPAL ---
OPCION_PRINCIPAL=$(zenity --list --radiolist --title="Linuquendo" \
    --text="¿Qué deseas hacer?" --column="" --column="Opción" \
    TRUE "Instalación completa (Motor + SDK + Voces + App)" \
    FALSE "Instalar solo voces extra (Requiere motor ya instalado)" \
    FALSE "Desinstalar Linuquendo (Eliminar todo)" \
    --height=300 --width=500)
if [ -z "$OPCION_PRINCIPAL" ]; then exit 0; fi

# --- Opción: Desinstalar ---
if [[ "$OPCION_PRINCIPAL" == *"Desinstalar"* ]]; then
    if [ -x "$PROJECT_DIR/desinstalar.sh" ]; then
        exec "$PROJECT_DIR/desinstalar.sh"
    else
        mostrar_error "No se encontró el desinstalador en el proyecto."
    fi
fi

WINEPREFIX=""
LOQUENDO_FILES=""

if [[ "$OPCION_PRINCIPAL" == *"completa"* ]]; then
    mensaje_paso "Paso 1: Bienvenido" "<b>Advertencia:</b> Este es solo un instalador del programa de TTS Director 7. Necesitarás los ejecutables de instalación de Windows."
    mensaje_paso "Paso 2: Ruta de instalación" "Selecciona la ruta donde quieres que se instale el programa (el entorno y la app)."

    while true; do
        CARPETA_PADRE=$(zenity --file-selection --directory --title="Elige una carpeta para guardar el programa" --filename="$HOME/" --width=600)
        if [ -z "$CARPETA_PADRE" ]; then cancelar_instalacion; continue; fi
        WINEPREFIX="$CARPETA_PADRE/linuquendo_env"
        if zenity --question --title="Confirmar carpeta" --text="El programa se instalará en:\n<b>$WINEPREFIX</b>\n\n¿Es correcto?" --ok-label="Sí" --cancel-label="No" --width=500; then break; fi
    done

    mensaje_paso "Paso 3: Archivos" "Selecciona cómo tienes los archivos de Director TTS."
    OPCION_ARCH=$(zenity --list --radiolist --title="Archivos" --text="¿Cómo tienes los archivos?" --column="" --column="Opción" TRUE "Carpeta descomprimida" FALSE "Archivo comprimido (.zip o .rar)" --height=200 --width=450)
    if [ -z "$OPCION_ARCH" ]; then cancelar_instalacion; fi

    while true; do
        if [[ "$OPCION_ARCH" == *"Carpeta"* ]]; then
            RUTA_SEL=$(zenity --file-selection --directory --title="Selecciona la carpeta con los archivos" --width=600)
            if [ -z "$RUTA_SEL" ]; then cancelar_instalacion; continue; fi
            LOQUENDO_FILES=$(buscar_engine_inteligente "$RUTA_SEL")
        else
            RUTA_SEL=$(zenity --file-selection --title="Selecciona el archivo .zip o .rar" --file-filter="Archivos comprimidos | *.zip *.rar" --width=600)
            if [ -z "$RUTA_SEL" ]; then cancelar_instalacion; continue; fi
            TEMP_DIR=$(mktemp -d)
            extraer_comprimido "$RUTA_SEL" "$TEMP_DIR"
            LOQUENDO_FILES=$(buscar_engine_inteligente "$TEMP_DIR")
        fi
        if [ -n "$LOQUENDO_FILES" ] && [ -f "$LOQUENDO_FILES/Engine.exe" ]; then break; fi
        zenity --error --title="No encontrado" --text="No se encontró Engine.exe. Intenta de nuevo." --width=400
    done

    export WINEPREFIX
    export WINEDEBUG=-all
    if [ -d "$WINEPREFIX" ]; then
        rm -rf "$WINEPREFIX"
    fi

    (
    echo "5" ; echo "# Creando prefix de Wine..."
    wineboot --init &> /dev/null
    echo "15" ; echo "# Esperando a que el prefix esté listo..."
    sleep 3
    echo "25" ; echo "# Instalando SAPI5 (puede tardar varios minutos)..."
    WINETRICKS_FORCE=1 winetricks -q speechsdk &> /dev/null || true
    echo "100"
    ) | zenity --progress --title="Preparando entorno" --text="Creando prefix e instalando SAPI5..." --percentage=0 --auto-close --cancel-label="Cancelar"
    if [ $? -ne 0 ]; then pkill -f wine; wineserver -k 2>/dev/null; exit 0; fi

    zenity --info --title="Instalador del Motor" --text="Se abrirá el instalador del motor de Loquendo.\n\nHaz clic en 'Siguiente' / 'Aceptar' / 'Instalar' hasta que termine." --width=500
    wine "$LOQUENDO_FILES/Engine.exe"
    if [ ! -d "$WINEPREFIX/drive_c/Program Files (x86)/Loquendo/LTTS7/bin" ]; then
        mostrar_error "El motor no se instaló correctamente. Revisa el log: $LOG_FILE"
    fi

    zenity --info --title="Instalador del Idioma" --text="Se abrirá el instalador del paquete de idioma español.\n\nHaz clic en 'Siguiente' / 'Aceptar' / 'Instalar' hasta que termine." --width=500
    wine "$LOQUENDO_FILES/Spanish.exe"

    zenity --info --title="Instalador del SDK" --text="Se abrirá el instalador del SDK (necesario para TTSFileGenerator.exe).\n\nHaz clic en 'Siguiente' / 'Aceptar' / 'Instalar' hasta que termine." --width=500
    wine "$LOQUENDO_FILES/SDK.exe"

    PATCH_FILE="$LOQUENDO_FILES/Patch.exe"
    if [ -f "$PATCH_FILE" ]; then
        zenity --info --title="Parche" --text="Se abrirá el parche. Selecciona la MAC y haz clic en 'activate' hasta que diga 'OK'.\n\nLinuquendo no se hace responsable de su uso." --width=500
        wine "$PATCH_FILE"
    fi

    VOCES_ENCONTRADAS=()
    while IFS= read -r exe; do
        nombre=$(basename "$exe")
        if [[ "$nombre" != "Engine.exe" && "$nombre" != "Spanish.exe" && "$nombre" != "SDK.exe" && "$nombre" != "Patch.exe" && "$nombre" != "spchapi.exe" ]]; then
            VOCES_ENCONTRADAS+=("$exe")
        fi
    done < <(find "$LOQUENDO_FILES" -maxdepth 1 -iname "*.exe" 2>/dev/null)

    if [ ${#VOCES_ENCONTRADAS[@]} -gt 0 ]; then
        LISTA_ZENITY=()
        for voz in "${VOCES_ENCONTRADAS[@]}"; do LISTA_ZENITY+=(TRUE "$(basename "$voz")"); done
        VOCES_SELECCIONADAS=$(zenity --list --checklist --title="Voces encontradas" --text="Selecciona las voces a instalar:" --column="" --column="Voz" "${LISTA_ZENITY[@]}" --height=300 --width=400 --separator="|")
        if [ -n "$VOCES_SELECCIONADAS" ]; then
            IFS='|' read -r -a VOCES_A_INSTALAR <<< "$VOCES_SELECCIONADAS"
            for voz_nombre in "${VOCES_A_INSTALAR[@]}"; do
                zenity --info --title="Instalando $voz_nombre" --text="Se abrirá el instalador de $voz_nombre.\n\nHaz clic en 'Siguiente' / 'Aceptar' / 'Instalar' hasta que termine." --width=500
                for voz_path in "${VOCES_ENCONTRADAS[@]}"; do
                    if [ "$(basename "$voz_path")" = "$voz_nombre" ]; then
                        wine "$voz_path"
                        break
                    fi
                done
            done
        fi
    fi

    (
    echo "20" ; echo "# Copiando DLLs a syswow64..."
    BIN_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Loquendo/LTTS7/bin"
    SYSWOW64="$WINEPREFIX/drive_c/windows/syswow64"
    for dll in LTTS7Util.dll LoqTTS7.dll LTTS7DB.dll LTTS7XML.dll LTTS7Codec210.dll \
               LTTS7Morphyzer.dll LTTS7LanguageGuesser.dll LTTS7AudioFile.dll \
               LTTS7AudioBoard.dll LTTS7jni.dll; do
        if [ -f "$BIN_DIR/$dll" ]; then
            cp "$BIN_DIR/$dll" "$SYSWOW64/" 2>/dev/null || true
        fi
    done
    cp "$BIN_DIR/LoqTTS7.dll" "$BIN_DIR/LOQTTS7.dll" 2>/dev/null || true
    echo "100"
    ) | zenity --progress --title="Copiando DLLs" --text="Copiando dependencias del motor..." --percentage=0 --auto-close
else
    # Solo voces extra
    zenity --info --title="Voces Extra" --text="Selecciona la carpeta donde está instalado el entorno de Linuquendo." --width=450
    while true; do
        CARPETA_PADRE=$(zenity --file-selection --directory --title="Selecciona la carpeta del entorno" --filename="$HOME/" --width=600)
        if [ -z "$CARPETA_PADRE" ]; then exit 0; fi
        WINEPREFIX="$CARPETA_PADRE"
        if [ -d "$WINEPREFIX/drive_c" ]; then break; fi
        zenity --error --title="No válido" --text="Esa carpeta no contiene un entorno de Linuquendo." --width=400
    done
    export WINEPREFIX
fi

APP_DIR="$WINEPREFIX/linuquendo_app"
mkdir -p "$APP_DIR"
cp -r "$PROJECT_DIR/src" "$APP_DIR/"
cp -r "$PROJECT_DIR/gui" "$APP_DIR/"
cp -r "$PROJECT_DIR/assets" "$APP_DIR/" 2>/dev/null || true

# --- ICONO: Instalar el SVG en el tema de iconos del usuario ---
# Se copia a ~/.local/share/icons/hicolor/scalable/apps/ para que el .desktop
# pueda referenciarlo solo por nombre (Icon=linuquendo) y funcione en cualquier
# tamaño (dock, menú, notificaciones, AboutWindow, etc.).
ICON_SRC="$APP_DIR/assets/icons/hicolor/scalable/apps/linuquendo.svg"
ICON_DST_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_DST="$ICON_DST_DIR/linuquendo.svg"

if [ -f "$ICON_SRC" ]; then
    mkdir -p "$ICON_DST_DIR"
    cp -f "$ICON_SRC" "$ICON_DST"
    if command -v gtk-update-icon-cache &> /dev/null; then
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor/" 2>/dev/null || true
    fi
    echo "Icono instalado en: $ICON_DST"
else
    echo "Aviso: no se encontró $ICON_SRC. El icono no se instalará."
fi

# --- Copiar el desinstalador a la instalación ---
if [ -f "$PROJECT_DIR/desinstalar.sh" ]; then
    cp "$PROJECT_DIR/desinstalar.sh" "$APP_DIR/desinstalar.sh"
    chmod +x "$APP_DIR/desinstalar.sh"
    echo "Desinstalador copiado a: $APP_DIR/desinstalar.sh"
fi

CONFIG_DIR="$HOME/.config/linuquendo"
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/config.json" <<EOF
{"wineprefix": "$WINEPREFIX", "app_dir": "$APP_DIR"}
EOF

# Precalentamiento temporal
zenity --info --title="Optimizando" --text="Preparando el motor de voz para la primera ejecución. Esto puede tardar unos segundos..." --width=450 &
ZENITY_PID=$!
export WINEPREFIX
export WINEDEBUG=-all
python3 -c "
import sys
sys.path.insert(0, '$APP_DIR')
from src.backend import list_installed_voices
voces = list_installed_voices(force_refresh=True)
print('Voces detectadas:', voces)
" 2>/dev/null || true
wineserver -k 2>/dev/null || true
kill $ZENITY_PID 2>/dev/null || true

chmod +x "$APP_DIR/gui/linuquendo-gui"

# --- Lanzadores en el menú de aplicaciones ---
if zenity --question --title="Lanzador" --text="¿Deseas crear un acceso directo en el menú de aplicaciones?" --ok-label="Sí" --cancel-label="No" --width=450; then
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/linuquendo.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Linuquendo TTS
Comment=Generador de voz con el motor de Loquendo
Exec=$APP_DIR/gui/linuquendo-gui
Icon=linuquendo
Terminal=false
Categories=AudioVideo;Audio;Utility;
EOF
    # Lanzador de desinstalación
    cat > "$DESKTOP_DIR/linuquendo-desinstalar.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desinstalar Linuquendo
Comment=Elimina completamente Linuquendo del sistema
Exec=$APP_DIR/desinstalar.sh
Icon=edit-delete-symbolic
Terminal=false
Categories=Utility;
EOF
    # Refrescar el índice de aplicaciones para que aparezcan al instante
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
    zenity --info --title="Lanzadores Creados" --text="Linuquendo y 'Desinstalar Linuquendo' aparecerán en tu menú de aplicaciones." --width=450
else
    zenity --info --title="Ejecutable" --text="Puedes ejecutar Linuquendo manualmente con:\n<b>$APP_DIR/gui/linuquendo-gui</b>\n\nY desinstalarlo con:\n<b>$APP_DIR/desinstalar.sh</b>" --width=500
fi

# --- Mensaje final claro ---
zenity --info --title="¡Todo Listo!" \
    --text="El proceso ha finalizado.\n\n<b>Log:</b> $LOG_FILE\n<b>Entorno:</b> $WINEPREFIX\n\n<b>Para abrir Linuquendo:</b>\n  $APP_DIR/gui/linuquendo-gui\n\n<b>Para desinstalar Linuquendo:</b>\n  $APP_DIR/desinstalar.sh\n  (o vuelve a ejecutar este instalador y elige 'Desinstalar Linuquendo')" \
    --width=600
