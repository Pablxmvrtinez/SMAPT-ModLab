"""S.M.A.P.T. ModLab: catálogo visual CurseForge y diseñador con IA integrada."""
import json
import sys
from pathlib import Path
from threading import Event
from PySide6.QtCore import Qt,QThread,Signal,QTimer,QStandardPaths
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QPushButton,QComboBox,QSpinBox,QLineEdit,QTextEdit,QTextBrowser,QFrame,QStackedWidget,
    QScrollArea,QGridLayout,QListWidget,QListWidgetItem,QDialog,QFormLayout,QDialogButtonBox,
    QGroupBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QMessageBox,QFileDialog,
    QProgressBar,QSplitter)
from curseforge import CurseForgeClient,Connection,CatalogError,connection_from_environment
from intelligence import ExperienceDesigner,plan_text
from local_ai import LocalAI
from modpack import build_pack,resolve_loader_version,audit_pack
from core import hardware,instances,recommend,apply_graphics,save_plan
from visual_widgets import Images,Artwork,CardGrid,Cover,LABELS

STYLE="""
QWidget { background: #0d0f15; color: #e8eaf1; font-family: Inter, 'Noto Sans', sans-serif; font-size: 12px; }
QMainWindow { background: #0b0d13; }
QFrame#sidebar { background: #10121a; border-right: 1px solid #252a38; }
QFrame#hero, QFrame#modeCard { background: #151b2b; border: 1px solid #303c58; border-radius: 16px; }
QFrame#modCard { background: #151923; border: 1px solid #2b3345; border-radius: 14px; }
QFrame#modCard:hover { border: 1px solid #547bc5; }
QPushButton { background: #202736; border: 1px solid #35415a; border-radius: 8px; padding: 10px 15px; font-weight: 600; }
QPushButton:hover { background: #2b3c5a; border-color: #5e7ebc; }
QPushButton:disabled { color: #6c7489; background: #1a1e29; border-color: #262e40; }
QPushButton#primary { color: white; background: #bd3356; border: 1px solid #d34265; }
QPushButton#primary:hover { background: #d44368; }
QPushButton#primary:disabled { color: #817481; background: #30202b; border-color: #382b38; }
QPushButton#nav { background: transparent; border: none; text-align: left; padding: 13px 17px; color: #a5aec4; }
QPushButton#nav:checked { background: #25253b; color: #f19ab0; border-left: 3px solid #d14468; border-radius: 4px; }
QPushButton#category { background: #171d2a; text-align: left; padding: 15px; border-radius: 12px; }
QPushButton#selected { color: #93b7ef; background: #1b2d46; }
QLineEdit,QTextEdit,QTextBrowser,QComboBox,QSpinBox,QListWidget { background: #151b27; border: 1px solid #303b52; border-radius: 9px; padding: 9px; }
QLineEdit:focus,QTextEdit:focus { border-color: #638de2; }
QScrollArea,QScrollArea>QWidget>QWidget { background: transparent; border: none; }
QLabel { background: transparent; }
QLabel#h1 { font-size: 29px; font-weight: 800; color: #f4f5fc; }
QLabel#heroTitle { font-size: 31px; font-weight: 800; color: #ffffff; background: transparent; }
QLabel#h2 { font-size: 19px; font-weight: 700; }
QLabel#brand { font-size: 24px; font-weight: 900; color: #f0f1fa; }
QLabel#eyebrow { color: #e57793; font-size: 11px; font-weight: 800; letter-spacing: 2px; background: transparent; }
QLabel#muted,QLabel#subtitle { color: #9aa6c0; }
QLabel#cardTitle { font-size: 16px; font-weight: 750; }
QLabel#source { color: #e59673; font-size: 10px; font-weight: 800; }
QLabel#tag { background: #252e43; color: #aec5ec; border-radius: 5px; padding: 4px 6px; font-size: 10px; }
QLabel#metric { font-size: 18px; color: #e66c8d; font-weight: 700; }
QGroupBox { border: 1px solid #303b52; border-radius: 12px; margin-top: 14px; padding: 16px; }
QGroupBox::title { color: #a2bbed; subcontrol-origin: margin; left: 16px; padding: 0 6px; }
QHeaderView::section { background: #222d43; padding: 9px; border: 0; }
QTableWidget { background: #151b27; border: 1px solid #303b52; gridline-color: #29354d; }
QProgressBar { border: none; background: #192135; max-height: 5px; }
QProgressBar::chunk { background: #c43f61; }
QScrollBar:vertical { background: #11151e; width: 10px; }
QScrollBar::handle:vertical { background: #354766; border-radius: 5px; min-height: 30px; }
"""

THEMES=[('✦','Aventura y RPG','Adventure and RPG'),('◇','Magia','Magic'),('⚙','Tecnología','Technology'),
 ('▦','Construcción','Cosmetic'),('♧','Agricultura','Farming'),('♜','Criaturas y jefes','Mobs'),
 ('⌂','Estructuras','Structures'),('◈','Biomas','Biomes'),('◎','Dimensiones','Dimensions'),
 ('⚔','Armas y equipo','Armor, Tools, and Weapons'),('↗','Rendimiento','Performance'),
 ('☷','Almacenamiento','Storage'),('✚','Comodidad','Utility & QoL'),('⌖','Mapas','Map and Information'),
 ('●','Comida','Food'),('⌁','Redstone','Redstone'),('ϟ','Energía','Energy'),('⇆','Transporte','Transport'),
 ('◆','Minerales','Ores and Resources'),('▣','Procesamiento','Processing'),('⌘','Bibliotecas','API and Library'),
 ('▤','Servidores','Server Utility'),('✧','Integraciones','Twitch Integration'),('∞','Todo el catálogo',None)]

