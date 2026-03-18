import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from PIL import Image
import database as db
import utils

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

THUMB_SIZE = 200
THUMB_PAD  = 16

class PhotoManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gerenciador de Fotos")
        self.geometry("1200x750")
        self.selected_filter_tags = set()
        self.photo_frames        = []
        self.selection_mode      = False
        self.selected_photos     = {}
        self._gallery_items      = {}
        self._sidebar_visible    = True
        self._after_id           = None
        self._last_cols          = 0
        self._order              = "recentes"

        self._build_ui()
        self._refresh_tag_list()
        self.after(100, self._load_photos)

    def _build_ui(self):
        self.toggle_btn = ctk.CTkButton(
            self, text="◀", width=24, height=60,
            fg_color="#333", hover_color="#444",
            command=self._toggle_sidebar
        )
        self.toggle_btn.pack(side="left", fill="y", padx=(4, 0), pady=10)

        self.left_panel = ctk.CTkFrame(self, width=220)
        self.left_panel.pack(side="left", fill="y", padx=(2, 0), pady=10)
        self.left_panel.pack_propagate(False)

        ctk.CTkLabel(
            self.left_panel, text="Filtrar por Tags",
            font=("Arial", 15, "bold")
        ).pack(pady=(15, 5))

        self.tag_search_var = ctk.StringVar()
        self.tag_search_var.trace_add("write", lambda *_: self._refresh_tag_list())
        ctk.CTkEntry(
            self.left_panel, textvariable=self.tag_search_var,
            placeholder_text="Buscar tag..."
        ).pack(fill="x", padx=10)

        self.tag_list_frame = ctk.CTkScrollableFrame(self.left_panel, label_text="")
        self.tag_list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkButton(
            self.left_panel, text="Limpar Filtros",
            command=self._clear_filters
        ).pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkButton(
            self.left_panel, text="🏷 Gerenciar Tags",
            fg_color="#555", hover_color="#444",
            command=self._open_tag_manager
        ).pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkButton(
            self.left_panel, text="+ Importar Fotos",
            fg_color="green", command=self._import_photos
        ).pack(fill="x", padx=10, pady=(0, 15))

        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(4, 10), pady=10)

        top_bar = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(5, 0))

        self.status_label = ctk.CTkLabel(top_bar, text="", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(top_bar, text="Ordenar:").pack(side="left", padx=(0, 4))
        self.order_var = ctk.StringVar(value="Mais recentes")
        ctk.CTkOptionMenu(
            top_bar,
            variable=self.order_var,
            values=["Mais recentes", "Mais antigas", "Nome"],
            width=140,
            command=self._on_order_change
        ).pack(side="left", padx=(0, 10))

        self.select_mode_btn = ctk.CTkButton(
            top_bar, text="☑ Selecionar", width=130,
            command=self._toggle_selection_mode
        )
        self.select_mode_btn.pack(side="right")

        self.gallery = ctk.CTkScrollableFrame(self.right_panel)
        self.gallery.pack(fill="both", expand=True, padx=5, pady=5)
        self.bind("<Configure>", self._on_gallery_resize)

        self.action_bar = ctk.CTkFrame(self.right_panel, height=55, fg_color="#1e1e2e")
        self._build_action_bar()

    def _on_order_change(self, choice: str):
        ORDER_MAP = {
            "Mais recentes": "recentes",
            "Mais antigas":  "antigas",
            "Nome":          "nome",
        }
        self._order = ORDER_MAP[choice]
        self._load_photos()

    def _toggle_sidebar(self):
        if self._sidebar_visible:
            self.left_panel.pack_forget()
            self.toggle_btn.configure(text="▶")
        else:
            self.toggle_btn.pack_forget()
            self.toggle_btn.pack(side="left", fill="y", padx=(4, 0), pady=10)
            self.left_panel.pack(side="left", fill="y", padx=(2, 0), pady=10)
            self.toggle_btn.configure(text="◀")
        self._sidebar_visible = not self._sidebar_visible
        self._last_cols = 0
        self._load_photos()

    def _on_gallery_resize(self, event):
        if event.widget != self:
            return
        new_cols = max(1, self.gallery.winfo_width() // (THUMB_SIZE + THUMB_PAD))
        if new_cols == self._last_cols:
            return
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(150, self._reflow_gallery)

    def _reflow_gallery(self):
        self._load_photos()

    def _calc_cols(self):
        self.gallery.update_idletasks()
        width = self.gallery.winfo_width()
        return max(1, width // (THUMB_SIZE + THUMB_PAD))

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
            self.action_bar, text="🗑 Excluir Seleção", width=140,
            fg_color="#c0392b", hover_color="#96281b",
            command=self._bulk_delete
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            self.action_bar, text="— Remover Tags", width=130,
            fg_color="#7d6608", command=self._bulk_remove_tags
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            self.action_bar, text="+ Adicionar Tags", width=130,
            fg_color="#2a6496", command=self._bulk_add_tags
        ).pack(side="right", padx=5)

    def _toggle_selection_mode(self):
        self.selection_mode = not self.selection_mode
        self.selected_photos.clear()

        if self.selection_mode:
            self.select_mode_btn.configure(text="✕ Cancelar Seleção", fg_color="#555")
            self.action_bar.pack(fill="x", padx=5, pady=(0, 5))
        else:
            self.select_mode_btn.configure(text="☑ Selecionar", fg_color=["#3a7ebf", "#1f538d"])
            self.action_bar.pack_forget()

        self._last_cols = 0
        self._load_photos()

    def _toggle_photo_selection(self, photo, var, frame):
        if var.get():
            self.selected_photos[photo["id"]] = photo
            frame.configure(border_color="#3a7ebf", border_width=3)
        else:
            self.selected_photos.pop(photo["id"], None)
            frame.configure(border_width=0, fg_color=["#ebebeb", "#2b2b2b"])
        self.selection_count_label.configure(
            text=f"{len(self.selected_photos)} selecionada(s)"
        )

    def _select_all(self):
        for photo_id, (photo, var, frame) in self._gallery_items.items():
            var.set(True)
            self.selected_photos[photo["id"]] = photo
            frame.configure(border_color="#3a7ebf", border_width=3)
        self.selection_count_label.configure(
            text=f"{len(self.selected_photos)} selecionada(s)"
        )

    def _deselect_all(self):
        for photo_id, (photo, var, frame) in self._gallery_items.items():
            var.set(False)
            frame.configure(border_width=0, fg_color=["#ebebeb", "#2b2b2b"])
        self.selected_photos.clear()
        self.selection_count_label.configure(text="0 selecionada(s)")

    def _bulk_delete(self):
        if not self.selected_photos:
            messagebox.showwarning("Nenhuma foto", "Selecione ao menos uma foto.")
            return
        count = len(self.selected_photos)
        if messagebox.askyesno(
            "Excluir fotos",
            f"Excluir {count} foto(s)?\n\nEsta ação não pode ser desfeita.",
            icon="warning"
        ):
            db.delete_photos_bulk(list(self.selected_photos.values()))
            self.selected_photos.clear()
            self._toggle_selection_mode()
            self._refresh_tag_list()
            self._load_photos()

    def _bulk_add_tags(self):
        if not self.selected_photos:
            messagebox.showwarning("Nenhuma foto", "Selecione ao menos uma foto.")
            return
        self._open_bulk_tag_editor(mode="add")

    def _bulk_remove_tags(self):
        if not self.selected_photos:
            messagebox.showwarning("Nenhuma foto", "Selecione ao menos uma foto.")
            return
        self._open_bulk_tag_editor(mode="remove")

    def _open_bulk_tag_editor(self, mode: str):
        win = ctk.CTkToplevel(self)
        win.title("Adicionar Tags em Lote" if mode == "add" else "Remover Tags em Lote")
        win.geometry("400x520")
        win.lift(); win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.grab_set()

        count = len(self.selected_photos)
        cor   = "#2a6496" if mode == "add" else "#7d6608"
        acao  = "adicionar a" if mode == "add" else "remover de"

        ctk.CTkLabel(
            win, text=f"Tags para {acao} {count} foto(s)",
            font=("Arial", 13, "bold"), wraplength=360
        ).pack(pady=12, padx=10)

        vars_map = {}
        scroll   = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=15)

        for tag in db.get_user_tags():
            var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(scroll, text=tag, variable=var).pack(anchor="w", pady=2)
            vars_map[tag] = var

        if mode == "add":
            ctk.CTkLabel(win, text="Nova tag:").pack()
            entry = ctk.CTkEntry(win, placeholder_text="Ex: Viagem 2025")
            entry.pack(fill="x", padx=15, pady=5)

            def add_new():
                name = entry.get().strip()
                if name and name not in vars_map:
                    v = ctk.BooleanVar(value=True)
                    ctk.CTkCheckBox(scroll, text=name, variable=v).pack(anchor="w", pady=2)
                    vars_map[name] = v
                    entry.delete(0, "end")

            ctk.CTkButton(win, text="+ Adicionar", command=add_new).pack(pady=2)

        def save():
            selected = [t for t, v in vars_map.items() if v.get()]
            if not selected:
                messagebox.showwarning("Nenhuma tag", "Selecione ao menos uma tag.")
                return
            ids = list(self.selected_photos.keys())
            if mode == "add":
                db.add_tags_bulk(ids, selected)
            else:
                db.remove_tags_bulk(ids, selected)
            win.destroy()
            self._toggle_selection_mode()
            self._refresh_tag_list()
            self._load_photos()

        ctk.CTkButton(win, text="Aplicar", fg_color=cor, command=save).pack(pady=12)

    def _open_tag_manager(self):
        win = ctk.CTkToplevel(self)
        win.title("Gerenciar Tags")
        win.geometry("420x500")
        win.lift(); win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.grab_set()

        ctk.CTkLabel(win, text="Gerenciar Tags", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkLabel(
            win, text="Renomeie ou exclua tags. Alterações se aplicam a todas as fotos.",
            font=("Arial", 10), text_color="gray", wraplength=380
        ).pack(pady=(0, 8))

        search_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=search_var, placeholder_text="Buscar tag...").pack(
            fill="x", padx=15, pady=(0, 5)
        )

        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        def render_tags():
            for w in scroll.winfo_children():
                w.destroy()
            s    = search_var.get().lower()
            tags = [t for t in db.get_all_tags() if s in t.lower() and t != db.SEM_TAGS]
            if not tags:
                ctk.CTkLabel(scroll, text="Nenhuma tag encontrada.", text_color="gray").pack(pady=20)
                return

            for tag in tags:
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)

                ctk.CTkLabel(row, text=tag, anchor="w").pack(
                    side="left", fill="x", expand=True, padx=5
                )

                def make_rename(t=tag):
                    def do():
                        dialog = ctk.CTkToplevel(win)
                        dialog.title("Renomear Tag")
                        dialog.geometry("320x150")
                        dialog.lift(); dialog.focus_force()
                        dialog.attributes("-topmost", True)
                        dialog.after(200, lambda: dialog.attributes("-topmost", False))
                        dialog.grab_set()

                        ctk.CTkLabel(dialog, text=f"Novo nome para '{t}':").pack(pady=(15, 5))
                        entry = ctk.CTkEntry(dialog)
                        entry.insert(0, t)
                        entry.pack(fill="x", padx=20)
                        entry.select_range(0, "end")
                        entry.focus_set()

                        def confirm():
                            new_name = entry.get().strip()
                            if not new_name or new_name == t:
                                dialog.destroy()
                                return
                            if t in self.selected_filter_tags:
                                self.selected_filter_tags.discard(t)
                                self.selected_filter_tags.add(new_name)
                            db.rename_tag(t, new_name)
                            dialog.destroy()
                            render_tags()
                            self._refresh_tag_list()
                            self._load_photos()

                        entry.bind("<Return>", lambda e: confirm())
                        ctk.CTkButton(
                            dialog, text="Confirmar",
                            fg_color="#2a6496", command=confirm
                        ).pack(pady=10)
                    return do

                def make_delete(t=tag):
                    def do():
                        if messagebox.askyesno(
                            "Excluir tag",
                            f"Excluir a tag '{t}'?\n\nEla será removida de todas as fotos.",
                            icon="warning"
                        ):
                            db.delete_tag(t)
                            self.selected_filter_tags.discard(t)
                            render_tags()
                            self._refresh_tag_list()
                            self._load_photos()
                    return do

                ctk.CTkButton(
                    row, text="Excluir", width=65,
                    fg_color="#c0392b", hover_color="#96281b",
                    command=make_delete()
                ).pack(side="right", padx=(2, 5))

                ctk.CTkButton(
                    row, text="Renomear", width=80,
                    fg_color="#2a6496", hover_color="#1a4a7a",
                    command=make_rename()
                ).pack(side="right", padx=2)

        search_var.trace_add("write", lambda *_: render_tags())
        render_tags()
        ctk.CTkButton(win, text="Fechar", command=win.destroy).pack(pady=10)

    def _refresh_tag_list(self):
        for w in self.tag_list_frame.winfo_children():
            w.destroy()
        s    = self.tag_search_var.get().lower()
        tags = [t for t in db.get_all_tags() if s in t.lower()]
        for tag in tags:
            var = ctk.BooleanVar(value=tag in self.selected_filter_tags)
            ctk.CTkCheckBox(
                self.tag_list_frame, text=tag, variable=var,
                command=lambda t=tag, v=var: self._toggle_filter_tag(t, v)
            ).pack(anchor="w", pady=2)

    def _toggle_filter_tag(self, tag, var):
        if var.get():
            self.selected_filter_tags.add(tag)
        else:
            self.selected_filter_tags.discard(tag)
        self._load_photos()

    def _clear_filters(self):
        self.selected_filter_tags.clear()
        self._refresh_tag_list()
        self._load_photos()

    def _load_photos(self):
        cols = self._calc_cols()
        self._last_cols = cols

        for w in self.gallery.winfo_children():
            w.destroy()
        self._gallery_items = {}

        photos = db.get_photos_by_tags(list(self.selected_filter_tags), order=self._order)
        self.status_label.configure(text=f"{len(photos)} foto(s) encontrada(s)")

        for i, photo in enumerate(photos):
            frame = ctk.CTkFrame(self.gallery, corner_radius=8)
            frame.grid(row=i // cols, column=i % cols, padx=8, pady=8)

            thumb_path = os.path.join(utils.get_thumbs_dir(), photo["filename"])
            try:
                img     = Image.open(thumb_path)
                ctk_img = ctk.CTkImage(light_image=img, size=(THUMB_SIZE, THUMB_SIZE))

                if self.selection_mode:
                    sel_var = ctk.BooleanVar(value=photo["id"] in self.selected_photos)
                    self._gallery_items[photo["id"]] = (photo, sel_var, frame)

                    if sel_var.get():
                        frame.configure(border_color="#3a7ebf", border_width=3)

                    ctk.CTkButton(
                        frame, image=ctk_img, text="",
                        fg_color="transparent", hover_color="#333",
                        command=lambda p=photo, v=sel_var, f=frame: (
                            v.set(not v.get()),
                            self._toggle_photo_selection(p, v, f)
                        )
                    ).pack()

                    cb = ctk.CTkCheckBox(
                        frame, text="", variable=sel_var, width=24,
                        command=lambda p=photo, v=sel_var, f=frame:
                            self._toggle_photo_selection(p, v, f)
                    )
                    cb.place(relx=0.05, rely=0.05)

                else:
                    ctk.CTkButton(
                        frame, image=ctk_img, text="",
                        command=lambda p=photo: self._open_photo_detail(p),
                        fg_color="transparent", hover_color="#333"
                    ).pack()

            except Exception:
                ctk.CTkLabel(frame, text="[Erro]").pack()

            # ── nome do arquivo ──
            nome = photo.get("original_name") or photo["filename"]
            ctk.CTkLabel(
                frame, text=nome, wraplength=THUMB_SIZE,
                font=("Arial", 10, "bold"), text_color="#cccccc"
            ).pack(pady=(4, 0))

            # ── tags ──
            tags     = db.get_photo_tags(photo["id"])
            real     = [t for t in tags if t != db.SEM_TAGS]
            tag_text = ", ".join(real) if real else "sem tags"
            ctk.CTkLabel(
                frame, text=tag_text, wraplength=THUMB_SIZE,
                font=("Arial", 10), text_color="#888888"
            ).pack(pady=(0, 5))

    def _import_photos(self):
        files = filedialog.askopenfilenames(
            title="Selecionar fotos",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.gif *.bmp *.webp")]
        )
        if not files:
            return

        imported = duplicates = 0
        last_id  = None

        for filepath in files:
            result = utils.import_photo(filepath)
            if result is None:
                duplicates += 1
                continue
            file_hash, new_filename = result
            taken_date = utils.get_exif_date(filepath)
            original   = os.path.basename(filepath)
            last_id    = db.add_photo(new_filename, original, file_hash, taken_date)
            imported  += 1

        msg = f"{imported} foto(s) importada(s)."
        if duplicates:
            msg += f" {duplicates} duplicata(s) ignorada(s)."
        messagebox.showinfo("Importação concluída", msg)

        if last_id:
            self._open_tag_editor(last_id)

        self._refresh_tag_list()
        self._load_photos()

    def _open_photo_detail(self, photo):
        win = ctk.CTkToplevel(self)
        win.title(photo.get("original_name", "Foto"))
        win.geometry("700x700")
        win.lift(); win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))

        try:
            img = Image.open(os.path.join(utils.get_photos_dir(), photo["filename"]))
            img.thumbnail((500, 400))
            ctk_img = ctk.CTkImage(light_image=img, size=img.size)
            ctk.CTkLabel(win, image=ctk_img, text="").pack(pady=10)
        except Exception:
            ctk.CTkLabel(win, text="Não foi possível carregar a imagem").pack()

        # ── nome com opção de renomear ──
        nome_frame = ctk.CTkFrame(win, fg_color="transparent")
        nome_frame.pack(fill="x", padx=20, pady=(0, 5))

        nome_var = ctk.StringVar(value=photo.get("original_name", ""))
        nome_entry = ctk.CTkEntry(nome_frame, textvariable=nome_var, width=380)
        nome_entry.pack(side="left", fill="x", expand=True)

        def salvar_nome():
            novo = nome_var.get().strip()
            if novo and novo != photo.get("original_name", ""):
                db.rename_photo(photo["id"], novo)
                win.title(novo)
                self._load_photos()

        ctk.CTkButton(
            nome_frame, text="✎", width=36,
            fg_color="#2a6496", hover_color="#1a4a7a",
            command=salvar_nome
        ).pack(side="left", padx=(6, 0))

        nome_entry.bind("<Return>", lambda e: salvar_nome())

        # ── tags ──
        real_tags = db.get_photo_real_tags(photo["id"])
        tags_str  = ", ".join(real_tags) if real_tags else "sem tags"
        ctk.CTkLabel(win, text=f"Tags: {tags_str}").pack()

        ctk.CTkButton(
            win, text="Editar Tags",
            command=lambda: [win.destroy(), self._open_tag_editor(photo["id"])]
        ).pack(pady=5)

        ctk.CTkButton(
            win, text="Abrir no Explorador",
            command=lambda: os.startfile(
                os.path.join(utils.get_photos_dir(), photo["filename"])
            )
        ).pack(pady=2)

        def confirmar_remocao():
            if messagebox.askyesno(
                "Remover foto",
                f"Remover '{photo.get('original_name', 'esta foto')}'?\n\nEsta ação não pode ser desfeita.",
                icon="warning"
            ):
                db.delete_photo(photo["id"], photo["filename"])
                win.destroy()
                self._refresh_tag_list()
                self._load_photos()

        ctk.CTkButton(
            win, text="Remover Foto",
            fg_color="#c0392b", hover_color="#96281b",
            command=confirmar_remocao
        ).pack(pady=(15, 5))

    def _open_tag_editor(self, photo_id):
        win = ctk.CTkToplevel(self)
        win.title("Editar Tags")
        win.geometry("400x500")
        win.lift(); win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.grab_set()

        ctk.CTkLabel(win, text="Tags desta foto", font=("Arial", 14, "bold")).pack(pady=10)

        current_tags = set(db.get_photo_real_tags(photo_id))
        vars_map     = {}
        scroll       = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=15)

        for tag in db.get_user_tags():
            var = ctk.BooleanVar(value=tag in current_tags)
            ctk.CTkCheckBox(scroll, text=tag, variable=var).pack(anchor="w", pady=2)
            vars_map[tag] = var

        ctk.CTkLabel(win, text="Adicionar nova tag:").pack()
        entry = ctk.CTkEntry(win, placeholder_text="Ex: Viagem 2025")
        entry.pack(fill="x", padx=15, pady=5)

        def add_new():
            name = entry.get().strip()
            if name and name not in vars_map:
                v = ctk.BooleanVar(value=True)
                ctk.CTkCheckBox(scroll, text=name, variable=v).pack(anchor="w", pady=2)
                vars_map[name] = v
                entry.delete(0, "end")

        ctk.CTkButton(win, text="+ Adicionar", command=add_new).pack(pady=2)

        def save():
            selected = [t for t, v in vars_map.items() if v.get()]
            db.set_photo_tags(photo_id, selected)
            win.destroy()
            self._refresh_tag_list()
            self._load_photos()

        ctk.CTkButton(win, text="Salvar", fg_color="green", command=save).pack(pady=15)