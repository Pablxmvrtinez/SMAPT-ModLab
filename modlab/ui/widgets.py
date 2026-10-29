"""Tarjetas, imágenes asíncronas y arte de interfaz nativo de Qt."""
import math
from PySide6.QtCore import Qt,QRectF,QUrl,Signal,QTimer
from PySide6.QtGui import QColor,QPainter,QPainterPath,QLinearGradient,QPixmap,QFont,QPolygonF
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QVBoxLayout,QHBoxLayout,QPushButton,QScrollArea,QGridLayout,QSizePolicy)


LABELS={'Adventure and RPG':'Aventura y RPG','World Gen':'Generación del mundo','Cosmetic':'Decoración',
        'Technology':'Tecnología','Magic':'Magia','Utility & QoL':'Utilidad y comodidad','Food':'Comida',
        'Farming':'Agricultura','Mobs':'Criaturas','Structures':'Estructuras','Storage':'Almacenamiento',
        'Biomes':'Biomas','Dimensions':'Dimensiones','Armor, Tools, and Weapons':'Armas y equipo',
        'API and Library':'Bibliotecas','Map and Information':'Mapas e información','Performance':'Rendimiento',
        'Server Utility':'Servidores','Redstone':'Redstone','Energy':'Energía','Processing':'Procesamiento',
        'Transport':'Transporte','Ores and Resources':'Minerales y recursos','Twitch Integration':'Integraciones'}


