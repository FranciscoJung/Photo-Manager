import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from PIL import Image
import database as db
import utils

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class PhotoManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gerenciador de Fotos")
        self.geometry("1200x750")
        self.selected_filter_tags = set()
        self.photo_frames = []
        self.selection_mode = False
        self.selected_photos = {}

        self._build_ui()
        self._refresh_tag_list()
        self._load_photos()

    # ── CONSTRUÇÃO DA INTERFACE ─────────────────────────────

    def _build_ui(self):
        self.left_panel = ctk.CTkFrame(self, width=250)
        self.left_panel.pack(side="left", fill="y", padx=10, pady=10)
        self.left_panel.pack_propagate(False)

        ctk.CTkLabel(self.left_panel, text="Filtrar por Tags", font=("Arial", 16, "bold")).pack(pady=(15, 5))

        self.tag_search_var = ctk.StringVar()
        self.tag_search_var.trace_add("write", lambda *_: self._refresh_tag_list())
        ctk.CTkEntry(self.left_panel, textvariable=self.tag_search_var, placeholder_text="Buscar tag...").pack(fill="x", padx=10)

        self.tag_list_frame = ctk.CTkScrollableFrame(self.left_panel, label_text="")
        self.tag_list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkButton(self.left_panel, text="Limpar Filtros", command=self._clear_filters).pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkButton(
            self.left_panel, text="🏷 Gerenciar Tags",
            fg_color="#555", hover_color="#444",
            command=self._open_tag_manager
        ).pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkButton(self.left_panel, text="+ Importar Fotos", command=self._import_photos, fg_color="green").pack(fill="x", padx=10, pady=(0, 15))

        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)

        top_bar = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(5, 0))

        self.status_label = ctk.CTkLabel(top_bar, text="", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)

        self.select_mode_btn = ctk.CTkButton(
            top_bar, text="☑ Selecionar", width=120,
            command=self._toggle_selection_mode
        )
        self.select_mode_btn.pack(side="right")

        self.gallery = ctk.CTkScrollableFrame(self.right_panel)
        self.gallery.pack(fill="both", expand=True, padx=5, pady=5)

        self.action_bar = ctk.CTkFrame(self.right_panel, height=55, fg_color="#1e1e2e")
        self._build_action_bar()

    def _build_action_bar(self):
        self.selection_count_label = ctk.CTkLabel(
            self.action_bar, text="0 selecionada(s)", anchor="w"
        )
        self.selection_count_label.pack(side="left", padx=15)

        ctk.CTkButton(
            self.action_bar, text="Selecionar Tudo", width=130,
            command=self._select_all
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.action_bar, text="Desmarcar Tudo", width=130,
            command=self._deselect_all
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.action_bar, text="+ Adicionar Tags", width=130,
            fg_color="#2a6496",
            command=self._bulk_add_tags
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            self.action_bar, text="— Remover Tags", width=130,
            fg_color="#7d6608",
            command=self._bulk_remove_tags
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            self.action_bar, text="🗑 Excluir Seleção", width=140,
            fg_color="#c0392b", hover_color="#96281b",
            command=self._bulk_delete
        ).pack(side="right", padx=5)

    # ── MODO SELEÇÃO ───────────────────────────────────────

    def _toggle_selection_mode(self):
        self.selection_mode = not self.selection_mode
        self.selected_photos.clear()

        if self.selection_mode:
            self.select_mode_btn.configure(text="✕ Cancelar Seleção", fg_color="#555")
            self.action_bar.pack(fill="x", padx=5, pady=(0, 5))
        else:
            self.select_mode_btn.configure(text="☑ Selecionar", fg_color=["#3a7ebf", "#1f538d"])
            self.action_bar.pack_forget()

        self._load_photos()

    def _toggle_photo_selection(self, photo: dict, var: ctk.BooleanVar, frame: ctk.CTkFrame):
        if var.get():
            self.selected_photos[photo["id"]] = photo
            frame.configure(border_color="#3a7ebf", border_width=3)
        else:
            self.selected_photos.pop(photo["id"], None)
            frame.configure(border_width=0, fg_color=["#ebebeb", "#2b2b2b"])

        self.selection_count_label.configure(text=f"{len(self.selected_photos)} selecionada(s)")

    def _select_all(self):
        for photo_id, (photo, var, frame) in self._gallery_items.items():
            var.set(True)
            self.selected_photos[photo["id"]] = photo
            frame.configure(border_color="#3a7ebf", border_width=3)
        self.selection_count_label.configure(text=f"{len(self.selected_photos)} selecionada(s)")

    def _deselect_all(self):
        for photo_id, (photo, var, frame) in self._gallery_items.items():
            var.set(False)
            frame.configure(border_width=0, fg_color=["#ebebeb", "#2b2b2b"])
        self.selected_photos.clear()
        self.selection_count_label.configure(text="0 selecionada(s)")

    # ── AÇÕES EM LOTE ──────────────────────────────────────

    def _bulk_delete(self):
        if not self.selected_photos:
            messagebox.showwarning("Nenhuma foto", "Selecione ao menos uma foto para excluir.")
            return

        count = len(self.selected_photos)
        resposta = messagebox.askyesno(
            "Excluir fotos",
            f"Tem certeza que deseja excluir {count} foto(s) selecionada(s)?\n\nEsta ação não pode ser desfeita.",
            icon="warning"
        )
        if resposta:
            db.delete_photos_bulk(list(self.selected_photos.values()))
            self.selected_photos.clear()
            self._toggle_selection_mode()
            self._refresh_tag_list()
            self._load_photos()

    def _bulk_add_tags(self):
        if not self.selected_photos:
            messagebox.showwarning("Nenhuma foto", "Selecione ao menos uma foto para adicionar tags.")
            return
        self._open_bulk_tag_editor(mode="add")

    def _bulk_remove_tags(self):
        if not self.selected_photos:
            messagebox.showwarning("Nenhuma foto", "Selecione ao menos uma foto para remover tags.")
            return
        self._open_bulk_tag_editor(mode="remove")

    def _open_bulk_tag_editor(self, mode: str):
        win = ctk.CTkToplevel(self)
        win.title("Adicionar Tags em Lote" if mode == "add" else "Remover Tags em Lote")
        win.geometry("400x520")
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.grab_set()

        count = len(self.selected_photos)
        cor_titulo = "#2a6496" if mode == "add" else "#7d6608"
        acao = "adicionar a" if mode == "add" else "remover de"

        ctk.CTkLabel(
            win,
            text=f"Selecione as tags para {acao} {count} foto(s)",
            font=("Arial", 13, "bold"),
            wraplength=360
        ).pack(pady=12, padx=10)

        all_tags = db.get_all_tags()
        vars_map = {}

        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=15)

        for tag in all_tags:
            var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(scroll, text=tag, variable=var).pack(anchor="w", pady=2)
            vars_map[tag] = var

        if mode == "add":
            ctk.CTkLabel(win, text="Nova tag:").pack()
            new_tag_entry = ctk.CTkEntry(win, placeholder_text="Ex: Viagem 2025")
            new_tag_entry.pack(fill="x", padx=15, pady=5)

            def add_new_tag():
                name = new_tag_entry.get().strip()
                if name and name not in vars_map:
                    var = ctk.BooleanVar(value=True)
                    ctk.CTkCheckBox(scroll, text=name, variable=var).pack(anchor="w", pady=2)
                    vars_map[name] = var
                    new_tag_entry.delete(0, "end")

            ctk.CTkButton(win, text="+ Adicionar", command=add_new_tag).pack(pady=2)

        def save():
            selected_tags = [tag for tag, var in vars_map.items() if var.get()]
            if not selected_tags:
                messagebox.showwarning("Nenhuma tag", "Selecione ao menos uma tag.")
                return

            photo_ids = list(self.selected_photos.keys())
            if mode == "add":
                db.add_tags_bulk(photo_ids, selected_tags)
            else:
                db.remove_tags_bulk(photo_ids, selected_tags)

            win.destroy()
            self._toggle_selection_mode()
            self._refresh_tag_list()
            self._load_photos()

        ctk.CTkButton(win, text="Aplicar", fg_color=cor_titulo, command=save).pack(pady=12)

    # ── GERENCIADOR DE TAGS ────────────────────────────────

    def _open_tag_manager(self):
        win = ctk.CTkToplevel(self)
        win.title("Gerenciar Tags")
        win.geometry("380x500")
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.grab_set()

        ctk.CTkLabel(win, text="Gerenciar Tags", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkLabel(
            win,
            text="Excluir uma tag a remove de todas as fotos.",
            font=("Arial", 10),
            text_color="gray"
        ).pack(pady=(0, 8))

        search_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=search_var, placeholder_text="Buscar tag...").pack(fill="x", padx=15, pady=(0, 5))

        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        def render_tags():
            for widget in scroll.winfo_children():
                widget.destroy()

            search = search_var.get().lower()
            all_tags = db.get_all_tags()
            filtered = [t for t in all_tags if search in t.lower()]

            if not filtered:
                ctk.CTkLabel(scroll, text="Nenhuma tag encontrada.", text_color="gray").pack(pady=20)
                return

            for tag in filtered:
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)

                ctk.CTkLabel(row, text=tag, anchor="w").pack(side="left", fill="x", expand=True, padx=5)

                def make_delete(t=tag):
                    def delete():
                        resposta = messagebox.askyesno(
                            "Excluir tag",
                            f"Tem certeza que deseja excluir a tag '{t}'?\n\nEla será removida de todas as fotos.",
                            icon="warning"
                        )
                        if resposta:
                            db.delete_tag(t)
                            self.selected_filter_tags.discard(t)
                            render_tags()
                            self._refresh_tag_list()
                            self._load_photos()
                    return delete

                ctk.CTkButton(
                    row, text="Excluir", width=70,
                    fg_color="#c0392b", hover_color="#96281b",
                    command=make_delete()
                ).pack(side="right", padx=5)

        search_var.trace_add("write", lambda *_: render_tags())
        render_tags()

        ctk.CTkButton(win, text="Fechar", command=win.destroy).pack(pady=10)

    # ── TAGS ───────────────────────────────────────────────

    def _refresh_tag_list(self):
        for widget in self.tag_list_frame.winfo_children():
            widget.destroy()

        search = self.tag_search_var.get().lower()
        all_tags = db.get_all_tags()
        filtered = [t for t in all_tags if search in t.lower()]

        for tag in filtered:
            var = ctk.BooleanVar(value=tag in self.selected_filter_tags)
            cb = ctk.CTkCheckBox(
                self.tag_list_frame, text=tag, variable=var,
                command=lambda t=tag, v=var: self._toggle_filter_tag(t, v)
            )
            cb.pack(anchor="w", pady=2)

    def _toggle_filter_tag(self, tag: str, var: ctk.BooleanVar):
        if var.get():
            self.selected_filter_tags.add(tag)
        else:
            self.selected_filter_tags.discard(tag)
        self._load_photos()

    def _clear_filters(self):
        self.selected_filter_tags.clear()
        self._refresh_tag_list()
        self._load_photos()

    # ── GALERIA ────────────────────────────────────────────

    def _load_photos(self):
        for widget in self.gallery.winfo_children():
            widget.destroy()

        self._gallery_items = {}

        photos = db.get_photos_by_tags(list(self.selected_filter_tags))
        self.status_label.configure(text=f"{len(photos)} foto(s) encontrada(s)")

        cols = 4
        for i, photo in enumerate(photos):
            frame = ctk.CTkFrame(self.gallery, corner_radius=8)
            frame.grid(row=i // cols, column=i % cols, padx=8, pady=8)

            thumb_path = os.path.join("thumbnails", photo["filename"])
            try:
                img = Image.open(thumb_path)
                ctk_img = ctk.CTkImage(light_image=img, size=(180, 180))

                if self.selection_mode:
                    sel_var = ctk.BooleanVar(value=photo["id"] in self.selected_photos)
                    self._gallery_items[photo["id"]] = (photo, sel_var, frame)

                    if sel_var.get():
                        frame.configure(border_color="#3a7ebf", border_width=3)

                    img_btn = ctk.CTkButton(
                        frame, image=ctk_img, text="",
                        fg_color="transparent", hover_color="#333",
                        command=lambda p=photo, v=sel_var, f=frame: (
                            v.set(not v.get()),
                            self._toggle_photo_selection(p, v, f)
                        )
                    )
                    img_btn.pack()

                    cb = ctk.CTkCheckBox(
                        frame, text="", variable=sel_var, width=24,
                        command=lambda p=photo, v=sel_var, f=frame: self._toggle_photo_selection(p, v, f)
                    )
                    cb.place(relx=0.05, rely=0.05)

                else:
                    btn = ctk.CTkButton(
                        frame, image=ctk_img, text="",
                        command=lambda p=photo: self._open_photo_detail(p),
                        fg_color="transparent", hover_color="#333"
                    )
                    btn.pack()

            except Exception:
                ctk.CTkLabel(frame, text="[Erro]").pack()

            tags = db.get_photo_tags(photo["id"])
            tag_text = ", ".join(tags) if tags else "sem tags"
            ctk.CTkLabel(frame, text=tag_text, wraplength=180, font=("Arial", 10)).pack(pady=(2, 5))

    # ── IMPORTAÇÃO ─────────────────────────────────────────

    def _import_photos(self):
        files = filedialog.askopenfilenames(
            title="Selecionar fotos",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.gif *.bmp *.webp")]
        )
        if not files:
            return

        imported, duplicates = 0, 0
        last_photo_id = None

        for filepath in files:
            result = utils.import_photo(filepath)
            if result is None:
                duplicates += 1
                continue
            file_hash, new_filename = result
            taken_date = utils.get_exif_date(filepath)
            original_name = os.path.basename(filepath)
            photo_id = db.add_photo(new_filename, original_name, file_hash, taken_date)
            last_photo_id = photo_id
            imported += 1

        msg = f"{imported} foto(s) importada(s)."
        if duplicates:
            msg += f" {duplicates} duplicata(s) ignorada(s)."
        messagebox.showinfo("Importação concluída", msg)

        if last_photo_id:
            self._open_tag_editor(last_photo_id)

        self._refresh_tag_list()
        self._load_photos()

    # ── DETALHE / EDITOR DE TAGS ───────────────────────────

    def _open_photo_detail(self, photo: dict):
        win = ctk.CTkToplevel(self)
        win.title(photo.get("original_name", "Foto"))
        win.geometry("700x650")
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))

        try:
            img_path = os.path.join("photos", photo["filename"])
            img = Image.open(img_path)
            img.thumbnail((500, 400))
            ctk_img = ctk.CTkImage(light_image=img, size=img.size)
            ctk.CTkLabel(win, image=ctk_img, text="").pack(pady=10)
        except Exception:
            ctk.CTkLabel(win, text="Não foi possível carregar a imagem").pack()

        current_tags = db.get_photo_tags(photo["id"])
        tags_str = ", ".join(current_tags)
        ctk.CTkLabel(win, text=f"Tags: {tags_str or 'nenhuma'}").pack()

        ctk.CTkButton(
            win, text="Editar Tags",
            command=lambda: [win.destroy(), self._open_tag_editor(photo["id"])]
        ).pack(pady=5)

        ctk.CTkButton(
            win, text="Abrir no Explorador",
            command=lambda: os.startfile(os.path.join("photos", photo["filename"]))
        ).pack(pady=2)

        def confirmar_remocao():
            resposta = messagebox.askyesno(
                "Remover foto",
                f"Tem certeza que deseja remover '{photo.get('original_name', 'esta foto')}'?\n\nEsta ação não pode ser desfeita.",
                icon="warning"
            )
            if resposta:
                db.delete_photo(photo["id"], photo["filename"])
                win.destroy()
                self._refresh_tag_list()
                self._load_photos()

        ctk.CTkButton(
            win,
            text="Remover Foto",
            fg_color="#c0392b",
            hover_color="#96281b",
            command=confirmar_remocao
        ).pack(pady=(15, 5))

    def _open_tag_editor(self, photo_id: int):
        win = ctk.CTkToplevel(self)
        win.title("Editar Tags")
        win.geometry("400x500")
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.grab_set()

        ctk.CTkLabel(win, text="Tags desta foto", font=("Arial", 14, "bold")).pack(pady=10)

        all_tags = db.get_all_tags()
        current_tags = set(db.get_photo_tags(photo_id))
        vars_map = {}

        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=15)

        for tag in all_tags:
            var = ctk.BooleanVar(value=tag in current_tags)
            ctk.CTkCheckBox(scroll, text=tag, variable=var).pack(anchor="w", pady=2)
            vars_map[tag] = var

        ctk.CTkLabel(win, text="Adicionar nova tag:").pack()
        new_tag_entry = ctk.CTkEntry(win, placeholder_text="Ex: Viagem 2025")
        new_tag_entry.pack(fill="x", padx=15, pady=5)

        def add_new_tag():
            name = new_tag_entry.get().strip()
            if name and name not in vars_map:
                var = ctk.BooleanVar(value=True)
                ctk.CTkCheckBox(scroll, text=name, variable=var).pack(anchor="w", pady=2)
                vars_map[name] = var
                new_tag_entry.delete(0, "end")

        ctk.CTkButton(win, text="+ Adicionar", command=add_new_tag).pack(pady=2)

        def save():
            selected = [tag for tag, var in vars_map.items() if var.get()]
            db.set_photo_tags(photo_id, selected)
            win.destroy()
            self._refresh_tag_list()
            self._load_photos()

        ctk.CTkButton(win, text="Salvar", fg_color="green", command=save).pack(pady=15)