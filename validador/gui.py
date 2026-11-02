# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""
Interfaz gráfica del validador (CustomTkinter).

El diseño se adapta al tamaño de la ventana: con ventana ancha hay barra
lateral; al achicarla, la navegación pasa a una barra superior, los campos se
apilan en una columna y la tabla oculta las columnas menos importantes.
"""

import datetime
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter.font as tkfont
import traceback
import webbrowser
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk

from . import APP_NAME, LINKEDIN, __author__, __version__, config, core, exportar, nomina, online
from .core import ERROR, INVALIDO, VALIDO

FUENTE = "Segoe UI"

# Paleta tomada del logo USACH (turquesa #17A499, naranjo #EB7703, gris #323E48). (claro, oscuro)
P = {
    "bg":        ("#F2F5F6", "#0E1416"),
    "panel":     ("#FFFFFF", "#162024"),
    "borde":     ("#E1E7EA", "#24323A"),
    "campo":     ("#F7F9FA", "#111A1E"),
    "cabecera":  ("#F3F6F7", "#1B272C"),
    "hover":     ("#EBF0F2", "#1F2D33"),
    "texto":     ("#1D2A31", "#E4ECEF"),
    "suave":     ("#62717A", "#8B9DA5"),
    "acento":    ("#17A499", "#1FB3A7"),
    "acento_h":  ("#11877E", "#17A499"),
    "acento_bg": ("#E2F4F2", "#12302E"),
    "naranjo":   ("#EB7703", "#F5891C"),
    "ok":        ("#16803C", "#4ADE80"),
    "ok_bg":     ("#E2F5E9", "#12301E"),
    "mal":       ("#C62A31", "#F87171"),
    "mal_bg":    ("#FCE7E7", "#3A191B"),
    "mal_h":     ("#A72128", "#EF5350"),
    "aviso":     ("#B45309", "#FBBF24"),
    "aviso_bg":  ("#FEF2D9", "#382C10"),
    "seg":       ("#E8EDEF", "#0F171A"),
    "seg_sel":   ("#FFFFFF", "#26363D"),
    "marca_agua": ("#8A989F", "#5F7078"),
}


def segmentado(master, app, valores, comando=None, **kw):
    return ctk.CTkSegmentedButton(master, values=valores, command=comando, font=app.f["normal"], corner_radius=9,
                                  fg_color=P["seg"], selected_color=P["seg_sel"], selected_hover_color=P["seg_sel"],
                                  unselected_color=P["seg"], unselected_hover_color=P["hover"],
                                  text_color=P["texto"], **kw)

GLIFOS = {
    "online": "\uE774", "nomina": "\uE716", "carpeta": "\uE8B7", "carpeta_abierta": "\uE838",
    "excel": "\uE9F9", "validar": "\uE768", "detener": "\uE71A", "exportar": "\uE896",
    "mover": "\uE8DE", "buscar": "\uE721", "reintentar": "\uE72C", "sol": "\uE706", "luna": "\uE708",
    "abajo": "\uE70D", "arriba": "\uE70E", "total": "\uEB95", "valido": "\uE930",
    "invalido": "\uEA39", "error": "\uE7BA", "info": "\uE946", "pdf": "\uE8A5", "copiar": "\uE8C8",
    "listo": "\uE73E", "reloj": "\uE823",
}

ESTADOS = {
    VALIDO: ("Válido", "ok"),
    INVALIDO: ("Inválido", "mal"),
    ERROR: ("Error", "aviso"),
}

# (id, título, ancho fijo o None, peso para repartir el ancho restante)
COLUMNAS = [
    ("nombre", "Nombre", None, 2.6),
    ("rut", "RUT", 112, 0),
    ("carrera", "Carrera", None, 1.8),
    ("detalle", "Detalle", None, 3.2),
    ("archivo", "Archivo", None, 1.6),
]
ANCHO_ESTADO = 112
COLUMNAS_VISIBLES = {
    "ancho": ("nombre", "rut", "carrera", "detalle", "archivo"),
    "medio": ("nombre", "rut", "detalle"),
    "angosto": ("nombre", "detalle"),
}


def recurso(nombre):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "recursos", nombre)


def es_oscuro():
    return ctk.get_appearance_mode() == "Dark"


def color(clave):
    return P[clave][1 if es_oscuro() else 0]


class Iconos:
    """Íconos nítidos a partir de la fuente de íconos de Windows (Segoe Fluent Icons / MDL2)."""

    def __init__(self, escala):
        fuentes = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        self.fuente = next((p for p in (os.path.join(fuentes, n) for n in ("SegoeIcons.ttf", "segmdl2.ttf"))
                            if os.path.exists(p)), None)
        self.escala = escala
        self._cache = {}

    def imagen_pil(self, nombre, rgb, tam):
        px = max(8, round(tam * self.escala))
        im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        if self.fuente:
            fnt = ImageFont.truetype(self.fuente, px)
            d = ImageDraw.Draw(im)
            x0, y0, x1, y1 = d.textbbox((0, 0), GLIFOS[nombre], font=fnt)
            d.text(((px - (x1 - x0)) / 2 - x0, (px - (y1 - y0)) / 2 - y0), GLIFOS[nombre], font=fnt, fill=rgb)
        return im

    def __call__(self, nombre, tono="texto", tam=16):
        """`tono` es una clave de la paleta o un color fijo ('#FFFFFF')."""
        if not self.fuente:
            return None
        clave = (nombre, tono, tam)
        if clave not in self._cache:
            claro, oscuro = P[tono] if tono in P else (tono, tono)
            self._cache[clave] = ctk.CTkImage(self.imagen_pil(nombre, claro, tam),
                                              self.imagen_pil(nombre, oscuro, tam), size=(tam, tam))
        return self._cache[clave]


# ------------------------------------------------------------ widgets ---

def tarjeta(master, **kw):
    return ctk.CTkFrame(master, fg_color=P["panel"], corner_radius=14, border_width=1, border_color=P["borde"], **kw)


def boton_primario(master, app, texto, icono, comando, **kw):
    return ctk.CTkButton(master, text=texto, image=app.iconos(icono, "#FFFFFF"), compound="left", command=comando,
                         height=40, corner_radius=10, font=app.f["boton"], fg_color=P["acento"],
                         hover_color=P["acento_h"], text_color="#FFFFFF", **kw)


def boton_secundario(master, app, texto, icono, comando, **kw):
    kw.setdefault("height", 36)
    return ctk.CTkButton(master, text=texto, image=app.iconos(icono) if icono else None, compound="left",
                         command=comando, corner_radius=9, font=app.f["normal"], fg_color=P["panel"],
                         hover_color=P["hover"], border_width=1, border_color=P["borde"], text_color=P["texto"],
                         text_color_disabled=P["suave"], **kw)


def entrada(master, app, placeholder="", **kw):
    return ctk.CTkEntry(master, placeholder_text=placeholder, height=38, corner_radius=9, border_width=1,
                        fg_color=P["campo"], border_color=P["borde"], text_color=P["texto"],
                        placeholder_text_color=P["suave"], font=app.f["normal"], **kw)


def casilla(master, app, texto, valor):
    var = ctk.BooleanVar(value=valor)
    caja = ctk.CTkCheckBox(master, text=texto, variable=var, font=app.f["normal"], text_color=P["texto"],
                           fg_color=P["acento"], hover_color=P["acento_h"], border_color=P["suave"],
                           checkbox_width=20, checkbox_height=20, corner_radius=6, border_width=2)
    return caja, var


class Campo(ctk.CTkFrame):
    """Título + control + texto de ayuda opcional."""

    def __init__(self, master, app, titulo, ayuda=None, completo=True):
        super().__init__(master, fg_color="transparent")
        self.completo = completo
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=titulo, font=app.f["etiqueta"], text_color=P["texto"], anchor="w",
                     height=18).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo.grid(row=1, column=0, sticky="ew")
        self.cuerpo.grid_columnconfigure(0, weight=1)
        self.ayuda = ctk.CTkLabel(self, text=ayuda or "", font=app.f["chico"], text_color=P["suave"],
                                  anchor="w", justify="left", height=16)
        if ayuda is not None:
            self.ayuda.grid(row=2, column=0, sticky="w", pady=(5, 0))

    def aviso(self, texto, tono="suave"):
        self.ayuda.configure(text=texto, text_color=P[tono])
        self.ayuda.grid(row=2, column=0, sticky="w", pady=(5, 0))


class SelectorRuta(Campo):
    def __init__(self, master, app, titulo, placeholder, carpeta=True, tipos=None, ayuda=None, al_cambiar=None):
        super().__init__(master, app, titulo, ayuda)
        self.carpeta, self.tipos, self.al_cambiar = carpeta, tipos, al_cambiar
        self._ultimo = None
        self.entrada = entrada(self.cuerpo, app, placeholder)
        self.entrada.grid(row=0, column=0, sticky="ew")
        self.boton = boton_secundario(self.cuerpo, app, "Examinar", "carpeta" if carpeta else "excel",
                                      self.examinar, width=116, height=38)
        self.boton.grid(row=0, column=1, padx=(8, 0))
        self.entrada.bind("<FocusOut>", lambda _: self._notificar())
        self.entrada.bind("<Return>", lambda _: self._notificar())

    def get(self):
        return self.entrada.get().strip().strip('"')

    def set(self, valor):
        self.entrada.delete(0, "end")
        if valor:
            self.entrada.insert(0, os.path.normpath(valor))
        self._notificar()

    def examinar(self):
        actual = self.get()
        inicial = actual if os.path.isdir(actual) else os.path.dirname(actual) if actual else None
        if self.carpeta:
            ruta = filedialog.askdirectory(parent=self, initialdir=inicial, title="Elegir carpeta con los PDF")
        else:
            ruta = filedialog.askopenfilename(parent=self, initialdir=inicial, filetypes=self.tipos,
                                              title="Elegir nómina")
        if ruta:
            self.set(os.path.normpath(ruta))

    def _notificar(self):
        valor = self.get()
        if valor != self._ultimo:
            self._ultimo = valor
            if self.al_cambiar:
                self.al_cambiar(valor)


class TarjetaDato(ctk.CTkFrame):
    def __init__(self, master, app, titulo, icono, tono, al_click):
        super().__init__(master, fg_color=P["panel"], corner_radius=14, border_width=1, border_color=P["borde"])
        self.tono = tono
        self.grid_columnconfigure(1, weight=1)
        self.insignia =ctk.CTkLabel(self, text="", image=app.iconos(icono, tono, 20), width=42, height=42,
                                     corner_radius=11, fg_color=P[tono + "_bg"])
        self.insignia.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=14)
        self.valor = ctk.CTkLabel(self, text="0", font=app.f["cifra"], text_color=P["texto"], anchor="w", height=30)
        self.valor.grid(row=0, column=1, sticky="sw", pady=(12, 0), padx=(0, 12))
        self.titulo = ctk.CTkLabel(self, text=titulo, font=app.f["chico"], text_color=P["suave"], anchor="w",
                                   height=18)
        self.titulo.grid(row=1, column=1, sticky="nw", pady=(0, 12), padx=(0, 12))
        for w in (self, self.insignia, self.valor, self.titulo):
            w.bind("<Button-1>", lambda _: al_click())
            w.configure(cursor="hand2")

    def set(self, n):
        self.valor.configure(text=f"{n:,}".replace(",", "."))

    def compacta(self, si):
        """En ventanas angostas: sin ícono y con menos relleno, para que quepan 4 en una fila."""
        if si:
            self.insignia.grid_remove()
            self.valor.grid_configure(padx=(12, 6), pady=(8, 0))
            self.titulo.grid_configure(padx=(12, 6), pady=(0, 8))
        else:
            self.insignia.grid()
            self.valor.grid_configure(padx=(0, 12), pady=(12, 0))
            self.titulo.grid_configure(padx=(0, 12), pady=(0, 12))
        self.valor.configure(text_color=P[self.tono] if si else P["texto"])


# --------------------------------------------------------------- página ---

class Pagina(ctk.CTkFrame):
    """Estructura común: encabezado, configuración, progreso, resumen y tabla de resultados."""

    clave = titulo = subtitulo = icono = ""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.cfg = app.cfg
        self.resultados = []
        self.por_iid = {}
        self.trabajando = False
        self.carpeta_validada = ""
        self.filtro = None
        self.orden = (None, False)
        self.disposicion = None
        self._busqueda_pendiente = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._crear_encabezado()
        self._crear_configuracion()
        self._crear_progreso()
        self._crear_resumen()
        self._crear_resultados()
        self._actualizar_vacio()

    # ---- construcción

    def _crear_encabezado(self):
        f = self.app.f
        enc = ctk.CTkFrame(self, fg_color="transparent")
        enc.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        enc.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(enc, text="", image=self.app.iconos(self.icono, "acento", 24), width=52, height=52,
                     corner_radius=14, fg_color=P["acento_bg"]).grid(row=0, column=0, rowspan=2, padx=(0, 14))
        ctk.CTkLabel(enc, text=self.titulo, font=f["titulo"], text_color=P["texto"], anchor="w",
                     height=30).grid(row=0, column=1, sticky="sw")
        self.lbl_subtitulo = ctk.CTkLabel(enc, text=self.subtitulo, font=f["normal"], text_color=P["suave"],
                                          anchor="w", justify="left")
        self.lbl_subtitulo.grid(row=1, column=1, sticky="nw")

    def _crear_configuracion(self):
        f = self.app.f
        self.tarjeta_cfg = tarjeta(self)
        self.tarjeta_cfg.grid(row=1, column=0, sticky="ew")
        self.tarjeta_cfg.grid_columnconfigure(0, weight=1)

        cab = ctk.CTkFrame(self.tarjeta_cfg, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 0))
        cab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cab, text="Configuración", font=f["seccion"], text_color=P["texto"],
                     anchor="w").grid(row=0, column=0, sticky="w")
        self.btn_plegar = ctk.CTkButton(cab, text="", image=self.app.iconos("arriba", "suave", 14), width=32,
                                        height=28, corner_radius=8, fg_color="transparent",
                                        hover_color=P["hover"], command=self.alternar_configuracion)
        self.btn_plegar.grid(row=0, column=1)
        self.cab_cfg = cab

        self.marco_campos = ctk.CTkFrame(self.tarjeta_cfg, fg_color="transparent")
        self.marco_campos.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 0))
        self.campos = self.construir_campos(self.marco_campos)

        self.marco_acciones = ctk.CTkFrame(self.tarjeta_cfg, fg_color="transparent")
        self.marco_acciones.grid(row=2, column=0, sticky="ew", padx=20, pady=(16, 18))
        self.marco_acciones.grid_columnconfigure(0, weight=1)
        self.marco_casillas = ctk.CTkFrame(self.marco_acciones, fg_color="transparent")
        self.casillas = []
        self.chk_recursivo, self.var_recursivo = casilla(
            self.marco_casillas, self.app, "Incluir subcarpetas", self.cfg.get(f"{self.clave}_recursivo", False))
        self.chk_duplicados, self.var_duplicados = casilla(
            self.marco_casillas, self.app, "Anular RUT repetidos", self.cfg.get(f"{self.clave}_duplicados", True))
        self.casillas = [self.chk_recursivo, self.chk_duplicados]
        self.btn_validar = boton_primario(self.marco_acciones, self.app, "Validar", "validar", self.iniciar,
                                          width=150)
        self.plegada = False

    def _crear_progreso(self):
        f = self.app.f
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.grid(row=2, column=0, sticky="ew", pady=(16, 14))
        fila.grid_columnconfigure(0, weight=1)
        self.barra = ctk.CTkProgressBar(fila, height=6, corner_radius=3, fg_color=P["borde"],
                                        progress_color=P["acento"])
        self.barra.set(0)
        self.barra.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.lbl_estado = ctk.CTkLabel(fila, text="Listo para validar.", font=f["chico"], text_color=P["suave"],
                                       anchor="w", compound="left", height=18,
                                       image=self.app.iconos("info", "suave", 14))
        self.lbl_estado.grid(row=1, column=0, sticky="w")

    def _crear_resumen(self):
        self.marco_resumen = ctk.CTkFrame(self, fg_color="transparent")
        self.marco_resumen.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        self.datos = {
            None: TarjetaDato(self.marco_resumen, self.app, "Total", "total", "acento", lambda: self.filtrar("Todos")),
            VALIDO: TarjetaDato(self.marco_resumen, self.app, "Válidos", "valido", "ok",
                                lambda: self.filtrar("Válidos")),
            INVALIDO: TarjetaDato(self.marco_resumen, self.app, "Inválidos", "invalido", "mal",
                                  lambda: self.filtrar("Inválidos")),
            ERROR: TarjetaDato(self.marco_resumen, self.app, "Errores", "error", "aviso",
                               lambda: self.filtrar("Errores")),
        }

    def _crear_resultados(self):
        app, f = self.app, self.app.f
        self.tarjeta_res = tarjeta(self)
        self.tarjeta_res.grid(row=4, column=0, sticky="nsew")
        self.tarjeta_res.grid_columnconfigure(0, weight=1)
        self.tarjeta_res.grid_rowconfigure(2, weight=1)

        barra = ctk.CTkFrame(self.tarjeta_res, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 0))
        barra.grid_columnconfigure(2, weight=1)
        self.seg_filtro = segmentado(barra, app, ["Todos", "Válidos", "Inválidos", "Errores"], self.filtrar,
                                     height=34, dynamic_resizing=False, width=330)
        self.seg_filtro.set("Todos")
        self.seg_filtro.grid(row=0, column=0, sticky="w")

        caja = ctk.CTkFrame(barra, fg_color=P["campo"], corner_radius=9, border_width=1, border_color=P["borde"],
                            height=34)
        caja.grid(row=0, column=1, sticky="w", padx=(10, 0))
        caja.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(caja, text="", image=app.iconos("buscar", "suave", 14), width=20).grid(row=0, column=0,
                                                                                          padx=(10, 0))
        self.ent_buscar = ctk.CTkEntry(caja, placeholder_text="Buscar nombre, RUT, archivo…", height=32,
                                       border_width=0, fg_color=P["campo"], text_color=P["texto"],
                                       placeholder_text_color=P["suave"], font=f["normal"], width=230)
        self.ent_buscar.grid(row=0, column=1, sticky="ew", padx=(2, 6), pady=1)
        self.ent_buscar.bind("<KeyRelease>", lambda _: self._buscar_luego())
        self.caja_buscar = caja

        self.marco_botones = ctk.CTkFrame(barra, fg_color="transparent")
        self.btn_reintentar = boton_secundario(self.marco_botones, app, "Reintentar errores", "reintentar",
                                               self.reintentar_errores)
        self.btn_mover = boton_secundario(self.marco_botones, app, "Mover inválidos", "mover", self.mover_invalidos)
        self.btn_exportar = boton_secundario(self.marco_botones, app, "Exportar", "exportar", self.exportar)
        self.btn_mover.grid(row=0, column=1, padx=(8, 0))
        self.btn_exportar.grid(row=0, column=2, padx=(8, 0))
        self.barra_herramientas = barra

        marco = ctk.CTkFrame(self.tarjeta_res, fg_color="transparent")
        marco.grid(row=2, column=0, sticky="nsew", padx=16, pady=(12, 0))
        marco.grid_columnconfigure(0, weight=1)
        marco.grid_rowconfigure(0, weight=1)
        self.tabla = ttk.Treeview(marco, style="Resultados.Treeview", columns=[c[0] for c in COLUMNAS],
                                  show="tree headings", selectmode="browse")
        self.tabla.heading("#0", text="  Estado", anchor="w", command=lambda: self.ordenar("estado"))
        self.tabla.column("#0", width=self._px(ANCHO_ESTADO), minwidth=20, stretch=False, anchor="w")
        for cid, titulo, *_ in COLUMNAS:
            self.tabla.heading(cid, text=f"  {titulo}", anchor="w", command=lambda c=cid: self.ordenar(c))
            self.tabla.column(cid, width=self._px(120), minwidth=20, stretch=False, anchor="w")
        sb_y = ctk.CTkScrollbar(marco, command=self.tabla.yview, button_color=P["borde"],
                                button_hover_color=P["suave"], width=12)
        self.tabla.configure(yscrollcommand=sb_y.set)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.tabla.bind("<Configure>", lambda _: self._ajustar_columnas())
        self.tabla.bind("<<TreeviewSelect>>", lambda _: self._mostrar_detalle())
        self.tabla.bind("<Double-1>", self._abrir_fila)
        self.tabla.bind("<Return>", self._abrir_fila)
        self.tabla.bind("<Button-3>", self._menu_contextual)

        # Aviso de tabla vacía: cubre toda la tabla (encabezados incluidos) con un mensaje centrado.
        self.vacio = ctk.CTkFrame(marco, fg_color=P["panel"], corner_radius=0)
        centro = ctk.CTkFrame(self.vacio, fg_color="transparent")
        centro.place(relx=0.5, rely=0.5, anchor="center")
        self.vacio_icono = ctk.CTkLabel(centro, text="", image=app.iconos("pdf", "suave", 32))
        self.vacio_icono.pack(pady=(0, 8))
        self.vacio_titulo = ctk.CTkLabel(centro, text="", font=f["seccion"], text_color=P["texto"], height=22)
        self.vacio_titulo.pack()
        self.vacio_texto = ctk.CTkLabel(centro, text="", font=f["normal"], text_color=P["suave"], height=20)
        self.vacio_texto.pack()
        self.vacio.bind("<Configure>", lambda e: self.vacio_icono.pack(before=self.vacio_titulo, pady=(0, 8))
                        if e.height > self._px(130) else self.vacio_icono.pack_forget())

        self.lbl_detalle = ctk.CTkLabel(self.tarjeta_res, text="Doble clic en una fila abre el PDF · clic derecho "
                                        "para más opciones.", font=f["chico"], text_color=P["suave"], anchor="w",
                                        justify="left")
        self.lbl_detalle.grid(row=3, column=0, sticky="ew", padx=18, pady=(10, 14))

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Abrir PDF", command=lambda: self._abrir_fila())
        self.menu.add_command(label="Mostrar en la carpeta", command=self._mostrar_en_carpeta)
        self.menu.add_separator()
        self.menu.add_command(label="Copiar detalle", command=lambda: self._copiar("detalle"))
        self.menu.add_command(label="Copiar RUT", command=lambda: self._copiar("rut"))
        self._actualizar_botones()

    def _px(self, n):
        return round(n * self.app.escala)

    # ---- disposición adaptable

    def disponer(self, modo):
        if modo == self.disposicion:
            return
        self.disposicion = modo
        angosto = modo == "angosto"

        columnas = 1 if angosto else 2
        for w in self.campos:
            w.grid_forget()
        for c in range(2):
            usada = c < columnas
            self.marco_campos.grid_columnconfigure(c, weight=int(usada), uniform="campos" if usada else "")
        fila = col = 0
        for w in self.campos:
            if w.completo or columnas == 1:
                if col:
                    fila, col = fila + 1, 0
                w.grid(row=fila, column=0, columnspan=columnas, sticky="ew", pady=(0, 14))
                fila += 1
            else:
                w.grid(row=fila, column=col, sticky="ew", pady=(0, 14), padx=(0, 16) if col == 0 else (0, 0))
                col = (col + 1) % columnas
                fila += col == 0

        for i, c in enumerate(self.casillas):
            c.grid_forget()
            if angosto:
                c.grid(row=i, column=0, sticky="w", pady=(0, 8))
            else:
                c.grid(row=0, column=i, sticky="w", padx=(0, 22))
        self.marco_casillas.grid(row=0, column=0, sticky="w")
        self.btn_validar.grid_forget()
        if angosto:
            self.btn_validar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        else:
            self.btn_validar.grid(row=0, column=1, sticky="e")

        for w in self.datos.values():
            w.grid_forget()
        sep = 4 if angosto else 6
        for c, w in enumerate(self.datos.values()):
            self.marco_resumen.grid_columnconfigure(c, weight=1, uniform="datos")
            w.grid(row=0, column=c, sticky="ew", padx=(0 if c == 0 else sep, 0 if c == 3 else sep))

        self.marco_botones.grid_forget()
        self.caja_buscar.grid_forget()
        if modo == "ancho":
            self.caja_buscar.grid(row=0, column=1, sticky="w", padx=(10, 0))
            self.marco_botones.grid(row=0, column=3, sticky="e", padx=(10, 0))
        elif modo == "medio":
            self.caja_buscar.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(10, 0))
            self.marco_botones.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        else:
            self.caja_buscar.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
            self.marco_botones.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.tabla.configure(displaycolumns=COLUMNAS_VISIBLES[modo])
        self._ajustar_columnas()
        for w in self.datos.values():
            w.compacta(angosto)

    def _ajustar_columnas(self):
        """Reparte el ancho de la tabla entre las columnas visibles (sin barra horizontal)."""
        disponible = self.tabla.winfo_width() - 2
        if disponible < 50:
            return
        visibles = [c for c in COLUMNAS if c[0] in COLUMNAS_VISIBLES[self.disposicion or "ancho"]]
        fijo = self._px(ANCHO_ESTADO) + sum(self._px(c[2]) for c in visibles if c[2])
        resto = max(0, disponible - fijo)
        peso_total = sum(c[3] for c in visibles if not c[2]) or 1
        for cid, _, ancho, peso in visibles:
            self.tabla.column(cid, width=self._px(ancho) if ancho else int(resto * peso / peso_total))

    def ajustar_ancho(self, ancho):
        self.lbl_subtitulo.configure(wraplength=max(200, ancho - 120))
        self.lbl_detalle.configure(wraplength=max(200, ancho - 60))
        for w in self.campos:
            columnas = 1 if w.completo or self.disposicion == "angosto" else 2
            w.ayuda.configure(wraplength=max(160, (ancho - 80) / columnas - 16))

    def alternar_configuracion(self, plegar=None):
        self.plegada = (not self.plegada) if plegar is None else plegar
        if self.plegada:
            self.marco_campos.grid_remove()
            self.marco_acciones.grid_remove()
            self.cab_cfg.grid_configure(pady=(12, 12))
        else:
            self.marco_campos.grid()
            self.marco_acciones.grid()
            self.cab_cfg.grid_configure(pady=(14, 0))
        self.btn_plegar.configure(image=self.app.iconos("abajo" if self.plegada else "arriba", "suave", 14))

    # ---- a implementar por cada modo

    def construir_campos(self, master):
        raise NotImplementedError

    def leer_parametros(self):
        raise NotImplementedError

    def ejecutar(self, rutas, params, avance, cancelado):
        raise NotImplementedError

    def guardar_cfg(self):
        self.cfg[f"{self.clave}_recursivo"] = self.var_recursivo.get()
        self.cfg[f"{self.clave}_duplicados"] = self.var_duplicados.get()

    # ---- ejecución en segundo plano

    def iniciar(self):
        if self.trabajando:
            self.cancelado.set()
            self._estado("Cancelando…", "reloj", "suave")
            return
        params = self.leer_parametros()
        if params is None:
            return
        self.guardar_cfg()
        self.app.guardar_cfg()
        self.carpeta_validada = params["carpeta"]
        self._arrancar(params, None)

    def reintentar_errores(self):
        rutas = [r.ruta for r in self.resultados if r.estado == ERROR]
        params = self.leer_parametros() if rutas and not self.trabajando else None
        if params:
            self._arrancar(params, rutas)

    def _arrancar(self, params, rutas):
        self.cancelado = threading.Event()
        self.cola = queue.SimpleQueue()
        self.reintento = rutas is not None
        self.trabajando = True
        self.t0 = time.perf_counter()
        self.total = len(rutas) if rutas else 0
        self.hechos = 0
        if not self.reintento:
            self.resultados = []
            self._limpiar_tabla()
        self.btn_validar.configure(text="Cancelar", image=self.app.iconos("detener", "#FFFFFF"),
                                   fg_color=P["mal"], hover_color=P["mal_h"])
        self.barra.set(0)
        self._estado("Buscando archivos PDF…", "reloj", "suave")
        self._actualizar_botones()
        self.alternar_configuracion(plegar=True)  # Deja el espacio a los resultados; la flecha la vuelve a abrir.
        threading.Thread(target=self._hilo, args=(params, rutas), daemon=True).start()
        self.after(50, self._sondear)

    def _hilo(self, params, rutas):
        try:
            if rutas is None:
                rutas = core.listar_pdfs(params["carpeta"], params["recursivo"])
            self.cola.put(("inicio", len(rutas)))
            res = self.ejecutar(rutas, params, lambda r, h, t: self.cola.put(("avance", r, h)), self.cancelado)
            self.cola.put(("fin", res))
        except Exception as e:
            traceback.print_exc()
            self.cola.put(("falla", str(e) or e.__class__.__name__))

    def _sondear(self):
        nuevos = 0
        try:
            for _ in range(500):
                msg = self.cola.get_nowait()
                if msg[0] == "inicio":
                    self.total = msg[1]
                elif msg[0] == "avance":
                    self.hechos = msg[2]
                    if not self.reintento:
                        self._agregar(msg[1])
                        nuevos += 1
                elif msg[0] == "fin":
                    return self._terminar(msg[1])
                elif msg[0] == "falla":
                    return self._terminar(None, msg[1])
        except queue.Empty:
            pass
        if nuevos:
            self._actualizar_resumen()
            self._actualizar_vacio()
        if self.total:
            self.barra.set(self.hechos / self.total)
            self._estado(f"Validando {self.hechos} de {self.total} · {self._transcurrido()}", "reloj", "suave")
        self.after(60, self._sondear)

    def _terminar(self, res, falla=None):
        self.trabajando = False
        self.btn_validar.configure(text="Validar", image=self.app.iconos("validar", "#FFFFFF"),
                                   fg_color=P["acento"], hover_color=P["acento_h"])
        if falla:
            self.barra.set(0)
            self._estado(f"No se pudo completar: {falla}", "error", "mal")
            messagebox.showerror(APP_NAME, falla, parent=self)
        else:
            if self.reintento:
                nuevos = {r.ruta: r for r in res}
                self.resultados = [nuevos.get(r.ruta, r) for r in self.resultados]
            else:
                self.resultados = res
            if self.var_duplicados.get():
                core.anular_duplicados(self.resultados)
            self.refrescar_tabla()
            if self.cancelado.is_set():
                self._estado(f"Cancelado: {len(res)} de {self.total} archivos procesados.", "error", "aviso")
            elif not self.total:
                self.barra.set(0)
                self._estado("No se encontraron archivos PDF en la carpeta.", "error", "aviso")
            else:
                self.barra.set(1)
                n = sum(r.estado == VALIDO for r in self.resultados)
                errores = sum(r.estado == ERROR for r in self.resultados)
                texto = (f"{len(res)} archivo{'s' * (len(res) != 1)} procesado{'s' * (len(res) != 1)} en "
                         f"{self._transcurrido()} · {n} válido{'s' * (n != 1)}")
                if errores:
                    texto += f" · {errores} con error de conexión (usa «Reintentar errores»)"
                self._estado(texto, "listo" if not errores else "error", "ok" if not errores else "aviso")
        self._actualizar_botones()

    def _transcurrido(self):
        s = time.perf_counter() - self.t0
        return f"{s:.1f} s".replace(".", ",") if s < 60 else f"{int(s // 60)} min {int(s % 60)} s"

    def _estado(self, texto, icono, tono):
        self.lbl_estado.configure(text=f"  {texto}", text_color=P[tono], image=self.app.iconos(icono, tono, 14))

    # ---- tabla

    def _limpiar_tabla(self):
        self.tabla.delete(*self.tabla.get_children())
        self.por_iid.clear()
        self._actualizar_resumen()
        self._actualizar_vacio()
        self._mostrar_detalle()

    def _visible(self, r, consulta):
        if self.filtro and r.estado != self.filtro:
            return False
        if consulta:
            texto = " ".join((r.nombre, r.rut, core.formatear_rut(r.rut), r.carrera, r.detalle, r.archivo))
            return consulta in core.normalizar_clave(texto)
        return True

    def _agregar(self, r):
        self.resultados.append(r)
        if self._visible(r, core.normalizar_clave(self.ent_buscar.get())):
            self._insertar(r)

    def _insertar(self, r):
        iid = str(len(self.por_iid))
        self.por_iid[iid] = r
        etiqueta = ESTADOS[r.estado][0]
        par = "par" if len(self.por_iid) % 2 else "impar"
        self.tabla.insert("", "end", iid=iid, text=f" {etiqueta}", image=self.app.img_estado[r.estado],
                          values=[f"  {v}" for v in (r.nombre, core.formatear_rut(r.rut), r.carrera, r.detalle,
                                                     r.archivo)], tags=(par,))

    def refrescar_tabla(self):
        self.tabla.delete(*self.tabla.get_children())
        self.por_iid.clear()
        consulta = core.normalizar_clave(self.ent_buscar.get())
        filas = [r for r in self.resultados if self._visible(r, consulta)]
        col, desc = self.orden
        if col:
            filas.sort(key=self._clave_orden(col), reverse=desc)
        for r in filas:
            self._insertar(r)
        self._actualizar_resumen()
        self._actualizar_vacio()
        self._mostrar_detalle()

    @staticmethod
    def _clave_orden(col):
        if col == "estado":
            orden = {VALIDO: 0, INVALIDO: 1, ERROR: 2}
            return lambda r: orden[r.estado]
        if col == "rut":
            return lambda r: int(r.rut.split("-")[0]) if r.rut else 0
        return lambda r: core.normalizar_clave(getattr(r, col))

    def ordenar(self, col):
        actual, desc = self.orden
        self.orden = (col, not desc if actual == col else False)
        flecha = " ▼" if self.orden[1] else " ▲"
        self.tabla.heading("#0", text="  Estado" + (flecha if col == "estado" else ""))
        for cid, titulo, *_ in COLUMNAS:
            self.tabla.heading(cid, text=f"  {titulo}" + (flecha if cid == col else ""))
        self.refrescar_tabla()

    def filtrar(self, valor):
        self.seg_filtro.set(valor)
        self.filtro = {"Válidos": VALIDO, "Inválidos": INVALIDO, "Errores": ERROR}.get(valor)
        self.refrescar_tabla()

    def _buscar_luego(self):
        if self._busqueda_pendiente:
            self.after_cancel(self._busqueda_pendiente)
        self._busqueda_pendiente = self.after(150, self.refrescar_tabla)

    def _actualizar_resumen(self):
        self.datos[None].set(len(self.resultados))
        for estado in (VALIDO, INVALIDO, ERROR):
            self.datos[estado].set(sum(r.estado == estado for r in self.resultados))
        self._actualizar_botones()

    def _actualizar_botones(self):
        hay_inv = any(r.estado == INVALIDO for r in self.resultados)
        hay_err = any(r.estado == ERROR for r in self.resultados)
        libre = "disabled" if self.trabajando else "normal"
        self.btn_exportar.configure(state=libre if self.resultados else "disabled")
        self.btn_mover.configure(state=libre if hay_inv else "disabled")
        if hay_err and not self.trabajando:
            self.btn_reintentar.grid(row=0, column=0)
        else:
            self.btn_reintentar.grid_forget()

    def _actualizar_vacio(self):
        if self.tabla.get_children():
            self.vacio.place_forget()
            return
        if self.trabajando:
            titulo, texto = "Validando…", "Los resultados aparecerán aquí a medida que se procesen."
        elif self.resultados:
            titulo, texto = "Sin coincidencias", "Prueba con otro filtro o búsqueda."
        else:
            titulo, texto = "Aún no hay resultados", "Elige la carpeta con los PDF y presiona «Validar»."
        self.vacio_titulo.configure(text=titulo)
        self.vacio_texto.configure(text=texto)
        self.vacio.place(x=0, y=0, relwidth=1, relheight=1)

    def actualizar_iconos_tabla(self):
        for iid, r in self.por_iid.items():
            self.tabla.item(iid, image=self.app.img_estado[r.estado])

    def _seleccion(self):
        sel = self.tabla.selection()
        return self.por_iid.get(sel[0]) if sel else None

    def _mostrar_detalle(self):
        r = self._seleccion()
        if not r:
            self.lbl_detalle.configure(text="Doble clic en una fila abre el PDF · clic derecho para más opciones.",
                                       text_color=P["suave"])
            return
        extra = [r.archivo]
        if r.folio:
            extra.append(f"Folio {r.folio} · código {r.codigo}")
        if r.semestre:
            extra.append(r.semestre)
        self.lbl_detalle.configure(text=f"{'  ·  '.join(extra)}\n{ESTADOS[r.estado][0]}: {r.detalle}",
                                   text_color=P[ESTADOS[r.estado][1]] if r.estado != VALIDO else P["texto"])

    def _abrir_fila(self, evento=None):
        if evento is not None and evento.type == tk.EventType.ButtonPress and \
                self.tabla.identify_region(evento.x, evento.y) == "heading":
            return
        r = self._seleccion()
        if r:
            try:
                os.startfile(r.ruta)
            except OSError as e:
                messagebox.showerror(APP_NAME, f"No se pudo abrir el archivo:\n{e}", parent=self)

    def _mostrar_en_carpeta(self):
        r = self._seleccion()
        if r:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(r.ruta)])

    def _copiar(self, campo):
        r = self._seleccion()
        if r:
            self.clipboard_clear()
            self.clipboard_append(core.formatear_rut(r.rut) if campo == "rut" else r.detalle)

    def _menu_contextual(self, evento):
        iid = self.tabla.identify_row(evento.y)
        if iid:
            self.tabla.selection_set(iid)
            self.menu.tk_popup(evento.x_root, evento.y_root)

    # ---- acciones sobre resultados

    def exportar(self):
        fecha = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        ruta = filedialog.asksaveasfilename(
            parent=self, title="Exportar resultados", defaultextension=".xlsx",
            initialfile=f"resultados_{self.clave}_{fecha}.xlsx", initialdir=self.carpeta_validada or None,
            filetypes=[("Libro de Excel", "*.xlsx"), ("CSV (separado por ;)", "*.csv")])
        if not ruta:
            return
        try:
            exportar.exportar(self.resultados, ruta)
        except OSError as e:
            messagebox.showerror(APP_NAME, f"No se pudo guardar (¿está abierto en Excel?):\n{e}", parent=self)
            return
        self._estado(f"Resultados exportados a {os.path.basename(ruta)}", "listo", "ok")
        if messagebox.askyesno(APP_NAME, "Resultados exportados.\n¿Abrir el archivo ahora?", parent=self):
            os.startfile(ruta)

    def mover_invalidos(self):
        n = sum(r.estado == INVALIDO for r in self.resultados)
        destino = os.path.join(self.carpeta_validada, core.CARPETA_INVALIDOS)
        if not n or not messagebox.askyesno(
                APP_NAME, f"Se moverán {n} PDF inválidos a:\n{destino}\n\n¿Continuar?", parent=self):
            return
        movidos, errores = core.mover_invalidos(self.resultados, self.carpeta_validada)
        self.refrescar_tabla()
        if errores:
            messagebox.showwarning(APP_NAME, "Algunos archivos no se pudieron mover:\n\n" + "\n".join(errores[:15]),
                                   parent=self)
        self._estado(f"{movidos} archivos movidos a «{core.CARPETA_INVALIDOS}».", "listo", "ok")


# ------------------------------------------------------------ modos ---

class PaginaOnline(Pagina):
    clave = "online"
    titulo = "Validación online"
    subtitulo = "Verifica cada certificado de alumno regular directamente en el portal loa.usach.cl."
    icono = "online"

    def construir_campos(self, master):
        app, f, cfg = self.app, self.app.f, self.cfg
        self.sel_carpeta = SelectorRuta(master, app, "Carpeta con los certificados (PDF)",
                                        "Selecciona la carpeta que contiene los PDF")
        self.sel_carpeta.set(cfg.get("online_carpeta", ""))

        hoy = datetime.date.today()
        periodo = Campo(master, app, "Periodo que deben acreditar", completo=False)
        self.cmb_anio = ctk.CTkComboBox(
            periodo.cuerpo, values=[str(a) for a in range(hoy.year + 1, hoy.year - 4, -1)], width=100, height=38,
            corner_radius=9, border_width=1, fg_color=P["campo"], border_color=P["borde"],
            button_color=P["borde"], button_hover_color=P["suave"], text_color=P["texto"], font=f["normal"],
            dropdown_font=f["normal"], dropdown_fg_color=P["panel"], dropdown_hover_color=P["hover"],
            dropdown_text_color=P["texto"])
        self.cmb_anio.set(str(hoy.year))
        self.cmb_anio.grid(row=0, column=0, sticky="w")
        self.seg_semestre = segmentado(periodo.cuerpo, app, ["1er semestre", "2do semestre"], height=38)
        self.seg_semestre.set("2do semestre" if hoy.month >= 7 else "1er semestre")
        self.seg_semestre.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        periodo.cuerpo.grid_columnconfigure(0, weight=0)
        periodo.cuerpo.grid_columnconfigure(1, weight=1)

        conexiones = Campo(master, app, "Consultas simultáneas", completo=False,
                           ayuda="Más consultas = más rápido. 8 es un buen equilibrio.")
        self.var_conexiones = ctk.IntVar(value=int(cfg.get("online_conexiones", 8)))
        self.sld_conexiones = ctk.CTkSlider(
            conexiones.cuerpo, from_=1, to=16, number_of_steps=15, variable=self.var_conexiones, height=18,
            button_color=P["acento"], button_hover_color=P["acento_h"], progress_color=P["acento"],
            fg_color=P["borde"], command=lambda v: self.lbl_conexiones.configure(text=str(int(v))))
        self.sld_conexiones.grid(row=0, column=0, sticky="ew", pady=10)
        self.lbl_conexiones = ctk.CTkLabel(conexiones.cuerpo, text=str(self.var_conexiones.get()), width=34,
                                           font=f["etiqueta"], text_color=P["texto"])
        self.lbl_conexiones.grid(row=0, column=1, padx=(10, 0))

        carreras = Campo(master, app, "Carreras permitidas",
                         ayuda="Palabras o códigos que debe contener el nombre de la carrera, separados por coma. "
                               "Vacío = cualquier carrera.")
        self.ent_carreras = entrada(carreras.cuerpo, app, "Ej.: ELECTRIC, TELEM, (1461)")
        self.ent_carreras.insert(0, cfg.get("online_carreras", ", ".join(online.CARRERAS_POR_DEFECTO)))
        self.ent_carreras.grid(row=0, column=0, sticky="ew")
        return [self.sel_carpeta, periodo, conexiones, carreras]

    def leer_parametros(self):
        carpeta = self.sel_carpeta.get()
        if not os.path.isdir(carpeta):
            messagebox.showwarning(APP_NAME, "Elige una carpeta válida con los certificados PDF.", parent=self)
            return None
        try:
            anio = int(self.cmb_anio.get())
            assert 2000 <= anio <= 2100
        except (ValueError, AssertionError):
            messagebox.showwarning(APP_NAME, "Escribe un año válido (por ejemplo 2026).", parent=self)
            return None
        carreras = [c.strip() for c in self.ent_carreras.get().split(",") if c.strip()]
        return {
            "carpeta": carpeta,
            "recursivo": self.var_recursivo.get(),
            "opciones": online.OpcionesOnline(anio=anio, semestre=1 if self.seg_semestre.get().startswith("1")
                                              else 2, carreras=carreras, conexiones=self.var_conexiones.get()),
        }

    def ejecutar(self, rutas, params, avance, cancelado):
        return online.validar(rutas, params["opciones"], avance, cancelado)

    def guardar_cfg(self):
        super().guardar_cfg()
        self.cfg["online_carpeta"] = self.sel_carpeta.get()
        self.cfg["online_carreras"] = self.ent_carreras.get()
        self.cfg["online_conexiones"] = self.var_conexiones.get()


class PaginaNomina(Pagina):
    clave = "nomina"
    titulo = "Validación con nómina"
    subtitulo = "Comprueba sin conexión que el RUT de cada PDF esté en una nómina de Excel o CSV."
    icono = "nomina"

    def construir_campos(self, master):
        app, cfg = self.app, self.cfg
        self._nomina = None
        self._nomina_clave = None
        self.sel_carpeta = SelectorRuta(master, app, "Carpeta con los PDF", "Selecciona la carpeta con los PDF")
        self.sel_carpeta.set(cfg.get("nomina_carpeta", ""))
        self.sel_nomina = SelectorRuta(
            master, app, "Nómina (Excel o CSV con columna RUT)", "Selecciona el archivo de la nómina",
            carpeta=False, ayuda="Se busca automáticamente la columna «RUT» (con o sin puntos y guion).",
            tipos=[("Excel o CSV", "*.xlsx *.xlsm *.csv"), ("Todos los archivos", "*.*")],
            al_cambiar=self._cargar_en_segundo_plano)
        self.sel_nomina.set(cfg.get("nomina_archivo", ""))
        return [self.sel_carpeta, self.sel_nomina]

    def _obtener_nomina(self, ruta):
        clave = (ruta, os.path.getmtime(ruta))
        if clave != self._nomina_clave:
            self._nomina = nomina.cargar_nomina(ruta)
            self._nomina_clave = clave
        return self._nomina

    def _cargar_en_segundo_plano(self, ruta):
        if not ruta or not os.path.isfile(ruta):
            if ruta:
                self.sel_nomina.aviso("No se encontró el archivo.", "mal")
            return
        self.sel_nomina.aviso("Leyendo nómina…")

        def tarea():
            try:
                texto, tono = f"✓  {self._obtener_nomina(ruta).descripcion}", "ok"
            except Exception as e:
                texto, tono = f"✗  {e}", "mal"
            self.after(0, lambda: self.sel_nomina.get() == ruta and self.sel_nomina.aviso(texto, tono))

        threading.Thread(target=tarea, daemon=True).start()

    def leer_parametros(self):
        carpeta, archivo = self.sel_carpeta.get(), self.sel_nomina.get()
        if not os.path.isdir(carpeta):
            messagebox.showwarning(APP_NAME, "Elige una carpeta válida con los PDF.", parent=self)
            return None
        if not os.path.isfile(archivo):
            messagebox.showwarning(APP_NAME, "Elige el archivo Excel o CSV de la nómina.", parent=self)
            return None
        return {"carpeta": carpeta, "recursivo": self.var_recursivo.get(), "nomina": archivo}

    def ejecutar(self, rutas, params, avance, cancelado):
        return nomina.validar(rutas, self._obtener_nomina(params["nomina"]), avance, cancelado)

    def guardar_cfg(self):
        super().guardar_cfg()
        self.cfg["nomina_carpeta"] = self.sel_carpeta.get()
        self.cfg["nomina_archivo"] = self.sel_nomina.get()


# ------------------------------------------------------------ ventana ---

class App(ctk.CTk):
    MODOS = {"online": "Validación online", "nomina": "Con nómina Excel"}

    def __init__(self):
        self.cfg = config.cargar()
        ctk.set_appearance_mode(self.cfg.get("tema", "system"))
        super().__init__(fg_color=P["bg"])
        self.title(f"{APP_NAME} · USACH")
        try:
            self.iconbitmap(recurso("icono.ico"))
        except tk.TclError:
            pass
        self.escala = self._get_window_scaling()
        self.iconos = Iconos(self.escala)
        self.f = {
            "titulo": ctk.CTkFont(family=FUENTE, size=24, weight="bold"),
            "marca": ctk.CTkFont(family=FUENTE, size=16, weight="bold"),
            "seccion": ctk.CTkFont(family=FUENTE, size=14, weight="bold"),
            "normal": ctk.CTkFont(family=FUENTE, size=13),
            "boton": ctk.CTkFont(family=FUENTE, size=13, weight="bold"),
            "etiqueta": ctk.CTkFont(family=FUENTE, size=12, weight="bold"),
            "chico": ctk.CTkFont(family=FUENTE, size=12),
            "mini": ctk.CTkFont(family=FUENTE, size=11, weight="bold"),
            "cifra": ctk.CTkFont(family=FUENTE, size=26, weight="bold"),
            "pie": ctk.CTkFont(family=FUENTE, size=11),
            "pie_enlace": ctk.CTkFont(family=FUENTE, size=11, underline=True),
        }
        # Tamaño en unidades lógicas (CTk lo escala); posición en píxeles reales, centrada sobre la barra de tareas.
        pantalla_w, pantalla_h = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.cfg.get("tamano", (1280, 860))
        w = int(min(w, pantalla_w / self.escala * 0.94))
        h = int(min(h, pantalla_h / self.escala * 0.85))
        x = int((pantalla_w - w * self.escala) / 2)
        y = int(max(0, (pantalla_h - h * self.escala) / 2 - 40 * self.escala))
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(520, 600)
        self._logo = self._cargar_logo()
        self._estilo_ttk()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self._crear_lateral()
        self._crear_superior()
        self._crear_pie()
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo.grid_rowconfigure(0, weight=1)
        self.cuerpo.grid_columnconfigure(0, weight=1)
        self.paginas = {"online": PaginaOnline(self.cuerpo, self), "nomina": PaginaNomina(self.cuerpo, self)}
        self.modo = None
        self.disposicion = None
        self._ancho = 0
        self._margen = (32, 26)
        self.mostrar(self.cfg.get("modo", "online"))
        self._aplicar_tema_ttk()
        self.bind("<Configure>", self._al_redimensionar, add="+")
        self.bind_all("<Control-f>", lambda _: self.paginas[self.modo].ent_buscar.focus_set())
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        if self.cfg.get("maximizada"):
            self.after(50, lambda: self.state("zoomed"))
        self.after(150, self._cerrar_splash)

    def _cerrar_splash(self):
        """Cierra la pantalla de carga del .exe (solo existe en la versión compilada)."""
        if "_PYI_SPLASH_IPC" not in os.environ:
            return
        try:
            import pyi_splash
            pyi_splash.close()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    # ---- recursos

    def _cargar_logo(self):
        try:
            im = Image.open(recurso("logo.png")).convert("RGBA")
        except OSError:
            return {}
        logos = {}
        for tam in (40, 30):
            px = round(tam * self.escala)
            chico = im.resize((px, px), Image.LANCZOS)
            logos[tam] = ctk.CTkImage(chico, chico, size=(tam, tam))
        return logos

    def _estilo_ttk(self):
        self.fuente_tabla = tkfont.Font(self, family=FUENTE, size=-round(13 * self.escala))
        self.fuente_cabecera = tkfont.Font(self, family=FUENTE, size=-round(12 * self.escala), weight="bold")
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.layout("Resultados.Treeview", [("Resultados.Treeview.treearea", {"sticky": "nswe"})])
        estilo.layout("Resultados.Treeview.Item", [
            ("Treeitem.padding", {"sticky": "nswe", "children": [
                ("Treeitem.image", {"side": "left", "sticky": ""}),
                ("Treeitem.text", {"side": "left", "sticky": ""}),
            ]}),
        ])
        alto = self.fuente_tabla.metrics("linespace") + round(16 * self.escala)
        estilo.configure("Resultados.Treeview", rowheight=alto, font=self.fuente_tabla, borderwidth=0,
                         relief="flat")
        estilo.configure("Resultados.Treeview.Heading", font=self.fuente_cabecera, relief="flat", borderwidth=0,
                         padding=(round(4 * self.escala), round(9 * self.escala)))
        estilo.configure("Resultados.Treeview.Item", padding=(round(6 * self.escala), 0))

    def _aplicar_tema_ttk(self):
        estilo = ttk.Style(self)
        panel, texto, suave = color("panel"), color("texto"), color("suave")
        estilo.configure("Resultados.Treeview", background=panel, fieldbackground=panel, foreground=texto)
        estilo.map("Resultados.Treeview", background=[("selected", color("acento_bg"))],
                   foreground=[("selected", texto)])
        estilo.configure("Resultados.Treeview.Heading", background=color("cabecera"), foreground=suave,
                         bordercolor=color("cabecera"), lightcolor=color("cabecera"), darkcolor=color("cabecera"))
        estilo.map("Resultados.Treeview.Heading", background=[("active", color("hover"))])
        self.img_estado = {}
        for estado, (_, tono) in ESTADOS.items():
            icono = {VALIDO: "valido", INVALIDO: "invalido", ERROR: "error"}[estado]
            self.img_estado[estado] = ImageTk.PhotoImage(self.iconos.imagen_pil(icono, color(tono), 16), master=self)
        for pagina in getattr(self, "paginas", {}).values():
            pagina.tabla.tag_configure("par", background=panel)
            pagina.tabla.tag_configure("impar", background=color("campo"))
            pagina.actualizar_iconos_tabla()

    # ---- navegación

    def _crear_lateral(self):
        f = self.f
        self.lateral = ctk.CTkFrame(self, fg_color=P["panel"], corner_radius=0, width=250)
        self.lateral.grid_propagate(False)
        self.lateral.grid_columnconfigure(0, weight=1)
        self.lateral.grid_rowconfigure(4, weight=1)
        self.divisor = ctk.CTkFrame(self, fg_color=P["borde"], corner_radius=0, width=1)

        marca = ctk.CTkFrame(self.lateral, fg_color="transparent")
        marca.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 26))
        ctk.CTkLabel(marca, text="", image=self._logo.get(40)).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(marca, text="Validador", font=f["marca"], text_color=P["texto"], anchor="w",
                     height=20).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(marca, text="Certificados USACH", font=f["chico"], text_color=P["suave"], anchor="w",
                     height=16).grid(row=1, column=1, sticky="nw")

        ctk.CTkLabel(self.lateral, text="MODO DE VALIDACIÓN", font=f["mini"], text_color=P["suave"],
                     anchor="w").grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.botones_nav = {}
        for i, (clave, texto) in enumerate(self.MODOS.items()):
            b = ctk.CTkButton(self.lateral, text=f"  {texto}", anchor="w", height=42, corner_radius=10,
                              font=f["normal"], fg_color="transparent", hover_color=P["hover"],
                              text_color=P["texto"], image=self.iconos(clave, "suave", 18), compound="left",
                              command=lambda c=clave: self.mostrar(c))
            b.grid(row=2 + i, column=0, sticky="new", padx=12, pady=2)
            self.botones_nav[clave] = b

        consejo = ctk.CTkFrame(self.lateral, fg_color=P["campo"], corner_radius=12)
        consejo.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 12))
        ctk.CTkLabel(consejo, text=" Consejo", image=self.iconos("info", "acento", 14), compound="left",
                     font=f["etiqueta"], text_color=P["texto"], anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(consejo, text="Haz clic en una tarjeta del resumen para filtrar la tabla. Doble clic en una "
                     "fila abre el PDF.", font=f["chico"], text_color=P["suave"], anchor="w", justify="left",
                     wraplength=196).pack(fill="x", padx=12, pady=(0, 12))

        # Los botones se crean con ícono: en CustomTkinter 5.2 agregarlo después con configure() no lo dibuja.
        self.btn_tema = ctk.CTkButton(self.lateral, text="", anchor="w", height=38, corner_radius=10,
                                      font=f["normal"], fg_color="transparent", hover_color=P["hover"],
                                      text_color=P["texto"], compound="left", command=self.alternar_tema,
                                      image=self.iconos("luna", "suave", 18))
        self.btn_tema.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 14))

    def _crear_pie(self):
        """Marca de agua con la autoría, abajo a la izquierda (visible con cualquier tamaño de ventana)."""
        f = self.f
        ctk.CTkFrame(self, fg_color=P["borde"], corner_radius=0, height=1).grid(row=2, column=0, columnspan=3,
                                                                               sticky="ew")
        pie = ctk.CTkFrame(self, fg_color=P["panel"], corner_radius=0)
        pie.grid(row=3, column=0, columnspan=3, sticky="ew")
        ctk.CTkLabel(pie, text=f"© 2026 {__author__}  ·  ", font=f["pie"], text_color=P["marca_agua"],
                     height=26).pack(side="left", padx=(16, 0))
        enlace = ctk.CTkLabel(pie, text=LINKEDIN.removeprefix("https://www."), font=f["pie"],
                              text_color=P["marca_agua"], height=26, cursor="hand2")
        enlace.pack(side="left")
        enlace.bind("<Button-1>", lambda _: webbrowser.open(LINKEDIN))
        enlace.bind("<Enter>", lambda _: enlace.configure(text_color=P["acento"], font=f["pie_enlace"]))
        enlace.bind("<Leave>", lambda _: enlace.configure(text_color=P["marca_agua"], font=f["pie"]))
        ctk.CTkLabel(pie, text=f"v{__version__}", font=f["pie"], text_color=P["marca_agua"],
                     height=26).pack(side="right", padx=16)

    def _crear_superior(self):
        f = self.f
        self.superior = ctk.CTkFrame(self, fg_color=P["panel"], corner_radius=0, height=60)
        self.superior.grid_columnconfigure(1, weight=1)
        self.divisor_sup = ctk.CTkFrame(self, fg_color=P["borde"], corner_radius=0, height=1)
        marca = ctk.CTkFrame(self.superior, fg_color="transparent")
        marca.grid(row=0, column=0, padx=(14, 10), pady=10, sticky="w")
        ctk.CTkLabel(marca, text="", image=self._logo.get(30)).grid(row=0, column=0, padx=(0, 8))
        self.lbl_marca_sup = ctk.CTkLabel(marca, text="Validador", font=f["marca"], text_color=P["texto"])
        self.lbl_marca_sup.grid(row=0, column=1)
        self.seg_modo = segmentado(self.superior, self, ["Online", "Con nómina"],
                                   lambda v: self.mostrar("online" if v == "Online" else "nomina"), height=34)
        self.seg_modo.grid(row=0, column=1, sticky="e", padx=6)
        self.btn_tema_sup = ctk.CTkButton(self.superior, text="", width=38, height=34, corner_radius=9,
                                          fg_color="transparent", hover_color=P["hover"],
                                          command=self.alternar_tema, image=self.iconos("luna", "suave", 18))
        self.btn_tema_sup.grid(row=0, column=2, padx=(0, 12))

    def mostrar(self, clave):
        if clave not in self.paginas or clave == self.modo:
            return
        if self.modo:
            self.paginas[self.modo].grid_remove()
        self.modo = clave
        self.paginas[clave].grid(row=0, column=0, sticky="nsew", padx=self._margen[0], pady=self._margen[1])
        if self.disposicion:
            self.paginas[clave].disponer(self.disposicion)
            self.paginas[clave].ajustar_ancho(self._ancho_contenido())
        for c, b in self.botones_nav.items():
            activo = c == clave
            b.configure(fg_color=P["acento_bg"] if activo else "transparent",
                        text_color=P["acento"] if activo else P["texto"],
                        font=self.f["boton"] if activo else self.f["normal"],
                        image=self.iconos(c, "acento" if activo else "suave", 18))
        self.seg_modo.set("Online" if clave == "online" else "Con nómina")
        self._actualizar_boton_tema()

    def _al_redimensionar(self, evento):
        if evento.widget is not self:
            return
        ancho = evento.width / self.escala
        if abs(ancho - self._ancho) < 8:
            return
        self._ancho = ancho
        self._aplicar_disposicion(ancho)

    def _aplicar_disposicion(self, ancho):
        modo = "ancho" if ancho >= 1100 else "medio" if ancho >= 780 else "angosto"
        if modo != self.disposicion:
            self.disposicion = modo
            if modo == "ancho":
                self.superior.grid_forget()
                self.divisor_sup.grid_forget()
                self.lateral.grid(row=0, column=0, rowspan=2, sticky="nsw")
                self.divisor.grid(row=0, column=1, rowspan=2, sticky="ns")
                self.cuerpo.grid(row=0, column=2, rowspan=2, sticky="nsew")
            else:
                self.lateral.grid_forget()
                self.divisor.grid_forget()
                self.superior.grid(row=0, column=0, columnspan=3, sticky="new")
                self.divisor_sup.grid(row=0, column=0, columnspan=3, sticky="sew")
                self.cuerpo.grid(row=1, column=0, columnspan=3, sticky="nsew")
            self.lbl_marca_sup.grid() if modo == "medio" else self.lbl_marca_sup.grid_remove()
            self._margen = {"ancho": (32, 26), "medio": (22, 18), "angosto": (14, 12)}[modo]
            self.paginas[self.modo].grid_configure(padx=self._margen[0], pady=self._margen[1])
            self.paginas[self.modo].disponer(modo)
        self.paginas[self.modo].ajustar_ancho(self._ancho_contenido())

    def _ancho_contenido(self):
        lateral = 251 if self.disposicion == "ancho" else 0
        pad = {"ancho": 32, "medio": 22, "angosto": 14}.get(self.disposicion, 20)
        return self._ancho - lateral - 2 * pad

    # ---- tema

    def alternar_tema(self):
        modo = "light" if es_oscuro() else "dark"
        ctk.set_appearance_mode(modo)
        self.cfg["tema"] = modo
        self._aplicar_tema_ttk()
        self._actualizar_boton_tema()

    def _actualizar_boton_tema(self):
        oscuro = es_oscuro()
        icono = self.iconos("sol" if oscuro else "luna", "suave", 18)
        self.btn_tema.configure(text=f"  {'Modo claro' if oscuro else 'Modo oscuro'}", image=icono)
        self.btn_tema_sup.configure(image=icono)

    # ---- cierre y errores

    def guardar_cfg(self):
        self.cfg["modo"] = self.modo
        maximizada = self.state() == "zoomed"
        self.cfg["maximizada"] = maximizada
        if not maximizada:
            self.cfg["tamano"] = (round(self.winfo_width() / self.escala), round(self.winfo_height() / self.escala))
        for p in self.paginas.values():
            p.guardar_cfg()
        config.guardar(self.cfg)

    def cerrar(self):
        trabajando = any(p.trabajando for p in self.paginas.values())
        if trabajando and not messagebox.askyesno(APP_NAME, "Hay una validación en curso. ¿Salir de todos modos?",
                                                  parent=self):
            return
        self.guardar_cfg()
        self.destroy()
        if trabajando:
            os._exit(0)  # No esperar a las consultas que siguen en vuelo.

    def report_callback_exception(self, tipo, valor, tb):
        traceback.print_exception(tipo, valor, tb)
        messagebox.showerror(APP_NAME, f"Ocurrió un error inesperado:\n\n{valor}", parent=self)


def ejecutar():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("usach.validador.certificados")
        except Exception:
            pass
    App().mainloop()
