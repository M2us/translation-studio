"""Qt media widgets; one audio controller is shared by all projects and tabs."""
import wave
from PySide6.QtCore import QObject, QTimer, Signal, Qt, QRectF, QBuffer, QIODevice, QSize
from PySide6.QtGui import QPixmap, QPainter, QIcon, QImageReader
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QGraphicsView, QGraphicsScene, QSlider, QCheckBox, QListWidget,
                               QListWidgetItem, QListView, QDialog, QAbstractItemView)
from PySide6.QtMultimedia import QAudioSink, QAudioFormat, QMediaDevices, QtAudio
from .core import StudioError, safe_path
from .i18n import tr


class AudioController(QObject):
    changed = Signal(str, int, int)
    failed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sink = None
        self.buffer = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._next)
        self.audio_poll = QTimer(self)
        self.audio_poll.setInterval(20)
        self.audio_poll.timeout.connect(self._poll_audio)
        self.queue = []
        self.index = -1
        self.active = False

    def play(self, queue):
        self.stop()
        if not queue:
            return
        self.queue = list(queue)
        self.index = -1
        self.active = True
        self._next()

    def stop(self):
        self.active = False
        self.timer.stop()
        self._release()
        self.queue = []
        self.index = -1
        self.changed.emit("", 0, 0)

    def _release(self):
        self.audio_poll.stop()
        if self.sink:
            self.sink.reset()
            self.sink.deleteLater()
            self.sink = None
        if self.buffer:
            self.buffer.close()
            self.buffer.deleteLater()
            self.buffer = None

    def _next(self):
        if not self.active:
            return
        self.index += 1
        if self.index >= len(self.queue):
            self.stop()
            return
        item = self.queue[self.index]
        self.changed.emit(item["id"], self.index + 1, len(self.queue))
        self._release()
        try:
            with wave.open(item["path"], "rb") as wav:
                width = wav.getsampwidth()
                data = wav.readframes(wav.getnframes())
                if len(data) != wav.getnframes() * wav.getnchannels() * width:
                    raise StudioError("unsupported_audio", path=item["path"])
                fmt = QAudioFormat()
                fmt.setSampleRate(wav.getframerate())
                fmt.setChannelCount(wav.getnchannels())
                if width == 3:
                    # Packed signed 24-bit PCM -> signed 32-bit PCM without amplitude loss.
                    data = b"".join(b"\x00" + data[i:i + 3] for i in range(0, len(data), 3))
                    width = 4
                formats = {1: QAudioFormat.SampleFormat.UInt8, 2: QAudioFormat.SampleFormat.Int16,
                           4: QAudioFormat.SampleFormat.Int32}
                if width not in formats:
                    raise StudioError("unsupported_audio", path=item["path"])
                fmt.setSampleFormat(formats[width])
            device = QMediaDevices.defaultAudioOutput()
            if device.isNull():
                raise StudioError("audio_device")
            self.buffer = QBuffer(self)
            self.buffer.setData(data)
            self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.sink = QAudioSink(device, fmt, self)
            self.sink.setVolume(.8)
            self.sink.start(self.buffer)
            self.audio_poll.start()
        except (OSError, wave.Error, StudioError) as error:
            self.stop()
            self.failed.emit(error if isinstance(error, StudioError) else StudioError(
                "audio_error", id=item["id"], detail=str(error)))

    def _poll_audio(self):
        if not self.active or not self.sink:
            return
        state = self.sink.state()
        if state == QtAudio.State.IdleState and self.buffer.atEnd():
            self.audio_poll.stop()
            self.timer.start(self.queue[self.index]["pause"] if self.index + 1 < len(self.queue) else 0)
        elif state == QtAudio.State.StoppedState and self.sink.error() != QtAudio.Error.NoError:
            self.audio_poll.stop()
            QTimer.singleShot(0, self._device_error)

    def _device_error(self):
        if self.active:
            self.stop()
            self.failed.emit(StudioError("audio_device"))


class ImageView(QGraphicsView):
    zoomed = Signal(float)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.setMinimumHeight(180)

    def show_image(self, path):
        self.scene().clear()
        self.resetTransform()
        if path is None:
            return
        try:
            with path.open("rb") as stream:
                if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError()
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                raise ValueError()
        except (OSError, ValueError):
            raise StudioError("image_error", path=str(path))
        self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        self.fit()
        return pixmap.width(), pixmap.height()

    def fit(self):
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        if 0.02 < self.transform().m11() * factor < 50:
            self.scale(factor, factor)
            self.zoomed.emit(factor)
        event.accept()


