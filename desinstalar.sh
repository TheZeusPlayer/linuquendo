#!/usr/bin/env bash
# Linuquendo - Desinstalador Completo
# Elimina todo rastro de Linuquendo del sistema.

# --- Configuración de rutas ---
CONFIG_DIR="$HOME/.config/linuquendo"
CONFIG_FILE="$CONFIG_DIR/config.json"
CACHE_DIR="$HOME/.cache/linuquendo"
LOG_DIR="$HOME/.local/share/linuquendo"
DESKTOP_FILE="$HOME/.local/share/applications/linuquendo.desktop"
DESKTOP_UNINSTALL_FILE="$HOME/.local/share/applications/linuquendo-desinstalar.desktop"
# ── ICONO ── ruta del SVG instalado en el tema del usuario
ICON_FILE="$HOME/.local/share/icons/hicolor/scalable/apps/linuquendo.svg"

# Log temporal (vivirá en /tmp porque vamos a borrar LOG_DIR)
LOG_FILE=$(mktemp /tmp/linuquendo_desinstalacion_XXXXXX.log)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mostrar_error() {
    echo -e "${RED}[ERROR] $1${NC}"
    if command -v zenity &> /dev/null; then
        zenity --error --title="Linuquendo - Error" --text="$1" --width=500
    fi
    exit 1
}

# --- Verificar zenity ---
if ! command -v zenity &> /dev/null; then
    echo "Error: Zenity no está instalado. No se puede mostrar la interfaz gráfica."
    echo "Puedes desinstalar manualmente borrando estas rutas:"
    echo "  - $CONFIG_DIR"
    echo "  - $CACHE_DIR"
    echo "  - $LOG_DIR"
    echo "  - $DESKTOP_FILE"
    echo "  - $DESKTOP_UNINSTALL_FILE"
    echo "  - $ICON_FILE"
    echo "  - Y la carpeta del WINEPREFIX que hayas elegido durante la instalación."
    exit 1
fi

# --- 1. Leer configuración o pedir la ruta manualmente ---
WINEPREFIX=""
APP_DIR=""

if [ -f "$CONFIG_FILE" ]; then
    WINEPREFIX=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['wineprefix'])" 2>/dev/null || echo "")
    APP_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['app_dir'])" 2>/dev/null || echo "")
else
    # Fallback: no hay config.json. Preguntar al usuario si quiere borrar el WINEPREFIX a mano.
    zenity --question --title="Configuración no encontrada" \
        --text="No se encontró el archivo de configuración de Linuquendo.\n\nEsto puede pasar si ya borraste la carpeta <b>~/.config/linuquendo</b>.\n\n¿Deseas seleccionar manualmente la carpeta del entorno de Wine para eliminarla?" \
        --ok-label="Sí, seleccionar carpeta" \
        --cancel-label="No, solo limpiar config/caché/logs" \
        --width=500
    if [ $? -eq 0 ]; then
        CARPETA_SEL=$(zenity --file-selection --directory --title="Selecciona la carpeta del entorno de Linuquendo (linuquendo_env)" --filename="$HOME/" --width=600)
        if [ -n "$CARPETA_SEL" ]; then
            WINEPREFIX="$CARPETA_SEL"
        fi
    fi
fi

# --- 2. Verificar si hay algo que borrar ---
if [ -z "$WINEPREFIX" ] && [ ! -d "$CONFIG_DIR" ] && [ ! -d "$CACHE_DIR" ] && [ ! -d "$LOG_DIR" ] && [ ! -f "$DESKTOP_FILE" ] && [ ! -f "$DESKTOP_UNINSTALL_FILE" ] && [ ! -f "$ICON_FILE" ]; then
    zenity --info --title="Linuquendo no encontrado" \
        --text="No se detectó ninguna instalación de Linuquendo en este sistema.\n\n¿Ya lo has desinstalado antes?" \
        --width=450
    exit 0
fi

