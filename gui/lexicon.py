import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.backend import load_pronunciations, save_pronunciations

class LexiconWindow(Adw.Window):
    def __init__(self, parent=None, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Editor de Lexicones")
        self.set_default_size(550, 650)
        self.set_transient_for(parent)
        self.set_modal(True)

        self.pronunciations = load_pronunciations()

        header = Adw.HeaderBar()
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.set_tooltip_text("Añadir palabra")
        add_btn.connect("clicked", self.on_add_clicked)
        header.pack_start(add_btn)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("boxed-list")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.listbox)
        scrolled.set_vexpand(True)

        self.main_box.append(scrolled)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self.main_box)
        self.set_content(toolbar_view)

        self.refresh_list()

    def refresh_list(self):
        while self.listbox.get_first_child():
            self.listbox.remove(self.listbox.get_first_child())

        if not self.pronunciations:
            row = Adw.ActionRow()
            row.set_title("No hay palabras personalizadas")
            row.set_subtitle("Pulsa el botón '+' para añadir una.")
            self.listbox.append(row)
            return

        for original, replacement in sorted(self.pronunciations.items(), key=lambda x: x[0].lower()):
            row = Adw.ActionRow()
            row.set_title(original)
            row.set_subtitle(f"Se pronuncia como: {replacement}")

            del_btn = Gtk.Button(icon_name="user-trash-symbolic")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.add_css_class("destructive-action")
            del_btn.connect("clicked", self.on_delete_clicked, original)
            row.add_suffix(del_btn)

            self.listbox.append(row)

    def on_add_clicked(self, btn):
        dialog = Adw.AlertDialog(
            heading="Añadir pronunciación",
            body="Escribe la palabra original y cómo quieres que se pronuncie."
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8); box.set_margin_bottom(8)

        original_entry = Gtk.Entry(placeholder_text="Palabra original (ej. Minecraft)")
        replacement_entry = Gtk.Entry(placeholder_text="Pronunciación (ej. Maincraft)")

        box.append(Gtk.Label(label="Palabra original:", xalign=0))
        box.append(original_entry)
        box.append(Gtk.Label(label="Se pronuncia como:", xalign=0))
        box.append(replacement_entry)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("add", "Añadir")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "add":
                orig = original_entry.get_text().strip()
                repl = replacement_entry.get_text().strip()
                if orig and repl:
                    self.pronunciations[orig] = repl
                    save_pronunciations(self.pronunciations)
                    self.refresh_list()
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present(self)

    def on_delete_clicked(self, btn, original):
        if original in self.pronunciations:
            del self.pronunciations[original]
            save_pronunciations(self.pronunciations)
            self.refresh_list()
