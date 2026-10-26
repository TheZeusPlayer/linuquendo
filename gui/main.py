import sys
import os
import threading
import subprocess
import gi
import logging

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gst', '1.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Adw, Gst, GLib, Gio, Gdk

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from src.backend import (
        generate_audio, list_installed_voices,
        get_expressions_for_voice, start_daemon_async,
        daemon_ready, shutdown_daemon,
        load_preferences, save_preferences,
        load_voice_colors, DEFAULT_VOICE_COLORS, DEFAULT_COLOR,
        extract_text_from_file
    )
    from gui.preferences import PreferencesWindow
    from gui.lexicon import LexiconWindow
except ImportError:
    generate_audio = None
    list_installed_voices = lambda: []
    get_expressions_for_voice = lambda x: []
    start_daemon_async = lambda: None
    daemon_ready = lambda: True
    shutdown_daemon = lambda: None
    load_preferences = lambda: {"theme": "system", "language": "", "volume": 1.0}
    save_preferences = lambda x: False
    load_voice_colors = lambda: {}
    DEFAULT_VOICE_COLORS = {}
    DEFAULT_COLOR = "#E0E0E0"
    PreferencesWindow = None
    LexiconWindow = None
    extract_text_from_file = lambda p: (None, "Backend no disponible")

LOG_DIR = os.path.expanduser("~/.local/share/linuquendo")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "linuquendo.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

PAUSE_UNIT_MS = 120


class LinuquendoWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(950, 650)
        self.set_size_request(600, 450)
        self.set_title("Linuquendo TTS")
        # ── ICONO ── (útil en X11; en Wayland lo gestiona el compositor)
        self.set_icon_name("linuquendo")
        self.current_file = None
        self.is_generating = False
        self.is_playing = False
        self.is_paused = False
        self.daemon_check_source = None
        self.voices_loaded = False
        self.current_expressions = []
        self.expression_action_group = Gio.SimpleActionGroup()
        self.voice_colors = load_voice_colors()
        self.prefs = load_preferences()

        self.player = Gst.ElementFactory.make("playbin", "player")
        self.player.set_property("volume", 1.0)

        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Linuquendo TTS", css_classes=["title"]))
        menu = Gio.Menu()
        menu.append("Preferencias", "win.preferences")
        menu.append("Acerca de Linuquendo", "win.about")
        menu.append("Salir", "app.quit")
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

        self.menubar_model = self.create_menubar_model()
        menubar = Gtk.PopoverMenuBar.new_from_model(self.menubar_model)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12); main_box.set_margin_bottom(12)
        main_box.set_margin_start(12); main_box.set_margin_end(12)

        controls_wrap = Adw.WrapBox()
        controls_wrap.set_line_spacing(6)
        controls_wrap.set_child_spacing(6)
        controls_wrap.set_margin_bottom(6)

        voice_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        voice_box.append(Gtk.Label(label="Voz:"))
        string_list = Gtk.StringList.new(["(Cargando voces...)"])
        self.voice_dropdown = Gtk.DropDown.new(string_list, None)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_voice_factory_setup)
        factory.connect("bind", self._on_voice_factory_bind)
        self.voice_dropdown.set_factory(factory)
        self.voice_dropdown.set_sensitive(False)
        self.voice_dropdown.connect("notify::selected", self._on_voice_changed)
        voice_box.append(self.voice_dropdown)
        controls_wrap.append(voice_box)

        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        speed_box.append(Gtk.Label(label="Velocidad:"))
        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.0, 0.1)
        self.speed_scale.set_value(1.0); self.speed_scale.set_size_request(100, -1)
        speed_box.append(self.speed_scale)
        controls_wrap.append(speed_box)

        pitch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pitch_box.append(Gtk.Label(label="Tono:"))
        self.pitch_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.0, 0.1)
        self.pitch_scale.set_value(1.0); self.pitch_scale.set_size_request(100, -1)
        pitch_box.append(self.pitch_scale)
        controls_wrap.append(pitch_box)

        vol_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vol_box.append(Gtk.Label(label="Volumen:"))
        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 2.0, 0.05)
        self.vol_scale.set_value(self.prefs.get("volume", 1.0))
        self.vol_scale.set_size_request(80, -1)
        self.vol_scale.connect("value-changed", self._on_volume_changed)
        vol_box.append(self.vol_scale)
        controls_wrap.append(vol_box)

        self.btn_add_pause = Gtk.Button(label="Añadir pausa personalizada")
        self.btn_add_pause.set_can_shrink(True)
        self.btn_add_pause.connect("clicked", self.on_insert_pause_clicked)
        controls_wrap.append(self.btn_add_pause)

        self.btn_lexicon = Gtk.Button(label="Lexicones")
        self.btn_lexicon.set_can_shrink(True)
        self.btn_lexicon.set_tooltip_text("Gestionar pronunciaciones personalizadas")
        self.btn_lexicon.connect("clicked", self.on_lexicon_clicked)
        controls_wrap.append(self.btn_lexicon)

        self.btn_ssml = Gtk.ToggleButton(label="Modo SSML (Experimental)")
        self.btn_ssml.set_can_shrink(True)
        self.btn_ssml.set_tooltip_text(
            "Modo SSML: envía el texto tal cual al motor.\n"
            "NOTA: TTSFileGenerator.exe no soporta SSML, por lo que el motor leerá las etiquetas literalmente."
        )
        controls_wrap.append(self.btn_ssml)

        main_box.append(controls_wrap)

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_vexpand(True)

        self.context_menu = Gio.Menu()
        self.context_menu.append("Cortar", "win.cut")
        self.context_menu.append("Copiar", "win.copy")
        self.context_menu.append("Pegar", "win.paste")
        self.context_menu.append("Seleccionar todo", "win.select_all")
        self.context_menu.append("Insertar pausa personalizada...", "win.insert_pause")
        self.text_view.set_extra_menu(self.context_menu)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.text_view)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

        playback_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        playback_box.set_halign(Gtk.Align.CENTER)
        playback_box.set_margin_top(6); playback_box.set_margin_bottom(6)

        self.btn_play = Gtk.Button(label="Reproducir")
        self.btn_play.connect("clicked", self.on_play_clicked)
        self.btn_play.set_sensitive(False)
        playback_box.append(self.btn_play)

        self.btn_pause_resume = Gtk.Button(label="Pausar")
        self.btn_pause_resume.set_sensitive(False)
        self.btn_pause_resume.connect("clicked", self.on_pause_resume_clicked)
        playback_box.append(self.btn_pause_resume)

        self.btn_stop = Gtk.Button(label="Detener")
        self.btn_stop.connect("clicked", self.on_stop_clicked)
        playback_box.append(self.btn_stop)

        main_box.append(playback_box)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_box.set_margin_start(12); status_box.set_margin_end(12)
        status_box.set_margin_top(6); status_box.set_margin_bottom(6)
        self.status_spinner = Gtk.Spinner()
        self.status_spinner.set_visible(True)
        self.status_spinner.start()
        status_box.append(self.status_spinner)
        self.status_label = Gtk.Label(label="Iniciando...")
        self.status_label.set_xalign(0)
        self.status_label.set_hexpand(True)
        self.status_label.add_css_class("dim-label")
        status_box.append(self.status_label)
        main_box.append(status_box)

        bp_very_narrow = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse("max-width: 650px")
        )
        bp_very_narrow.add_setter(self.btn_ssml, "visible", False)
        self.add_breakpoint(bp_very_narrow)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.add_top_bar(menubar)
        toolbar_view.set_content(main_box)
        self.set_content(toolbar_view)

        self.insert_action_group("expressions", self.expression_action_group)

        self.create_actions()
        self.connect("close-request", self.do_close_request)

        threading.Thread(target=self._load_voices_async, daemon=True).start()

    def _on_volume_changed(self, scale):
        vol = scale.get_value()
        self.prefs["volume"] = vol
        save_preferences(self.prefs)

    def _load_voices_async(self):
        try:
            logging.info("Cargando lista de voces...")
            voces = list_installed_voices()
            logging.info(f"Voces cargadas: {voces}")
        except Exception as e:
            logging.error(f"Error cargando voces: {e}")
            voces = []
        GLib.idle_add(self._on_voices_loaded, voces)

    def _on_voices_loaded(self, voces):
        self.voices_loaded = True
        if not voces:
            self.has_voices = False
            string_list = Gtk.StringList.new(["(No hay voces instaladas)"])
            self.voice_dropdown.set_model(string_list)
            self.voice_dropdown.set_sensitive(False)
            self.btn_play.set_sensitive(False)
            self.status_label.set_text("No hay voces instaladas. Instala una voz para empezar.")
            self.status_spinner.stop()
            self.status_spinner.set_visible(False)
            return

        self.has_voices = True
        string_list = Gtk.StringList.new(voces)
        self.voice_dropdown.set_model(string_list)
        self.voice_dropdown.set_sensitive(True)

        self.status_label.set_text("Motor listo.")
        self.status_spinner.stop()
        self.status_spinner.set_visible(False)
        self.btn_play.set_sensitive(True)

        self._refresh_expressions_menu()

    def _on_voice_changed(self, dropdown, pspec):
        if self.voices_loaded:
            self._refresh_expressions_menu()

    def _refresh_expressions_menu(self):
        try:
            voice = self.voice_dropdown.get_selected_item().get_string()
        except Exception:
            return

        for action_name in list(self.expression_action_group.list_actions()):
            self.expression_action_group.remove_action(action_name)

        try:
            self.current_expressions = get_expressions_for_voice(voice)
        except Exception as e:
            logging.error(f"Error obteniendo expresiones para {voice}: {e}")
            self.current_expressions = []

        sonidos = [e for e in self.current_expressions if e.get("type") == "sonido"]
        frases = [e for e in self.current_expressions if e.get("type") == "frase"]

        sounds_menu = Gio.Menu()
        if sonidos:
            for i, expr in enumerate(sonidos):
                action_name = f"expr_{i}"
                action = Gio.SimpleAction.new(action_name, None)
                action.connect("activate", self._on_insert_expression, expr["code"])
                self.expression_action_group.add_action(action)
                sounds_menu.append(expr["name"], f"expressions.{action_name}")
        else:
            sounds_menu.append("(No hay sonidos)", "expressions.noop")

        phrases_menu = Gio.Menu()
        if frases:
            for i, expr in enumerate(frases, start=len(sonidos)):
                action_name = f"expr_{i}"
                action = Gio.SimpleAction.new(action_name, None)
                action.connect("activate", self._on_insert_expression, expr["code"])
                self.expression_action_group.add_action(action)
                phrases_menu.append(expr["name"], f"expressions.{action_name}")
        else:
            phrases_menu.append("(No hay frases)", "expressions.noop")

        expr_menu = Gio.Menu()
        expr_menu.append_submenu("🔊 Sonidos", sounds_menu)
        expr_menu.append_submenu("💬 Frases", phrases_menu)

        self.menubar_model.remove(2)
        insert_menu = Gio.Menu()
        insert_menu.append_submenu("Expresiones", expr_menu)
        insert_menu.append("Insertar pausa personalizada...", "win.insert_pause")
        insert_menu.append("Gestionar Lexicones...", "win.lexicon")
        self.menubar_model.insert_submenu(2, "Insertar", insert_menu)

        logging.info(f"Menú de expresiones actualizado para {voice}: {len(sonidos)} sonidos, {len(frases)} frases")

    def _on_insert_expression(self, action, param, code):
        self._insert_text_at_cursor(code)
        self.status_label.set_text(f"Expresión insertada: {code}")

    def on_lexicon_clicked(self, button):
        if LexiconWindow is None:
            return
        win = LexiconWindow(parent=self)
        win.present()

    def on_insert_pause_clicked(self, button):
        self._show_pause_dialog()

    def _show_pause_dialog(self):
        dialog = Adw.AlertDialog(
            heading="Insertar pausa personalizada",
            body="Selecciona la duración de la pausa. El motor la redondeará al múltiplo de 120 ms más cercano."
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)

        quick_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        quick_box.append(Gtk.Label(label="Rápido:"))
        for ms in [120, 240, 480, 1000]:
            btn = Gtk.Button(label=f"{ms} ms")
            btn.connect("clicked", lambda b, v=ms: self._insert_pause(v, dialog))
            quick_box.append(btn)
        box.append(quick_box)

        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        custom_box.append(Gtk.Label(label="Personalizado:"))
        spin = Gtk.SpinButton.new_with_range(120, 10000, 120)
        spin.set_value(240)
        custom_box.append(spin)
        custom_box.append(Gtk.Label(label="ms"))
        box.append(custom_box)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("insert", "Insertar")
        dialog.set_response_appearance("insert", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "insert":
                ms = int(spin.get_value())
                self._insert_pause(ms, dialog)
            else:
                dialog.close()

        dialog.connect("response", on_response)
        dialog.present(self)

    def _insert_pause(self, ms, dialog=None):
        n = max(1, round(ms / PAUSE_UNIT_MS))
        real_ms = n * PAUSE_UNIT_MS
        code = " \\pause " * n
        self._insert_text_at_cursor(code)
        self.status_label.set_text(f"Pausa insertada: {real_ms} ms ({n} × \\pause)")
        if dialog:
            dialog.close()

    def _insert_text_at_cursor(self, text):
        buffer = self.text_view.get_buffer()
        if buffer.get_selection_bounds():
            start, end = buffer.get_selection_bounds()
            buffer.delete(start, end)
        else:
            start = buffer.get_iter_at_mark(buffer.get_insert())
        buffer.insert(start, text)

    def on_pause_resume_clicked(self, button):
        if not self.is_playing:
            return
        if self.is_paused:
            self.player.set_state(Gst.State.PLAYING)
            self.btn_pause_resume.set_label("Pausar")
            self.is_paused = False
            self.status_label.set_text("Reproduciendo...")
        else:
            self.player.set_state(Gst.State.PAUSED)
            self.btn_pause_resume.set_label("Reanudar")
            self.is_paused = True
            self.status_label.set_text("Reproducción pausada.")

    def do_close_request(self, *args):
        try:
            logging.info("Cerrando app...")
            if self.daemon_check_source is not None:
                try:
                    GLib.source_remove(self.daemon_check_source)
                except Exception:
                    pass
                self.daemon_check_source = None
            try:
                subprocess.run(["wineserver", "-k"], capture_output=True, timeout=5)
            except Exception:
                pass
        except Exception as e:
            logging.error(f"Error cerrando: {e}")
        return False

    def _on_voice_factory_setup(self, factory, list_item):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        color_dot = Gtk.DrawingArea(); color_dot.set_size_request(12, 12)
        color_dot.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label()
        box.append(color_dot); box.append(label)
        list_item.set_child(box)

    def _on_voice_factory_bind(self, factory, list_item):
        box = list_item.get_child()
        color_dot = box.get_first_child()
        label = color_dot.get_next_sibling()
        string_obj = list_item.get_item()
        voice_name = string_obj.get_string()
        label.set_text(voice_name)
        color_hex = self.voice_colors.get(voice_name, DEFAULT_COLOR)
        rgba = Gdk.RGBA(); rgba.parse(color_hex)
        color_dot.set_draw_func(self._draw_color_dot, rgba)

    def _draw_color_dot(self, area, cr, width, height, rgba):
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        cr.arc(width/2, height/2, min(width, height)/2, 0, 2 * 3.14159)
        cr.fill()

    def create_menubar_model(self):
        menubar = Gio.Menu()
        file_menu = Gio.Menu()
        file_menu.append("Nuevo", "app.new")
        file_menu.append("Abrir...", "app.open")
        file_menu.append("Importar desde PDF...", "app.import_pdf")
        file_menu.append("Importar desde DOCX...", "app.import_docx")
        file_menu.append("Importar desde EPUB...", "app.import_epub")
        file_menu.append("Guardar", "app.save")
        file_menu.append("Guardar como...", "app.save_as")
        file_menu.append("Exportar WAV...", "app.export")
        file_menu.append("Salir", "app.quit")
        menubar.append_submenu("Archivo", file_menu)

        edit_menu = Gio.Menu()
        edit_menu.append("Cortar", "win.cut")
        edit_menu.append("Copiar", "win.copy")
        edit_menu.append("Pegar", "win.paste")
        edit_menu.append("Seleccionar todo", "win.select_all")
        menubar.append_submenu("Edición", edit_menu)

        insert_menu = Gio.Menu()
        insert_menu.append("(Cargando...)", "win.noop")
        menubar.append_submenu("Insertar", insert_menu)

        view_menu = Gio.Menu()
        view_menu.append("Preferencias", "win.preferences")
        view_menu.append("Editor de Lexicones", "win.lexicon")
        menubar.append_submenu("Ver", view_menu)

        help_menu = Gio.Menu()
        help_menu.append("Acerca de Linuquendo", "win.about")
        menubar.append_submenu("Ayuda", help_menu)
        return menubar

    def create_actions(self):
        actions = {
            "new": self.on_new_clicked, "open": self.on_open_clicked,
            "import_pdf": lambda *a: self.on_import_file("pdf"),
            "import_docx": lambda *a: self.on_import_file("docx"),
            "import_epub": lambda *a: self.on_import_file("epub"),
            "save": self.on_save_clicked, "save_as": self.on_save_as_clicked,
            "export": self.on_export_clicked, "quit": lambda *args: self.get_application().quit(),
        }
        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.get_application().add_action(action)

        win_actions = {
            "cut": lambda *args: self.text_view.emit("cut-clipboard"),
            "copy": lambda *args: self.text_view.emit("copy-clipboard"),
            "paste": lambda *args: self.text_view.emit("paste-clipboard"),
            "select_all": lambda *args: self.text_view.get_buffer().select_range(
                self.text_view.get_buffer().get_start_iter(),
                self.text_view.get_buffer().get_end_iter()
            ),
            "about": self.on_about_clicked,
            "preferences": self.on_preferences_clicked,
            "insert_pause": lambda *args: self._show_pause_dialog(),
            "lexicon": lambda *args: self.on_lexicon_clicked(None),
            "noop": lambda *args: None,
        }
        for name, callback in win_actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def on_preferences_clicked(self, *args):
        if PreferencesWindow is None:
            return
        win = PreferencesWindow(parent=self)
        win.present()

    def on_import_file(self, kind):
        filter = Gtk.FileFilter()
        if kind == "pdf":
            filter.set_name("Archivos PDF (*.pdf)")
            filter.add_pattern("*.pdf")
            title = "Importar PDF"
        elif kind == "docx":
            filter.set_name("Archivos DOCX (*.docx)")
            filter.add_pattern("*.docx")
            title = "Importar DOCX"
        else:
            filter.set_name("Archivos EPUB (*.epub)")
            filter.add_pattern("*.epub")
            title = "Importar EPUB"

        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        dialog.set_default_filter(filter)

        def on_open(dialog, result):
            try:
                file = dialog.open_finish(result)
                if not file:
                    return
                path = file.get_path()
                self.status_label.set_text(f"Importando {os.path.basename(path)}...")
                self.status_spinner.set_visible(True)
                self.status_spinner.start()
                threading.Thread(target=self._do_import, args=(path,), daemon=True).start()
            except GLib.Error:
                pass

        dialog.open(self, None, on_open)

    def _do_import(self, path):
        text, error = extract_text_from_file(path)
        GLib.idle_add(self._on_import_done, text, error, path)

    def _on_import_done(self, text, error, path):
        self.status_spinner.stop()
        self.status_spinner.set_visible(False)
        if error:
            self.status_label.set_text(f"Error: {error}")
            dialog = Adw.AlertDialog(heading="No se pudo importar", body=error)
            dialog.add_response("ok", "Aceptar")
            dialog.present(self)
            return
        self.text_view.get_buffer().set_text(text)
        self.current_file = None
        self.status_label.set_text(f"Importado: {os.path.basename(path)} ({len(text)} caracteres)")

    def on_new_clicked(self, *args):
        self.text_view.get_buffer().set_text("")
        self.current_file = None
        self.status_label.set_text("Nuevo proyecto creado.")

    def on_open_clicked(self, *args):
        dialog = Gtk.FileDialog(); dialog.set_title("Abrir proyecto")
        filter = Gtk.FileFilter(); filter.set_name("Archivos de texto (*.txt)"); filter.add_pattern("*.txt")
        dialog.set_default_filter(filter)
        def on_open(dialog, result):
            try:
                file = dialog.open_finish(result)
                if file:
                    path = file.get_path()
                    with open(path, "r", encoding="utf-8") as f: content = f.read()
                    self.text_view.get_buffer().set_text(content)
                    self.current_file = path
                    self.status_label.set_text(f"Abierto: {os.path.basename(path)}")
            except GLib.Error: pass
        dialog.open(self, None, on_open)

    def on_save_clicked(self, *args):
        if self.current_file: self._save_to_file(self.current_file)
        else: self.on_save_as_clicked()

    def on_save_as_clicked(self, *args):
        dialog = Gtk.FileDialog(); dialog.set_title("Guardar proyecto como")
        dialog.set_initial_name("proyecto.txt")
        filter = Gtk.FileFilter(); filter.set_name("Archivos de texto (*.txt)"); filter.add_pattern("*.txt")
        dialog.set_default_filter(filter)
        def on_save(dialog, result):
            try:
                file = dialog.save_finish(result)
                if file: self._save_to_file(file.get_path())
            except GLib.Error: pass
        dialog.save(self, None, on_save)

    def _save_to_file(self, path):
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, False)
        with open(path, "w", encoding="utf-8") as f: f.write(text)
        self.current_file = path
        self.status_label.set_text(f"Guardado: {os.path.basename(path)}")

    def get_text_to_speak(self):
        buffer = self.text_view.get_buffer()
        if buffer.get_selection_bounds():
            start, end = buffer.get_selection_bounds()
            return buffer.get_text(start, end, False)
        else:
            start, end = buffer.get_bounds()
            return buffer.get_text(start, end, False)

    def on_play_clicked(self, button):
        if self.is_generating:
            self.status_label.set_text("Ya se está generando un audio. Por favor, espera.")
            return
        text = self.get_text_to_speak()
        if not text.strip():
            self.status_label.set_text("No hay texto para leer.")
            return
        if generate_audio is None:
            self.status_label.set_text("El motor de audio no está disponible.")
            return

        self.player.set_state(Gst.State.NULL)
        self.is_playing = False
        self.is_paused = False
        self.btn_pause_resume.set_sensitive(False)
        self.btn_pause_resume.set_label("Pausar")

        voice = self.voice_dropdown.get_selected_item().get_string()
        rate = self.speed_scale.get_value()
        pitch = self.pitch_scale.get_value()
        ssml = self.btn_ssml.get_active()
        modo_txt = " (SSML)" if ssml else ""
        self.status_label.set_text(f"Reproduciendo con {voice}{modo_txt}...")
        self.status_spinner.set_visible(True)
        self.status_spinner.start()
        self.btn_play.set_sensitive(False)
        self.is_generating = True
        threading.Thread(target=self._generate_and_play, args=(text, voice, rate, pitch, ssml), daemon=True).start()

    def _generate_and_play(self, text, voice, rate, pitch, ssml):
        try:
            wav_path = generate_audio(text, voice, frequency=44100, channels=2, rate=rate, pitch=pitch, mode="preview", ssml_mode=ssml)
        except Exception as e:
            wav_path = None
            logging.error(f"Excepción en generate_audio: {e}")
        GLib.idle_add(self._on_audio_generated, wav_path)

    def _on_audio_generated(self, wav_path):
        self.is_generating = False
        self.status_spinner.stop()
        self.status_spinner.set_visible(False)
        self.btn_play.set_sensitive(True)
        if wav_path and os.path.exists(wav_path):
            self.status_label.set_text(f"Reproduciendo: {os.path.basename(wav_path)}")
            self.player.set_property("uri", f"file://{wav_path}")
            self.player.set_state(Gst.State.PLAYING)
            self.is_playing = True
            self.is_paused = False
            self.btn_pause_resume.set_sensitive(True)
            self.btn_pause_resume.set_label("Pausar")
        else:
            self.status_label.set_text("Error al generar el audio. Revisa el log.")
            self.is_playing = False

    def on_stop_clicked(self, button):
        self.player.set_state(Gst.State.NULL)
        self.is_playing = False
        self.is_paused = False
        self.btn_pause_resume.set_sensitive(False)
        self.btn_pause_resume.set_label("Pausar")
        self.status_label.set_text("Reproducción detenida.")

    def on_export_clicked(self, *args):
        text = self.get_text_to_speak()
        if not text.strip():
            self.status_label.set_text("No hay texto para exportar.")
            return
        if generate_audio is None:
            self.status_label.set_text("El motor de audio no está disponible.")
            return

        dialog = Adw.AlertDialog(
            heading="Opciones de exportación",
            body="Selecciona la calidad y los canales del archivo WAV."
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)

        freq_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        freq_box.append(Gtk.Label(label="Frecuencia de muestreo:"))
        freq_dropdown = Gtk.DropDown.new_from_strings(["16000 Hz", "22050 Hz", "32000 Hz", "44100 Hz", "48000 Hz"])
        freq_dropdown.set_selected(3)
        freq_box.append(freq_dropdown)
        box.append(freq_box)

        chan_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chan_box.append(Gtk.Label(label="Canales:"))
        chan_dropdown = Gtk.DropDown.new_from_strings(["Mono", "Estéreo"])
        chan_dropdown.set_selected(1)
        chan_box.append(chan_dropdown)
        box.append(chan_box)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("export", "Exportar")
        dialog.set_response_appearance("export", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "export":
                freq_idx = freq_dropdown.get_selected()
                freq_map = [16000, 22050, 32000, 44100, 48000]
                freq = freq_map[freq_idx]
                channels = 1 if chan_dropdown.get_selected() == 0 else 2
                rate = self.speed_scale.get_value()
                pitch = self.pitch_scale.get_value()
                ssml = self.btn_ssml.get_active()

                file_dialog = Gtk.FileDialog()
                file_dialog.set_title("Exportar WAV")
                file_dialog.set_initial_name("linuquendo_output.wav")
                filter = Gtk.FileFilter()
                filter.set_name("Archivos WAV (*.wav)")
                filter.add_pattern("*.wav")
                file_dialog.set_default_filter(filter)

                def on_save(file_dialog, result):
                    try:
                        file = file_dialog.save_finish(result)
                        if file:
                            ruta_destino = file.get_path()
                            voice = self.voice_dropdown.get_selected_item().get_string()
                            self.status_label.set_text("Generando para exportar...")
                            self.status_spinner.set_visible(True)
                            self.status_spinner.start()
                            threading.Thread(target=self._export_audio, args=(text, voice, ruta_destino, freq, channels, rate, pitch, ssml), daemon=True).start()
                    except GLib.Error:
                        pass
                file_dialog.save(self, None, on_save)
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present(self)

    def _export_audio(self, text, voice, destino, freq, channels, rate, pitch, ssml):
        try:
            wav_path = generate_audio(text, voice, frequency=freq, channels=channels, rate=rate, pitch=pitch, mode="export", ssml_mode=ssml)
        except Exception:
            wav_path = None
        GLib.idle_add(self._on_export_done, wav_path, destino)

    def _on_export_done(self, wav_path, destino):
        self.status_spinner.stop()
        self.status_spinner.set_visible(False)
        if wav_path and os.path.exists(wav_path):
            import shutil
            shutil.copy(wav_path, destino)
            self.status_label.set_text(f"Exportado a: {destino}")
        else:
            self.status_label.set_text("Error al exportar.")

    def on_about_clicked(self, *args):
        # ── ICONO ── (usa el nuevo icono en lugar del genérico)
        about = Adw.AboutWindow(
            transient_for=self, application_name="Linuquendo TTS",
            application_icon="linuquendo",
            developer_name="Comunidad Linuquendo", version="0.1.0",
            website="https://github.com/tu-usuario/linuquendo",
            issue_url="https://github.com/tu-usuario/linuquendo/issues",
            license_type=Gtk.License.GPL_3_0,
            comments="Un frontend moderno para el motor de Loquendo TTS en Linux.",
            developers=["Tú", "Comunidad"],
        )
        about.present()


class LinuquendoApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # ── ICONO ── registra assets/icons en el tema de iconos de GTK
        # Así el icono "linuquendo" se resuelve igual en modo dev y en instalado.
        assets_icons = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons')
        )
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            icon_theme.add_search_path(assets_icons)

        prefs = load_preferences()
        sm = Adw.StyleManager.get_default()
        theme = prefs.get("theme", "system")
        if theme == "light":
            sm.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "dark":
            sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            sm.set_color_scheme(Adw.ColorScheme.DEFAULT)

        win = LinuquendoWindow(application=app)
        win.present()


if __name__ == "__main__":
    Gst.init(None)
    app = LinuquendoApp(application_id="com.linuquendo.tts")
    app.run(sys.argv)