# --- 3. Construir resumen de lo que se va a borrar ---
RESUMEN="Se eliminarán los siguientes componentes de Linuquendo:\n\n"
[ -n "$WINEPREFIX" ] && [ -d "$WINEPREFIX" ] && RESUMEN+="• Entorno Wine (motor + voces + app): $WINEPREFIX\n"
[ -n "$APP_DIR" ] && [ -d "$APP_DIR" ] && [ "$APP_DIR" != "$WINEPREFIX" ] && RESUMEN+="• Aplicación GUI: $APP_DIR\n"
[ -d "$CONFIG_DIR" ] && RESUMEN+="• Configuración (preferencias, colores, lexicones): $CONFIG_DIR\n"
[ -d "$CACHE_DIR" ] && RESUMEN+="• Caché de audio: $CACHE_DIR\n"
[ -d "$LOG_DIR" ] && RESUMEN+="• Logs de la aplicación: $LOG_DIR\n"
[ -f "$DESKTOP_FILE" ] && RESUMEN+="• Lanzador de Linuquendo: $DESKTOP_FILE\n"
[ -f "$DESKTOP_UNINSTALL_FILE" ] && RESUMEN+="• Lanzador de desinstalación: $DESKTOP_UNINSTALL_FILE\n"
# ── ICONO ── añadido al resumen
[ -f "$ICON_FILE" ] && RESUMEN+="• Icono del tema (hicolor): $ICON_FILE\n"

RESUMEN+="\n<b>Esta acción es irreversible.</b>\n\n¿Deseas continuar con la desinstalación completa?"

zenity --question --title="Desinstalar Linuquendo" \
    --text="$RESUMEN" \
    --ok-label="Sí, eliminar todo" \
    --cancel-label="Cancelar" \
    --width=600
if [ $? -ne 0 ]; then
    zenity --info --title="Cancelado" --text="La desinstalación ha sido cancelada." --width=400
    exit 0
fi

# --- 4. Iniciar log ---
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== Iniciando desinstalación de Linuquendo: $(date) ==="
echo ""

# --- 5. Detener procesos de Wine relacionados ---
echo -e "${YELLOW}[1/8] Deteniendo procesos de Wine...${NC}"
if [ -n "$WINEPREFIX" ] && [ -d "$WINEPREFIX" ]; then
    WINEPREFIX="$WINEPREFIX" wineserver -k 2>/dev/null || true
fi
pkill -f "python3.*linuquendo" 2>/dev/null || true
pkill -f "python3.*main.py" 2>/dev/null || true
sleep 1
echo "  ✔ Procesos detenidos."
echo ""

# --- 6. Eliminar el WINEPREFIX ---
echo -e "${YELLOW}[2/8] Eliminando entorno Wine (y app dentro)...${NC}"
if [ -n "$WINEPREFIX" ] && [ "$WINEPREFIX" != "/" ] && [ "$WINEPREFIX" != "$HOME" ] && [ -d "$WINEPREFIX" ]; then
    rm -rf "$WINEPREFIX"
    if [ -d "$WINEPREFIX" ]; then
        echo -e "${RED}  ✘ No se pudo eliminar completamente: $WINEPREFIX${NC}"
    else
        echo -e "${GREEN}  ✔ Eliminado: $WINEPREFIX${NC}"
    fi
else
    echo "  (Saltado: ruta inválida o no existe)"
fi
echo ""

# --- 7. Eliminar la app GUI si estaba fuera del WINEPREFIX ---
echo -e "${YELLOW}[3/8] Eliminando aplicación GUI (si estaba fuera del entorno)...${NC}"
if [ -n "$APP_DIR" ] && [ "$APP_DIR" != "/" ] && [ "$APP_DIR" != "$HOME" ] && [ -d "$APP_DIR" ]; then
    rm -rf "$APP_DIR"
    if [ -d "$APP_DIR" ]; then
        echo -e "${RED}  ✘ No se pudo eliminar: $APP_DIR${NC}"
    else
        echo -e "${GREEN}  ✔ Eliminado: $APP_DIR${NC}"
    fi
else
    echo "  (Ya eliminado con el WINEPREFIX o no existe)"
fi
echo ""