class Images:
    def __init__(self,parent):
        self.network=QNetworkAccessManager(parent);self.pending={}
    def fetch(self,url,callback):
        parsed=QUrl(url)
        host=parsed.host()
        if parsed.scheme()!='https' or not (host=='forgecdn.net' or host.endswith('.forgecdn.net')):return
        if url in self.pending:self.pending[url].append(callback);return
        self.pending[url]=[callback]
        request=QNetworkRequest(parsed);request.setTransferTimeout(12000)
        reply=self.network.get(request);reply.setReadBufferSize(8*1024*1024)
        def finished():
            pixmap=QPixmap()
            if reply.error()==reply.NetworkError.NoError:
                pixmap.loadFromData(bytes(reply.readAll()))
            callbacks=self.pending.pop(url,[])
            if not pixmap.isNull():
                pixmap=pixmap.scaled(640,360,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                for cb in callbacks:
                    try:cb(pixmap)
                    except RuntimeError:pass # Una tarjeta puede haber salido de la página.
            reply.deleteLater()
        reply.finished.connect(finished)


class Artwork(QWidget):
    """Paisaje isométrico original dibujado por código, sin imágenes de mods ficticios."""
    def __init__(self,variant='world',parent=None):
        super().__init__(parent);self.variant=variant;self.setMinimumHeight(170)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height()
        gradient=QLinearGradient(0,0,w,h);gradient.setColorAt(0,QColor('#141c35'));gradient.setColorAt(1,QColor('#351322'))
        p.fillRect(self.rect(),gradient)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(28):
            x=(i*97+47)%max(1,w);y=(i*29+13)%max(1,int(h*.7))
            p.setBrush(QColor('#6774a5') if i%3 else QColor('#cf5975'));p.drawEllipse(QRectF(x,y,2,2))
        p.setBrush(QColor('#325496'));p.drawEllipse(QRectF(w*.67,h*.08,85,85))
        # Islas de bloques, castillo y sendero en perspectiva isométrica.
        tile=max(13,min(29,w/20));cx=w*.67;cy=h*.6
        def cube(x,y,z,color):
            sx=cx+(x-y)*tile;sy=cy+(x+y)*tile*.43-z*tile*.8
            points=[(sx,sy),(sx+tile,sy+tile*.43),(sx,sy+tile*.86),(sx-tile,sy+tile*.43)]
            from PySide6.QtCore import QPointF
            def poly(coords,paint):
                p.setBrush(QColor(paint));p.drawPolygon(QPolygonF([QPointF(*a) for a in coords]))
            poly(points,color)
            poly([points[1],points[2],(points[2][0],points[2][1]+tile*.8),(points[1][0],points[1][1]+tile*.8)],'#162544')
            poly([points[2],points[3],(points[3][0],points[3][1]+tile*.8),(points[2][0],points[2][1]+tile*.8)],'#292337')
        for x in range(-3,4):
            for y in range(-3,4):
                if abs(x)+abs(y)<6:cube(x,y,0,'#385d69' if (x+y)%3 else '#4c637a')
        for x,y in [(-2,-2),(2,-2),(-2,2),(2,2)]:
            for z in range(1,4):cube(x,y,z,'#69718d' if z<3 else '#bb3c5f')
        for x,y in [(0,-2),(1,-2),(-1,-2),(-2,-1),(-2,0),(-2,1)]:cube(x,y,1,'#69718d')
        for z in range(1,3):cube(0,0,z,'#3d69ad')
        p.end()


class Cover(QWidget):
    def __init__(self,title,url,images,parent=None):
        super().__init__(parent);self.pixmap=None;self.title=title;self.setFixedHeight(140)
        if url:images.fetch(url,self.loaded)
    def loaded(self,pixmap):self.pixmap=pixmap;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(self.rect());path=QPainterPath();path.addRoundedRect(rect,12,12);p.setClipPath(path)
        gradient=QLinearGradient(0,0,self.width(),140);gradient.setColorAt(0,QColor('#1c2e4e'));gradient.setColorAt(1,QColor('#412336'))
        p.fillRect(self.rect(),gradient)
        if self.pixmap is not None:
            image=self.pixmap.scaled(self.width(),140,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((self.width()-image.width())//2,(140-image.height())//2,image)
        else:
            p.setPen(QColor('#7c93c1'));p.setFont(QFont('Noto Sans',35,QFont.Weight.Bold))
            p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,self.title[:2].upper())
        p.end()


def downloads(value):
    if value>=1_000_000:return f'{value/1_000_000:.1f} M'
    if value>=1000:return f'{value/1000:.0f} mil'
    return str(value)


class ModCard(QFrame):
    add=Signal(object);details=Signal(object)
    def __init__(self,mod,images,in_pack=False,parent=None):
        super().__init__(parent);self.mod=mod;self.setObjectName('modCard')
        self.setMinimumWidth(240);self.setMaximumWidth(430)
        v=QVBoxLayout(self);v.setContentsMargins(12,12,12,12);v.setSpacing(8)
        url=next((u for u in mod.get('screenshots',[]) if u),None) or mod.get('logo','')
        v.addWidget(Cover(mod['title'],url,images))
        top=QHBoxLayout();source=QLabel('CURSEFORGE');source.setObjectName('source');top.addWidget(source)
        top.addStretch();count=QLabel('↓ '+downloads(mod.get('downloads',0)));count.setObjectName('muted');top.addWidget(count);v.addLayout(top)
        title=QLabel(mod['title']);title.setTextFormat(Qt.TextFormat.PlainText);title.setWordWrap(True)
        title.setObjectName('cardTitle');title.setFixedHeight(42);v.addWidget(title)
        tags=QHBoxLayout();tags.setSpacing(4)
        for cat in mod.get('categories',[])[:2]:
            tag=QLabel(LABELS.get(cat['name'],cat['name']));tag.setObjectName('tag');tag.setMaximumWidth(155)
            tags.addWidget(tag)
        tags.addStretch();v.addLayout(tags)
        desc=QLabel(mod.get('reason') or mod.get('description',''));desc.setTextFormat(Qt.TextFormat.PlainText)
        desc.setWordWrap(True);desc.setFixedHeight(54);desc.setObjectName('muted');desc.setToolTip(desc.text());v.addWidget(desc)
        actions=QHBoxLayout();detail=QPushButton('Ver ficha');detail.clicked.connect(lambda:self.details.emit(mod));actions.addWidget(detail)
        self.button=QPushButton('✓ En tu pack' if in_pack else '+ Añadir')
        self.button.setObjectName('primary' if not in_pack else 'selected');self.button.setEnabled(not in_pack)
        self.button.clicked.connect(lambda:self.add.emit(mod));actions.addWidget(self.button);v.addLayout(actions)
    def set_in_pack(self,value):
        self.button.setText('✓ En tu pack' if value else '+ Añadir');self.button.setEnabled(not value)


class CardGrid(QScrollArea):
    add=Signal(object);details=Signal(object)
    def __init__(self,images,parent=None):
        super().__init__(parent);self.images=images;self.cards=[];self.columns=0
        self.setWidgetResizable(True);self.setFrameShape(QFrame.Shape.NoFrame)
        self.container=QWidget();self.grid=QGridLayout(self.container);self.grid.setContentsMargins(0,4,0,4);self.grid.setSpacing(14)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop);self.setWidget(self.container)
    def show_mods(self,mods,pack_ids=()):
        for card in self.cards:self.grid.removeWidget(card);card.deleteLater()
        self.cards=[]
        for mod in mods:
            card=ModCard(mod,self.images,mod['project_id'] in pack_ids)
            card.add.connect(self.add.emit);card.details.connect(self.details.emit);self.cards.append(card)
        self.columns=0;self.reflow()
    def reflow(self):
        columns=max(1,self.viewport().width()//270)
        if columns==self.columns:return
        self.columns=columns
        for i,card in enumerate(self.cards):self.grid.addWidget(card,i//columns,i%columns)
    def resizeEvent(self,event):
        super().resizeEvent(event);QTimer.singleShot(0,self.reflow)
    def update_pack(self,ids):
        for card in self.cards:card.set_in_pack(card.mod['project_id'] in ids)