class Cancelled(Exception):pass

class TaskThread(QThread):
    ready=Signal(object);failed=Signal(str);progress=Signal(str)
    def __init__(self,task,cancel):
        super().__init__();self.task=task;self.cancel=cancel
    def report(self,message):
        if self.cancel.is_set():raise Cancelled()
        self.progress.emit(message)
    def run(self):
        try:
            result=self.task(self.report)
            if not self.cancel.is_set():self.ready.emit(result)
        except Cancelled:pass
        except Exception as exc:self.failed.emit(str(exc))


def heading(text,kind='h2'):
    label=QLabel(text);label.setObjectName(kind);label.setWordWrap(True);return label


def scroll_page(widget):
    area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QFrame.Shape.NoFrame);area.setWidget(widget);return area


class ModLab(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('S.M.A.P.T. ModLab · Acheron');self.resize(1460,970)
        self.hw=hardware();self.packs=instances();self.current_profile={}
        self.catalog=CurseForgeClient()
        config_path=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))/'catalog.json'
        if not self.catalog.connection.gateway and not self.catalog.connection.api_key:
            try:
                url=json.loads(config_path.read_text()).get('catalog_url','')
                if url:self.catalog=CurseForgeClient(Connection(url))
            except (OSError,ValueError,TypeError,AttributeError):pass
        self.ai=LocalAI();self.designer=ExperienceDesigner(self.catalog,self.ai)
        self.pack={};self.tasks=[];self.busy=False;self.cancel=Event();self.categories=[]
        self.browse_mods=[];self.ai_mods=[];self.proposal=None;self.index=0;self.total=0;self.category_id=None
        root=QWidget();self.setCentralWidget(root);outer=QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(200);sv=QVBoxLayout(side);sv.setContentsMargins(16,28,16,22);sv.setSpacing(8)
        sv.addWidget(heading('SMAPT','brand'));sv.addWidget(heading('M O D L A B','eyebrow'));sv.addSpacing(30)
        self.nav=[]
        for name,index in [('⌂   Inicio',0),('✦   Crear con IA',1),('▦   Explorar mods',2),('▣   Mi modpack',3),('⌘   Mi equipo',4),('↗   Optimizar',5)]:
            button=QPushButton(name);button.setObjectName('nav');button.setCheckable(True)
            button.clicked.connect(lambda checked=False,i=index:self.navigate(i));sv.addWidget(button);self.nav.append(button)
        sv.addStretch();sv.addWidget(heading('ACHERON EDITION','eyebrow'))
        self.connection_label=QLabel();self.connection_label.setWordWrap(True);self.connection_label.setObjectName('muted');sv.addWidget(self.connection_label)
        connection=QPushButton('Conexión del catálogo');connection.clicked.connect(self.configure_connection);sv.addWidget(connection)
        outer.addWidget(side)
        main=QWidget();mv=QVBoxLayout(main);mv.setContentsMargins(28,22,28,15);mv.setSpacing(14)
        top=QHBoxLayout();top.addWidget(heading('Tu próximo mundo empieza aquí','h2'));top.addStretch()
        top.addWidget(QLabel('Minecraft'));self.version=QComboBox();self.version.setEditable(True)
        self.version.addItems(['1.20.1','1.21.1','1.19.2','1.21.4','1.18.2','1.16.5']);top.addWidget(self.version)
        self.loader=QComboBox();self.loader.addItems(['Forge','Fabric','NeoForge']);top.addWidget(self.loader)
        self.refresh=QPushButton('↻');self.refresh.setToolTip('Actualizar detección del equipo');self.refresh.clicked.connect(self.update_data);top.addWidget(self.refresh)
        self.pack_badge=QPushButton('Mi pack · 0');self.pack_badge.clicked.connect(lambda:self.navigate(3));top.addWidget(self.pack_badge);mv.addLayout(top)
        self.images=Images(self);self.stack=QStackedWidget();mv.addWidget(self.stack,1)
        self.stack.addWidget(self.create_home());self.stack.addWidget(self.create_ai());self.stack.addWidget(self.create_browser());self.stack.addWidget(self.create_pack())
        self.stack.addWidget(self.create_overview());self.stack.addWidget(self.create_optimizer())
        bottom=QHBoxLayout();self.status=QLabel('Listo. Catálogo exclusivo de CurseForge.');self.status.setWordWrap(True);self.status.setObjectName('muted');bottom.addWidget(self.status,1)
        self.cancel_button=QPushButton('Cancelar');self.cancel_button.setVisible(False);self.cancel_button.clicked.connect(self.cancel_task);bottom.addWidget(self.cancel_button);mv.addLayout(bottom)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setTextVisible(False);self.progress.hide();mv.addWidget(self.progress)
        outer.addWidget(main,1)
        self.version.currentTextChanged.connect(self.change_target);self.loader.currentTextChanged.connect(self.change_target)
        self.populate();self.update_connection_label();self.navigate(0)
        if '--smoke' not in sys.argv and (self.catalog.connection.gateway or self.catalog.connection.api_key):
            QTimer.singleShot(100,self.load_categories)

    def navigate(self,index):
        self.stack.setCurrentIndex(index)
        for i,button in enumerate(self.nav):button.setChecked(i==index)
        if index==2 and not self.browse_mods and not self.busy and (self.catalog.connection.gateway or self.catalog.connection.api_key):self.search_browser()

    def create_home(self):
        page=QWidget();v=QVBoxLayout(page);v.setContentsMargins(0,0,0,0);v.setSpacing(20)
        hero=QFrame();hero.setObjectName('hero');row=QHBoxLayout(hero);row.setContentsMargins(30,24,10,20)
        text=QVBoxLayout();text.addWidget(heading('CONSTRUYE ALGO TUYO','eyebrow'))
        text.addWidget(heading('Un mundo.\nTodas tus posibilidades.','heroTitle'))
        sub=QLabel('Mods de CurseForge, tu estilo de juego y una IA local para darle forma.');sub.setWordWrap(True);sub.setObjectName('muted');text.addWidget(sub)
        actions=QHBoxLayout();create=QPushButton('✦  Crear con IA');create.setObjectName('primary');create.clicked.connect(lambda:self.navigate(1));actions.addWidget(create)
        explore=QPushButton('Explorar mods  →');explore.clicked.connect(lambda:self.navigate(2));actions.addWidget(explore);text.addLayout(actions);row.addLayout(text,1)
        art=Artwork();art.setMinimumSize(360,245);row.addWidget(art,1);v.addWidget(hero)
        modes=QHBoxLayout()
        for title,desc,action,index in [('✦  Imagina tu modpack','Describe cómo quieres jugar. La IA interpreta el ritmo, busca alternativas y explica cada recomendación.','Diseñar mi experiencia',1),
                                      ('▦  Encuentra tu próximo mod','Explora imágenes, categorías y proyectos del catálogo oficial. Añade lo que te guste a tu pack.','Abrir biblioteca',2)]:
            card=QFrame();card.setObjectName('modeCard');cv=QVBoxLayout(card);cv.setContentsMargins(22,20,22,20);cv.addWidget(heading(title))
            label=QLabel(desc);label.setWordWrap(True);label.setObjectName('muted');cv.addWidget(label);button=QPushButton(action+'  →');button.clicked.connect(lambda checked=False,i=index:self.navigate(i));cv.addWidget(button);modes.addWidget(card)
        v.addLayout(modes);v.addWidget(heading('Explora tus posibilidades'));v.addWidget(self.theme_grid());v.addStretch();return scroll_page(page)

    def theme_grid(self):
        box=QWidget();grid=QGridLayout(box);grid.setContentsMargins(0,0,0,0);grid.setSpacing(10)
        for i,(icon,label,category) in enumerate(THEMES):
            button=QPushButton(icon+'   '+label);button.setObjectName('category');button.setMinimumHeight(52)
            button.clicked.connect(lambda checked=False,c=category:self.choose_theme(c));grid.addWidget(button,i//4,i%4)
        return box

    def create_ai(self):
        page=QWidget();v=QVBoxLayout(page);v.setContentsMargins(0,0,0,0);v.setSpacing(12)
        v.addWidget(heading('Describe la experiencia. La IA prepara las opciones.','h1'))
        note=QLabel('Sin filtros obligatorios. La IA se ejecuta dentro de ModLab y trabaja con mods de CurseForge.');note.setObjectName('muted');note.setWordWrap(True);v.addWidget(note)
        self.prompt=QTextEdit();self.prompt.setMaximumHeight(110)
        self.prompt.setPlaceholderText('Quiero construir tranquilo, explorar con amigos, algún jefe opcional y buen rendimiento en un PC modesto…')
        self.prompt.setPlainText('Quiero un modpack tranquilo para jugar chill, construir y pelear con algún jefe que otro, optimizado para un PC modesto.');v.addWidget(self.prompt)
        examples=QHBoxLayout()
        for label,text in [('Chill con amigos','Construir y decorar con amigos, cocinar, explorar a nuestro ritmo y algún jefe opcional. Prioriza rendimiento.'),
                           ('Fábricas y máquinas','Quiero muchas fábricas, automatización, energía y máquinas. Sin magia y con buena optimización.'),
                           ('Magia y aventura','Quiero progresión de magia, hechizos, exploración, mazmorras y jefes, sin tecnología industrial.'),
                           ('Construcción creativa','Quiero mucha variedad de bloques, muebles y herramientas para construir. Sin jefes ni combates extra.')]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,t=text:self.prompt.setPlainText(t));examples.addWidget(button)
        v.addLayout(examples)
        controls=QHBoxLayout();controls.addWidget(QLabel('Hasta'));self.max_mods=QSpinBox();self.max_mods.setRange(1,400);self.max_mods.setValue(80);controls.addWidget(self.max_mods)
        controls.addWidget(QLabel('mods · puedes ampliar el pack después'));controls.addStretch()
        self.ai_start=QPushButton('✦  Razonar y proponer mods');self.ai_start.setObjectName('primary');self.ai_start.clicked.connect(self.start_ai);controls.addWidget(self.ai_start);v.addLayout(controls)
        self.ai_summary=QTextEdit();self.ai_summary.setReadOnly(True);self.ai_summary.setMaximumHeight(100)
        self.ai_summary.setPlaceholderText('Aquí verás el criterio de la propuesta, sus supuestos y lo que se evita.');v.addWidget(self.ai_summary)
        self.ai_grid=CardGrid(self.images);self.ai_grid.add.connect(self.add_mod);self.ai_grid.details.connect(self.show_details);v.addWidget(self.ai_grid,1)
        bottom=QHBoxLayout();self.ai_count=QLabel('Las recomendaciones aparecerán como tarjetas con su explicación.');self.ai_count.setWordWrap(True);bottom.addWidget(self.ai_count,1)
        self.add_all=QPushButton('Añadir propuesta al pack');self.add_all.setEnabled(False);self.add_all.clicked.connect(self.add_proposal);bottom.addWidget(self.add_all);v.addLayout(bottom)
        return page

    def create_browser(self):
        page=QWidget();v=QVBoxLayout(page);v.setContentsMargins(0,0,0,0);v.setSpacing(12)
        v.addWidget(heading('Una biblioteca para perderse. Un pack para encontrarse.','h1'))
        row=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Buscar mods en CurseForge: Create, muebles, mapas…');self.search.returnPressed.connect(self.search_browser);row.addWidget(self.search,1)
        self.category=QComboBox();self.category.addItem('Todas las categorías',None);self.category.setMinimumWidth(190)
        self.category.currentIndexChanged.connect(self.search_browser);row.addWidget(self.category)
        self.sort=QComboBox();self.sort.addItem('Más descargados',6);self.sort.addItem('Populares',2);self.sort.addItem('Actualizados',3);self.sort.currentIndexChanged.connect(self.search_browser);row.addWidget(self.sort)
        button=QPushButton('Buscar');button.setObjectName('primary');button.clicked.connect(self.search_browser);row.addWidget(button);v.addLayout(row)
        self.browse_info=QLabel('Catálogo oficial de CurseForge · 50 resultados por página.');self.browse_info.setObjectName('muted');v.addWidget(self.browse_info)
        self.browse_grid=CardGrid(self.images);self.browse_grid.add.connect(self.add_mod);self.browse_grid.details.connect(self.show_details);v.addWidget(self.browse_grid,1)
        pagination=QHBoxLayout();self.prev=QPushButton('← Anteriores');self.prev.clicked.connect(lambda:self.page_browser(-50));pagination.addWidget(self.prev)
        self.page_label=QLabel('Página 1');pagination.addWidget(self.page_label);pagination.addStretch()
        self.next=QPushButton('Siguientes 50  →');self.next.clicked.connect(lambda:self.page_browser(50));pagination.addWidget(self.next);v.addLayout(pagination);self.prev.setEnabled(False);self.next.setEnabled(False)
        return page

    def create_pack(self):
        page=QWidget();v=QVBoxLayout(page);v.setContentsMargins(0,0,0,0)
        v.addWidget(heading('Tu modpack, pieza a pieza.','h1'))
        row=QHBoxLayout();self.pack_name=QLineEdit('Mi modpack Acheron');row.addWidget(self.pack_name,1)
        self.loader_build=QLineEdit();self.loader_build.setPlaceholderText('Cargador automático · versión manual opcional');row.addWidget(self.loader_build,1);v.addLayout(row)
        self.pack_summary=QLabel('Añade mods desde Explorar o desde una propuesta de IA.');self.pack_summary.setObjectName('muted');self.pack_summary.setWordWrap(True);v.addWidget(self.pack_summary)
        self.pack_list=QListWidget();v.addWidget(self.pack_list,1)
        row=QHBoxLayout();button=QPushButton('Quitar seleccionado');button.clicked.connect(self.remove_selected);row.addWidget(button)
        button=QPushButton('Guardar proyecto');button.clicked.connect(self.save_project);row.addWidget(button)
        button=QPushButton('Abrir proyecto');button.clicked.connect(self.open_project);row.addWidget(button);row.addStretch()
        self.audit_button=QPushButton('Comprobar pack');self.audit_button.clicked.connect(self.check_pack);row.addWidget(self.audit_button)
        self.export_button=QPushButton('Crear ZIP para CurseForge  →');self.export_button.setObjectName('primary');self.export_button.clicked.connect(self.export_pack);row.addWidget(self.export_button);v.addLayout(row)
        v.addWidget(QLabel('El ZIP usa IDs oficiales. CurseForge descarga los mods y crea el perfil al importarlo.'))
        return page

    def create_overview(self):
        tab=QWidget();layout=QVBoxLayout(tab);layout.setSpacing(15)
        hwbox=QGroupBox("Análisis del ordenador");v=QVBoxLayout(hwbox)
        self.hw_label=QLabel();self.hw_label.setWordWrap(True)
        self.hw_label.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(self.hw_label)
        layout.addWidget(hwbox)
        instbox=QGroupBox("Instalaciones encontradas");iv=QVBoxLayout(instbox)
        self.pack_table=QTableWidget(0,4)
        self.pack_table.setHorizontalHeaderLabels(["Instancia","Lanzador","Mods .jar","Minecraft"])
        self.pack_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.pack_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.pack_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        self.pack_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.ResizeToContents)
        self.pack_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        iv.addWidget(self.pack_table)
        layout.addWidget(instbox,1)
        note=QLabel("El diagnóstico inicial no mide FPS. La estimación se basa en la RAM, GPU y el número de mods; medir rendimiento real será una fase posterior.")
        note.setWordWrap(True);note.setObjectName("muted");layout.addWidget(note)
        return tab


    def create_optimizer(self):
        tab=QWidget();v=QVBoxLayout(tab);v.setSpacing(14)
        intro=QLabel("Crea un perfil para una instancia. Se guardará copia de sus ajustes antes de aplicar cualquier cambio.")
        intro.setWordWrap(True);intro.setObjectName("muted")
        v.addWidget(intro)
        selector=QHBoxLayout()
        selector.addWidget(QLabel("Instancia"))
        self.pack_combo=QComboBox()
        self.pack_combo.currentIndexChanged.connect(self.update_profile)
        selector.addWidget(self.pack_combo,1)
        selector.addWidget(QLabel("Prioridad"))
        self.mode=QComboBox();self.mode.addItems(["Equilibrado","Máximos FPS","Calidad visual"])
        self.mode.currentIndexChanged.connect(self.update_profile)
        selector.addWidget(self.mode)
        v.addLayout(selector)
        recbox=QGroupBox("Propuesta de optimización")
        b=QVBoxLayout(recbox)
        self.rec_label=QLabel("Selecciona una instancia.");self.rec_label.setWordWrap(True)
        self.rec_label.setTextFormat(Qt.TextFormat.RichText)
        b.addWidget(self.rec_label)
        v.addWidget(recbox)
        self.apply_btn=QPushButton("Aplicar gráficos con copia de seguridad")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self.apply)
        v.addWidget(self.apply_btn)
        note=QLabel("Se ajustan renderizado, simulación, FPS, partículas y el interruptor de shaders de Oculus cuando existe. La RAM de Java solo se recomienda: debes asignarla desde el lanzador. No tocamos mundos, mods ni configuraciones de servidores.")
        note.setWordWrap(True);note.setObjectName("muted")
        v.addWidget(note);v.addStretch()
        return tab

    def populate(self):
        h=self.hw
        self.hw_label.setText(
            f"<b>CPU:</b> {h['cpu']} ({h['threads']} hilos)<br>"
            f"<b>GPU:</b> {h['gpu']} • VRAM {h['vram_gb']} GB<br>"
            f"<b>RAM:</b> {h['ram_gb']} GB • disponible ahora {h['ram_available_gb']} GB<br>"
            "<b>Sistema:</b> CachyOS / KDE Plasma")
        self.pack_table.setRowCount(len(self.packs))
        for r,p in enumerate(self.packs):
            for c,val in enumerate([p["name"],p["launcher"],str(p["mods"]),p["version"] or "Desconocida"]):
                self.pack_table.setItem(r,c,QTableWidgetItem(val))
        old=self.pack_combo.currentText()
        self.pack_combo.blockSignals(True)
        self.pack_combo.clear()
        for p in self.packs:
            self.pack_combo.addItem(f"{p['name']} ({p['mods']} mods)",p)
        self.pack_combo.blockSignals(False)
        for idx in range(self.pack_combo.count()):
            if old.startswith(self.pack_combo.itemData(idx)["name"]):
                self.pack_combo.setCurrentIndex(idx)
        self.update_profile()


    def update_connection_label(self):
        connected=bool(self.catalog.connection.gateway or self.catalog.connection.api_key)
        self.connection_label.setText('CURSEFORGE\nConexión configurada' if connected else 'CURSEFORGE\nCatálogo pendiente de conexión')
        if not connected:self.browse_info.setText('El catálogo oficial todavía no está conectado. Abre «Conexión del catálogo» para configurar la pasarela de ModLab.')

    def configure_connection(self):
        if self.busy:return
        dialog=QDialog(self);dialog.setWindowTitle('Conexión de CurseForge');dialog.resize(570,270)
        v=QVBoxLayout(dialog);label=QLabel('Para distribuir ModLab, el desarrollador conecta una pasarela que protege su clave de CurseForge. Tus amigos reciben la URL ya configurada.');label.setWordWrap(True);v.addWidget(label)
        form=QFormLayout();url=QLineEdit(self.catalog.connection.gateway);url.setPlaceholderText('https://catalogo.tu-servidor.com')
        key=QLineEdit();key.setEchoMode(QLineEdit.EchoMode.Password);key.setPlaceholderText('Solo desarrollo · no se guarda ni se incluye en el paquete')
        form.addRow('Pasarela del catálogo',url);form.addRow('Clave API de desarrollo',key);v.addLayout(form)
        error=QLabel();error.setWordWrap(True);v.addWidget(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);v.addWidget(buttons)
        buttons.rejected.connect(dialog.reject)
        def save():
            connection=Connection(url.text().strip().rstrip('/'),key.text().strip() or self.catalog.connection.api_key)
            try:connection.check()
            except CatalogError as exc:error.setText(str(exc));return
            if connection.gateway:
                folder=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation));folder.mkdir(parents=True,exist_ok=True)
                try:(folder/'catalog.json').write_text(json.dumps({'catalog_url':connection.gateway}))
                except OSError:error.setText('No se pudo guardar la URL.');return
            self.catalog=CurseForgeClient(connection);self.designer=ExperienceDesigner(self.catalog,self.ai)
            self.categories=[];self.browse_mods=[];dialog.accept();self.update_connection_label();self.load_categories()
        buttons.accepted.connect(save);dialog.exec()

    def load_categories(self):
        if self.busy:return
        def ready(categories):
            self.categories=categories
            self.category.blockSignals(True);self.category.clear();self.category.addItem('Todas las categorías',None)
            for cat in sorted(categories,key=lambda c:LABELS.get(c['name'],c['name']).casefold()):
                if not cat.get('isClass'):self.category.addItem(LABELS.get(cat['name'],cat['name']),cat['id'])
            self.category.blockSignals(False)
            self.status.setText(f'{self.category.count()-1} categorías oficiales de CurseForge disponibles.')
        self.run_task(lambda progress:self.catalog.categories(),ready)

    def choose_theme(self,name):
        if self.busy:return
        self.stack.setCurrentIndex(2)
        for i,button in enumerate(self.nav):button.setChecked(i==2)
        if not self.categories:
            def ready(categories):
                self.categories=categories;self.choose_theme(name)
            # Llamada dependiente tras terminar la tarea actual.
            def fetched(categories):
                self.categories=categories
                self.category.blockSignals(True);self.category.clear();self.category.addItem('Todas las categorías',None)
                for c in sorted(categories,key=lambda c:c['name']):
                    self.category.addItem(LABELS.get(c['name'],c['name']),c['id'])
                self.category.blockSignals(False)
                self.pending_theme=name
            self.run_task(lambda progress:self.catalog.categories(),fetched);return
        wanted=next((c for c in self.categories if c['name'].casefold()==str(name).casefold()),None) if name else None
        if name and not wanted:
            self.status.setText('Esta temática no está disponible como categoría en el catálogo actual. Usa la IA para describirla.');return
        index=self.category.findData(wanted['id'] if wanted else None)
        self.category.blockSignals(True);self.category.setCurrentIndex(index);self.category.blockSignals(False)
        self.search.clear();self.search_browser()

    def search_browser(self,*_,offset=0):
        if self.busy:return
        query=self.search.text().strip();category=self.category.currentData();sort=self.sort.currentData()
        mc=self.version.currentText().strip();loader=self.loader.currentText()
        def ready(result):
            self.index=offset;self.browse_mods=result['mods'];pagination=result['pagination'];self.total=pagination.get('totalCount',len(self.browse_mods))
            self.browse_grid.show_mods(self.browse_mods,self.pack)
            self.browse_info.setText(f'CurseForge · {self.total:,} resultados · {mc} / {loader} · etiquetas originales en cada ficha')
            self.page_label.setText(f'Página {offset//50+1} · {len(self.browse_mods)} mods')
            self.prev.setEnabled(offset>0);self.next.setEnabled(offset+50<min(10000,self.total))
            if not self.browse_mods:self.browse_info.setText('No hay mods para esta búsqueda y versión. La IA puede explorar otras alternativas para tu experiencia.')
        self.run_task(lambda progress:self.catalog.search(query,category,offset,50,sort,mc,loader),ready)

    def page_browser(self,delta):
        self.search_browser(offset=max(0,self.index+delta))

    def start_ai(self):
        if self.busy:return
        phrase=self.prompt.toPlainText().strip()
        if not phrase:self.status.setText('Describe primero cómo quieres jugar.');return
        if not self.ai.available():
            self.status.setText('Esta instalación no incluye la IA local. Usa el paquete completo de ModLab.');return
        self.ai_mods=[];self.proposal=None;self.ai_grid.show_mods([]);self.add_all.setEnabled(False)
        mc=self.version.currentText().strip();loader=self.loader.currentText();limit=self.max_mods.value()
        def ready(result):
            self.proposal=result;self.ai_mods=result['mods'];self.ai_grid.show_mods(self.ai_mods,self.pack)
            text=plan_text(result['plan'])+'\n\n'+'\n'.join(result['warnings'])
            if result['rejected']:text+='\n\nDescartados: '+'; '.join(m['title']+': '+m['reason'] for m in result['rejected'])
            self.ai_summary.setPlainText(text);self.ai_count.setText(f"{len(self.ai_mods)} propuestas después de evaluar {result['candidate_count']} fichas. Revisa los motivos antes de añadirlas.")
            self.add_all.setEnabled(bool(self.ai_mods))
        self.run_task(lambda progress:self.designer.propose(phrase,mc,loader,limit,progress),ready)

    def add_mod(self,mod):
        if self.busy or mod['project_id'] in self.pack:return
        mc=self.version.currentText().strip();loader=self.loader.currentText()
        def ready(pinned):
            self.pack[pinned['project_id']]=pinned;self.refresh_pack()
            self.status.setText(pinned['title']+' añadido al pack con una versión compatible.')
        self.run_task(lambda progress:self.catalog.pin(mod,mc,loader),ready)

    def add_proposal(self):
        if self.busy:return
        for mod in self.ai_mods:
            if mod.get('minecraft')==self.version.currentText().strip() and mod.get('loader')==self.loader.currentText():
                self.pack[mod['project_id']]=mod
        self.refresh_pack();self.status.setText('Propuesta añadida. Puedes seguir explorando y ampliar el pack.')

    def refresh_pack(self):
        self.pack_badge.setText(f'Mi pack · {len(self.pack)}');self.pack_list.clear()
        for pid,mod in self.pack.items():
            item=QListWidgetItem(mod['title']+'\n'+(mod.get('role') or ', '.join(c['name'] for c in mod.get('categories',[])[:2]))+' · '+(mod.get('version_number') or 'Verificación pendiente'))
            item.setData(Qt.ItemDataRole.UserRole,pid);self.pack_list.addItem(item)
        self.pack_summary.setText(f'{len(self.pack)} mods elegidos · {self.version.currentText()} / {self.loader.currentText()} · dependencias completas al exportar.')
        self.browse_grid.update_pack(self.pack);self.ai_grid.update_pack(self.pack);self.export_button.setEnabled(bool(self.pack) and not self.busy);self.audit_button.setEnabled(bool(self.pack) and not self.busy)

    def remove_selected(self):
        if self.busy:return
        item=self.pack_list.currentItem()
        if item:self.pack.pop(item.data(Qt.ItemDataRole.UserRole),None);self.refresh_pack()

    def show_details(self,mod):
        if self.busy:return
        dialog=QDialog(self);dialog.setWindowTitle(mod['title']);dialog.resize(820,760)
        v=QVBoxLayout(dialog);v.addWidget(heading(mod['title'],'h1'))
        if mod.get('screenshots') or mod.get('logo'):
            cover=Cover(mod['title'],next(iter(mod.get('screenshots',[])),None) or mod.get('logo',''),self.images);cover.setFixedHeight(220);v.addWidget(cover)
        categories=QLabel(' · '.join(LABELS.get(c['name'],c['name']) for c in mod['categories']));categories.setWordWrap(True);categories.setObjectName('muted');v.addWidget(categories)
        text=QTextBrowser();text.setPlainText(mod.get('description','')+'\n\n'+('Por qué encaja: '+mod['reason'] if mod.get('reason') else '')+'\n'+mod.get('caveat',''));v.addWidget(text,1)
        actions=QHBoxLayout();web=QPushButton('Ver en CurseForge');web.clicked.connect(lambda:QDesktopServices.openUrl(QUrl('https://www.curseforge.com/minecraft/mc-mods/'+mod['slug'])));actions.addWidget(web)
        add=QPushButton('+ Añadir al pack');add.setObjectName('primary');add.setEnabled(mod['project_id'] not in self.pack)
        add.clicked.connect(lambda:(dialog.accept(),self.add_mod(mod)));actions.addWidget(add);close=QPushButton('Cerrar');close.clicked.connect(dialog.accept);actions.addWidget(close);v.addLayout(actions)
        def ready(description):
            text.setPlainText((('POR QUÉ ENCAJA\n'+mod['reason']+'\n'+mod.get('caveat','')+'\n\n') if mod.get('reason') else '')+description)
        self.run_task(lambda progress:self.catalog.description(mod['project_id']),ready);dialog.exec()

    def change_target(self,*_):
        self.ai_mods=[];self.proposal=None;self.ai_grid.show_mods([]);self.add_all.setEnabled(False)
        for mod in self.pack.values():
            for key in ('file_id','file','version_number','minecraft','loader'):mod.pop(key,None)
        self.browse_mods=[];self.browse_grid.show_mods([]);self.refresh_pack()
        self.status.setText('Versión cambiada. El pack conserva sus mods y se verificará de nuevo al exportar.')

    def save_project(self):
        path,_=QFileDialog.getSaveFileName(self,'Guardar proyecto','modlab-pack.json','Proyecto ModLab (*.json)')
        if not path:return
        try:
            value={'schema':1,'source':'curseforge','name':self.pack_name.text(),'minecraft':self.version.currentText(),
                   'loader':self.loader.currentText(),'mods':list(self.pack.values()),'description':self.prompt.toPlainText()}
            Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2))
            self.status.setText('Proyecto guardado: '+path)
        except OSError as exc:self.failure(str(exc))

    def open_project(self):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,'Abrir proyecto','','Proyecto ModLab (*.json)')
        if not path:return
        try:
            value=json.loads(Path(path).read_text())
            if value.get('schema')!=1 or value.get('source')!='curseforge' or not isinstance(value.get('mods'),list) or len(value['mods'])>1000:raise ValueError('Formato de proyecto no admitido.')
            if value['loader'] not in ('Forge','Fabric','NeoForge') or not isinstance(value['minecraft'],str):raise ValueError('Versión o cargador no válido.')
            for m in value['mods']:
                if m.get('source')!='curseforge' or type(m.get('project_id'))!=int or m['project_id']<=0 or not isinstance(m.get('title'),str):raise ValueError('El proyecto contiene mods no válidos.')
            self.version.setCurrentText(value['minecraft']);self.loader.setCurrentText(value['loader']);self.pack_name.setText(value.get('name','Mi pack'))
            self.pack={m['project_id']:m for m in value['mods']}
            # Mantiene los IDs elegidos; CurseForge los vuelve a verificar al exportar.
            self.prompt.setPlainText(value.get('description',''));self.refresh_pack();self.status.setText('Proyecto abierto. Los archivos se verificarán contra CurseForge al exportar.')
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:self.failure('No se pudo abrir el proyecto: '+str(exc))

    def check_pack(self):
        if self.busy or not self.pack:return
        mods=list(self.pack.values());mc=self.version.currentText().strip();loader=self.loader.currentText()
        def ready(result):
            added=result['dependencies']
            lines=[
                f"{result['selected']} mods elegidos + {len(added)} dependencias obligatorias.",
                f"Total previsto: {result['total']} mods para Minecraft {mc} / {loader}.",
                "",
            ]
            if added:
                lines.append('Se incorporarán automáticamente al exportar:')
                lines.extend('• '+m['title']+' ('+str(m['project_id'])+')' for m in added[:40])
                if len(added)>40:lines.append(f'… y {len(added)-40} dependencias más.')
            else:
                lines.append('No hay dependencias obligatorias adicionales.')
            lines.extend(['','Sin incompatibilidades declaradas en los archivos comprobados.',
                          'Esto no garantiza que Minecraft arranque ni que no haya conflictos sin declarar.'])
            QMessageBox.information(self,'Comprobación del modpack','\n'.join(lines))
            self.status.setText(f"Comprobación completada: {result['total']} mods, {len(added)} dependencias nuevas.")
        self.run_task(lambda progress:audit_pack(mods,mc,loader,progress,self.catalog),ready)

    def export_pack(self):
        if self.busy or not self.pack:return
        path,_=QFileDialog.getSaveFileName(self,'Exportar a CurseForge',self.pack_name.text()+'.zip','Modpack CurseForge (*.zip)')
        if not path:return
        if not path.lower().endswith('.zip'):path+='.zip'
        mods=list(self.pack.values());name=self.pack_name.text();mc=self.version.currentText().strip();loader=self.loader.currentText();build=self.loader_build.text().strip()
        def export(progress):
            progress('Comprobando cargador y dependencias de CurseForge…')
            version=build or resolve_loader_version(mc,loader)
            return build_pack(path,name,mc,loader,version,mods,progress,self.catalog)
        def ready(result):
            QMessageBox.information(self,'Pack preparado',f"{result['mods']} mods con dependencias.\n{result['path']}\n\nCurseForge → Minecraft → Importar → selecciona el ZIP.")
        self.run_task(export,ready)

    def run_task(self,task,ready):
        if self.busy:return
        self.busy=True;self.cancel.clear();worker=TaskThread(task,self.cancel);self.tasks.append(worker)
        self.progress.show();self.cancel_button.show();self.version.setEnabled(False);self.loader.setEnabled(False)
        self.ai_start.setEnabled(False);self.export_button.setEnabled(False);self.audit_button.setEnabled(False);self.refresh.setEnabled(False)
        for widget in (self.prompt,self.max_mods,self.search,self.category,self.sort,self.prev,self.next):widget.setEnabled(False)
        def deliver(result):
            try:ready(result)
            except Exception as exc:self.failure('No se pudo mostrar el resultado: '+str(exc))
        def progress(message):
            if message.startswith('EXPERIENCIA\n'):
                self.ai_summary.setPlainText(message.partition('\n')[2])
                self.status.setText('Interpretación preparada. Buscando opciones de CurseForge que encajen…')
            else:self.status.setText(message)
        worker.progress.connect(progress);worker.ready.connect(deliver);worker.failed.connect(self.failure)
        def finished():
            self.tasks.remove(worker);self.busy=False
            self.progress.hide();self.cancel_button.hide();self.version.setEnabled(True);self.loader.setEnabled(True)
            self.ai_start.setEnabled(True);self.refresh.setEnabled(True);self.export_button.setEnabled(bool(self.pack));self.audit_button.setEnabled(bool(self.pack))
            for widget in (self.prompt,self.max_mods,self.search,self.category,self.sort):widget.setEnabled(True)
            self.prev.setEnabled(self.index>0);self.next.setEnabled(self.index+50<min(10000,self.total))
            if self.cancel.is_set():self.status.setText('Operación cancelada. Tu pack se conserva.')
            if hasattr(self,'pending_theme'):
                theme=self.pending_theme;del self.pending_theme
                QTimer.singleShot(0,lambda:self.choose_theme(theme))
        worker.finished.connect(finished);worker.finished.connect(worker.deleteLater);worker.start()

    def cancel_task(self):
        self.cancel.set();self.status.setText('Cancelando al terminar el paso actual…')

    def failure(self,error):
        self.status.setText(error)
        # Los errores quedan visibles sin cerrar la biblioteca ni borrar la selección.
        if self.stack.currentIndex()==2:self.browse_info.setText(error)
        if self.stack.currentIndex()==1:self.ai_count.setText(error)

    def update_data(self):
        def ready(data):
            self.hw,self.packs=data;self.populate();self.status.setText('Hardware e instancias actualizados.')
        self.run_task(lambda progress:(hardware(),instances()),ready)

    def closeEvent(self,event):
        if self.tasks:
            self.cancel.set();self.status.setText('Finalizando el paso actual antes de cerrar. Vuelve a cerrar cuando termine.');event.ignore()
        else:event.accept()
    def update_profile(self,_=None):
        p=self.pack_combo.currentData()
        if not p:
            self.apply_btn.setEnabled(False);return
        self.apply_btn.setEnabled(True)
        r=recommend(p["mods"],self.hw,self.mode.currentText())
        self.current_profile=r
        enabled="Sí (si existe Oculus)" if r["shaders"] else "No"
        self.rec_label.setText(
            f"<b>Modpack:</b> {p['name']} • {p['mods']} mods<br><br>"
            f"• <b>RAM Java recomendada:</b> {r['heap']} GB máximo<br>"
            f"• <b>Distancia de renderizado:</b> {r['render']} chunks<br>"
            f"• <b>Simulación:</b> {r['simulation']} chunks<br>"
            f"• <b>FPS máximos:</b> {r['fps']}<br>"
            f"• <b>Shaders:</b> {enabled}<br><br>"
            "<span style='color:#9aafc1'>Estimación conservadora; medir FPS reales es una fase futura.</span>")

    def apply(self):
        p=self.pack_combo.currentData()
        if not p:return
        answer=QMessageBox.question(self,"Confirmar cambios",
            f"Se modificará la configuración gráfica de {p['name']} y se creará una copia de seguridad.\n"
            "Cierra Minecraft antes de continuar. ¿Aplicar?")
        if answer!=QMessageBox.StandardButton.Yes:return
        try:
            backup=apply_graphics(p,self.current_profile)
        except Exception as exc:
            QMessageBox.warning(self,"No se pudo aplicar",str(exc));return
        QMessageBox.information(self,"Perfil aplicado",
            f"Ajustes guardados. Copia de seguridad en:\n{backup}\n\nReinicia Minecraft para utilizarlos.")
        self.status.setText(f"Copia de seguridad: {backup}")

def main():
    if '--verify-ai' in sys.argv:
        result=LocalAI().complete('Devuelve un objeto JSON con ready igual a true.',{},
            {'type':'object','properties':{'ready':{'type':'boolean'}},'required':['ready'],'additionalProperties':False})
        if result.get('ready') is not True:raise SystemExit('La IA integrada no superó la comprobación.')
        print('IA integrada verificada.');return 0
    app=QApplication(sys.argv);app.setApplicationName('SMAPT-ModLab');app.setOrganizationName('SMAPT')
    app.setStyle('Fusion');app.setStyleSheet(STYLE)
    win=ModLab();win.show()
    if '--smoke' in sys.argv:QTimer.singleShot(1200,app.quit)
    return app.exec()

if __name__=='__main__':sys.exit(main())