# --- 8. Eliminar configuración ---
echo -e "${YELLOW}[4/8] Eliminando configuración del usuario...${NC}"
if [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    if [ -d "$CONFIG_DIR" ]; then
        echo -e "${RED}  ✘ No se pudo eliminar: $CONFIG_DIR${NC}"
    else
        echo -e "${GREEN}  ✔ Eliminado: $CONFIG_DIR${NC}"
    fi
else
    echo "  (No existe)"
fi
echo ""

# --- 9. Eliminar caché de audio ---
echo -e "${YELLOW}[5/8] Eliminando caché de audio...${NC}"
if [ -d "$CACHE_DIR" ]; then
    rm -rf "$CACHE_DIR"
    if [ -d "$CACHE_DIR" ]; then
        echo -e "${RED}  ✘ No se pudo eliminar: $CACHE_DIR${NC}"
    else
        echo -e "${GREEN}  ✔ Eliminado: $CACHE_DIR${NC}"
    fi
else
    echo "  (No existe)"
fi
echo ""

# --- 10. Eliminar lanzadores del menú de aplicaciones ---
echo -e "${YELLOW}[6/8] Eliminando lanzadores del menú de aplicaciones...${NC}"
if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    [ -f "$DESKTOP_FILE" ] && echo -e "${RED}  ✘ No se pudo eliminar: $DESKTOP_FILE${NC}" || echo -e "${GREEN}  ✔ Eliminado: $DESKTOP_FILE${NC}"
else
    echo "  (Lanzador principal no existe)"
fi
if [ -f "$DESKTOP_UNINSTALL_FILE" ]; then
    rm -f "$DESKTOP_UNINSTALL_FILE"
    [ -f "$DESKTOP_UNINSTALL_FILE" ] && echo -e "${RED}  ✘ No se pudo eliminar: $DESKTOP_UNINSTALL_FILE${NC}" || echo -e "${GREEN}  ✔ Eliminado: $DESKTOP_UNINSTALL_FILE${NC}"
else
    echo "  (Lanzador de desinstalación no existe)"
fi
# Refrescar el índice de aplicaciones para que desaparezcan al instante
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi
echo ""

# --- 11. Eliminar icono del tema de iconos ── ICONO ──
echo -e "${YELLOW}[7/8] Eliminando icono del tema de iconos...${NC}"
if [ -f "$ICON_FILE" ]; then
    rm -f "$ICON_FILE"
    if [ -f "$ICON_FILE" ]; then
        echo -e "${RED}  ✘ No se pudo eliminar: $ICON_FILE${NC}"
    else
        echo -e "${GREEN}  ✔ Eliminado: $ICON_FILE${NC}"
    fi
    if command -v gtk-update-icon-cache &> /dev/null; then
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor/" 2>/dev/null || true
    fi
else
    echo "  (No existe)"
fi
echo ""

# --- 12. Eliminar logs ---
echo -e "${YELLOW}[8/8] Eliminando logs de la aplicación...${NC}"
if [ -d "$LOG_DIR" ]; then
    rm -rf "$LOG_DIR"
    if [ -d "$LOG_DIR" ]; then
        echo -e "${RED}  ✘ No se pudo eliminar: $LOG_DIR${NC}"
    else
        echo -e "${GREEN}  ✔ Eliminado: $LOG_DIR${NC}"
    fi
else
    echo "  (No existe)"
fi
echo ""

# --- 13. Verificación final ---
RESIDUALES=""
[ -n "$WINEPREFIX" ] && [ -d "$WINEPREFIX" ] && RESIDUALES+="• $WINEPREFIX\n"
[ -n "$APP_DIR" ] && [ -d "$APP_DIR" ] && RESIDUALES+="• $APP_DIR\n"
[ -d "$CONFIG_DIR" ] && RESIDUALES+="• $CONFIG_DIR\n"
[ -d "$CACHE_DIR" ] && RESIDUALES+="• $CACHE_DIR\n"
[ -d "$LOG_DIR" ] && RESIDUALES+="• $LOG_DIR\n"
[ -f "$DESKTOP_FILE" ] && RESIDUALES+="• $DESKTOP_FILE\n"
[ -f "$DESKTOP_UNINSTALL_FILE" ] && RESIDUALES+="• $DESKTOP_UNINSTALL_FILE\n"
# ── ICONO ── comprobar también el SVG residual
[ -f "$ICON_FILE" ] && RESIDUALES+="• $ICON_FILE\n"

if [ -z "$RESIDUALES" ]; then
    echo "=== Desinstalación completada con éxito ==="
    zenity --info --title="Desinstalación Completada" \
        --text="<b>Linuquendo ha sido eliminado completamente de tu sistema.</b>\n\nSe han borrado:\n• Motor y voces\n• Aplicación GUI\n• Configuración y preferencias\n• Caché de audio\n• Logs\n• Lanzadores del menú\n• Icono del tema de iconos\n\nPuedes borrar también esta carpeta del proyecto si ya no la necesitas." \
        --width=550
else
    echo "=== Desinstalación completada con advertencias ==="
    echo -e "Residuales:\n$RESIDUALES"
    zenity --warning --title="Desinstalación parcial" \
        --text="La mayoría de Linuquendo ha sido eliminado, pero algunos archivos no se pudieron borrar:\n\n$RESIDUALES\n\nRevisa el log para más detalles:\n$LOG_FILE" \
        --width=550
fi