class ImageCompare(QWidget):
    def __init__(self, language):
        super().__init__()
        self.language = language
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        fit = QPushButton(tr("fit", language))
        self.linked = QCheckBox(tr("linked", language))
        self.linked.setChecked(True)
        bar.addWidget(fit)
        bar.addWidget(self.linked)
        bar.addStretch()
        layout.addLayout(bar)
        views = QHBoxLayout()
        self.views, self.labels = [], []
        for key in ("source", "translation"):
            box = QVBoxLayout()
            title = QLabel(tr(key, language))
            self.labels.append(title)
            box.addWidget(title)
            view = ImageView()
            self.views.append(view)
            box.addWidget(view)
            views.addLayout(box)
        layout.addLayout(views)
        fit.clicked.connect(lambda: [view.fit() for view in self.views])
        self.views[0].zoomed.connect(lambda factor: self.sync_zoom(1, factor))
        self.views[1].zoomed.connect(lambda factor: self.sync_zoom(0, factor))
        for i in (0, 1):
            for getter in ("horizontalScrollBar", "verticalScrollBar"):
                source = getattr(self.views[i], getter)()
                target = getattr(self.views[1 - i], getter)()
                source.valueChanged.connect(lambda value, src=source, dst=target: self.sync_scroll(src, dst, value))
        self.syncing = False

    def sync_scroll(self, source, target, value):
        if self.linked.isChecked() and not self.syncing and source.maximum() > source.minimum():
            self.syncing = True
            ratio = (value - source.minimum()) / (source.maximum() - source.minimum())
            target.setValue(round(target.minimum() + ratio * (target.maximum() - target.minimum())))
            self.syncing = False

    def sync_zoom(self, index, factor):
        if self.linked.isChecked():
            self.views[index].scale(factor, factor)

    def display(self, project, tab_id, entry_id, target, variant_id=None):
        for i, language in enumerate((project.config["sourceLanguage"], target)):
            title = tr("source" if i == 0 else "translation", self.language) + " · " + language
            try:
                path, stale = project.media_side(tab_id, entry_id, language, variant_id if i else None)
                size = self.views[i].show_image(path)
                title += " · " + str(size[0]) + " × " + str(size[1])
                if stale:
                    title += "\n" + tr("stale_preview", self.language, path=str(path))
            except StudioError as error:
                self.views[i].show_image(None)
                title += "\n" + error.issue.message(self.language)
            self.labels[i].setText(title)
            self.labels[i].setWordWrap(True)


class ContextScreenshots(QWidget):
    """Project-owned PNG references, with bounded thumbnails and a zoomable viewer."""
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.signature = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(QLabel(tr("screenshots", owner.language)))
        self.items = QListWidget()
        self.items.setViewMode(QListView.ViewMode.IconMode)
        self.items.setMovement(QListView.Movement.Static)
        self.items.setFlow(QListView.Flow.LeftToRight)
        self.items.setWrapping(False)
        self.items.setIconSize(QSize(128, 72))
        self.items.setGridSize(QSize(162, 112))
        self.items.setFixedHeight(140)
        self.items.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items.itemClicked.connect(self.open_item)
        layout.addWidget(self.items)

    def display(self, project, screenshots):
        self.setVisible(bool(screenshots))
        signature = (str(project.root), tuple((s["path"], s.get("caption", "")) for s in screenshots))
        if signature == self.signature:
            return
        self.signature = signature
        self.items.clear()
        for shot in screenshots:
            item = QListWidgetItem(shot.get("caption") or tr("enlarge", self.owner.language))
            item.setData(Qt.ItemDataRole.UserRole, shot)
            item.setToolTip(shot.get("caption", "") + "\n" + shot["path"])
            try:
                path = safe_path(project.root, shot["path"])
                reader = QImageReader(str(path), b"PNG")
                reader.setScaledSize(reader.size().scaled(128, 72, Qt.AspectRatioMode.KeepAspectRatio))
                thumb = reader.read()
                if thumb.isNull():
                    raise StudioError("image_error", path=shot["path"])
                item.setIcon(QIcon(QPixmap.fromImage(thumb)))
            except StudioError as error:
                item.setToolTip(error.issue.message(self.owner.language))
                item.setText("⚠ " + item.text())
            self.items.addItem(item)

    def open_item(self, item):
        shot = item.data(Qt.ItemDataRole.UserRole)
        dialog = QDialog(self.owner)
        dialog.setWindowTitle(shot.get("caption") or tr("screenshots", self.owner.language))
        dialog.resize(1000, 720)
        layout = QVBoxLayout(dialog)
        view = ImageView()
        layout.addWidget(view)
        caption = QLabel(shot.get("caption", ""))
        caption.setTextFormat(Qt.TextFormat.PlainText)
        caption.setWordWrap(True)
        layout.addWidget(caption)
        fit = QPushButton(tr("fit", self.owner.language))
        fit.clicked.connect(view.fit)
        layout.addWidget(fit)
        try:
            view.show_image(safe_path(self.owner.project.root, shot["path"]))
        except StudioError as error:
            self.owner.error(error)
            dialog.deleteLater()
            return
        QTimer.singleShot(0, view.fit)
        dialog.exec()
        dialog.deleteLater()
