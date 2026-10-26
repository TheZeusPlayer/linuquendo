import os
import json
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, Gio

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from src.backend import (
        load_preferences, save_preferences,
        load_voice_colors, save_voice_colors,
        get_cache_info, clear_audio_cache,
        list_installed_voices,
    )
    from gui.lexicon import LexiconWindow
except ImportError:
    load_preferences = lambda: {"theme": "system", "language": "", "volume": 1.0}
    save_preferences = lambda x: False
    load_voice_colors = lambda: {}
    save_voice_colors = lambda x: False
    get_cache_info = lambda: (0, 0)
    clear_audio_cache = lambda: (0, 0)
    list_installed_voices = lambda: []
    LexiconWindow = None


def _format_size(bytes_val):
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} MB"


# Mnemónicos válidos para Loquendo (no códigos ISO)
LANGUAGES = [
    ("", "Predeterminado (idioma de la voz)"),
    ("spanish", "Español"),
    ("english", "Inglés"),
    ("french", "Francés"),
    ("german", "Alemán"),
    ("italian", "Italiano"),
    ("portuguese", "Portugués"),
    ("catalan", "Catalán"),
    ("galician", "Gallego"),
]


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, parent=None, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Preferencias")
        self.set_default_size(600, 650)
        self.set_transient_for(parent)
        self.set_modal(True)

        self.voice_colors = load_voice_colors()
        self.voices = list_installed_voices()
        self.prefs = load_preferences()

        self._build_ui()

    def _build_ui(self):
        page = Adw.PreferencesPage()
        page.set_title("Ajustes")
        page.set_icon_name("preferences-system-symbolic")

        # --- Sección: Apariencia ---
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title("Apariencia")
        appearance_group.set_description("Tema de la interfaz")

        theme_row = Adw.ComboRow()
        theme_row.set_title("Tema")
        theme_row.set_subtitle("Claro, oscuro o seguir al sistema")
        themes = Gtk.StringList.new(["Seguir al sistema", "Claro", "Oscuro"])
        theme_row.set_model(themes)
        theme_map = {"system": 0, "light": 1, "dark": 2}
        theme_row.set_selected(theme_map.get(self.prefs.get("theme", "system"), 0))
        theme_row.connect("notify::selected", self._on_theme_changed)
        appearance_group.add(theme_row)

        page.add(appearance_group)

        # --- Sección: Idioma por defecto (opción avanzada) ---
        lang_group = Adw.PreferencesGroup()
        lang_group.set_title("Idioma (Avanzado)")
        lang_group.set_description(
            "Forzar el idioma del motor puede hacer que la síntesis falle si el paquete de idioma no está instalado.\n"
            "Deja 'Predeterminado' para usar el idioma nativo de la voz (recomendado)."
        )

        lang_names = [name for code, name in LANGUAGES]
        lang_row = Adw.ComboRow()
        lang_row.set_title("Idioma por defecto")
        lang_row.set_subtitle("Solo para usuarios avanzados con paquetes de idioma instalados")
        lang_model = Gtk.StringList.new(lang_names)
        lang_row.set_model(lang_model)
        current_lang = self.prefs.get("language", "")
        lang_idx = 0
        for i, (code, _) in enumerate(LANGUAGES):
            if code == current_lang:
                lang_idx = i
                break
        lang_row.set_selected(lang_idx)
        lang_row.connect("notify::selected", self._on_language_changed)
        lang_group.add(lang_row)

        page.add(lang_group)

        # --- Sección: Colores de voces ---
        colors_group = Adw.PreferencesGroup()
        colors_group.set_title("Colores de voces")
        colors_group.set_description("Personaliza el color de cada voz")

        if not self.voices:
            no_voices = Adw.ActionRow()
            no_voices.set_title("No hay voces instaladas")
            no_voices.set_subtitle("Instala una voz para personalizar sus colores")
            colors_group.add(no_voices)
        else:
            for voice in self.voices:
                row = Adw.ActionRow()
                row.set_title(voice)
                color = self.voice_colors.get(voice, "#E0E0E0")

                btn = Gtk.ColorDialogButton()
                dialog = Gtk.ColorDialog()
                dialog.set_with_alpha(False)
                btn.set_dialog(dialog)
                rgba = Gdk.RGBA()
                rgba.parse(color)
                btn.set_rgba(rgba)
                btn.set_valign(Gtk.Align.CENTER)
                btn.connect("notify::rgba", self._on_color_changed, voice)
                row.add_suffix(btn)

                colors_group.add(row)

            reset_btn = Adw.ActionRow()
            reset_btn.set_title("Restablecer colores por defecto")
            reset_btn.set_subtitle("Vuelve a la paleta original")
            reset_btn.set_activatable(True)
            reset_btn.add_suffix(Gtk.Image.new_from_icon_name("edit-undo-symbolic"))
            reset_btn.connect("activated", self._on_reset_colors)
            colors_group.add(reset_btn)

        page.add(colors_group)

        # --- Sección: Pronunciaciones personalizadas ---
        lexicon_group = Adw.PreferencesGroup()
        lexicon_group.set_title("Pronunciaciones personalizadas")
        lexicon_group.set_description("Define cómo se deben pronunciar ciertas palabras")

        lexicon_row = Adw.ActionRow()
        lexicon_row.set_title("Gestionar pronunciaciones")
        lexicon_row.set_subtitle("Añade o edita palabras como 'Minecraft' -> 'Maincraft'")
        lexicon_row.set_activatable(True)
        lexicon_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        lexicon_row.connect("activated", self._on_lexicon_clicked)
        lexicon_group.add(lexicon_row)

        page.add(lexicon_group)

        # --- Sección: Caché de audio ---
        cache_group = Adw.PreferencesGroup()
        cache_group.set_title("Caché de audio")
        cache_group.set_description("Los audios generados se guardan para acelerar futuras generaciones")

        count, total = get_cache_info()
        self.cache_size_row = Adw.ActionRow()
        self.cache_size_row.set_title("Tamaño actual del caché")
        self.cache_size_row.set_subtitle(f"{count} archivos, {_format_size(total)}")

        clear_row = Adw.ActionRow()
        clear_row.set_title("Limpiar caché de audio")
        clear_row.set_subtitle("Elimina todos los audios guardados")
        clear_row.set_activatable(True)
        clear_row.add_suffix(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
        clear_row.connect("activated", self._on_clear_cache)

        cache_group.add(self.cache_size_row)
        cache_group.add(clear_row)

        page.add(cache_group)

        self.add(page)

    def _on_theme_changed(self, row, pspec):
        idx = row.get_selected()
        theme = {0: "system", 1: "light", 2: "dark"}.get(idx, "system")
        self.prefs["theme"] = theme
        save_preferences(self.prefs)

        sm = Adw.StyleManager.get_default()
        if theme == "light":
            sm.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "dark":
            sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            sm.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_language_changed(self, row, pspec):
        idx = row.get_selected()
        if 0 <= idx < len(LANGUAGES):
            code = LANGUAGES[idx][0]
            self.prefs["language"] = code
            save_preferences(self.prefs)

    def _on_color_changed(self, btn, pspec, voice):
        rgba = btn.get_rgba()
        hex_color = "#{:02X}{:02X}{:02X}".format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
        )
        self.voice_colors[voice] = hex_color
        save_voice_colors(self.voice_colors)

    def _on_reset_colors(self, row):
        from src.backend import DEFAULT_VOICE_COLORS
        self.voice_colors = dict(DEFAULT_VOICE_COLORS)
        save_voice_colors(self.voice_colors)
        self.close()
        new_win = PreferencesWindow(parent=self.get_transient_for())
        new_win.present()

    def _on_lexicon_clicked(self, row):
        if LexiconWindow is None:
            return
        win = LexiconWindow(parent=self)
        win.present()

    def _on_clear_cache(self, row):
        count, total = clear_audio_cache()
        dialog = Adw.AlertDialog(
            heading="Caché limpiado",
            body=f"Se eliminaron {count} archivos ({_format_size(total)})."
        )
        dialog.add_response("ok", "Aceptar")
        dialog.present(self)

        new_count, new_total = get_cache_info()
        self.cache_size_row.set_subtitle(f"{new_count} archivos, {_format_size(new_total)}")
