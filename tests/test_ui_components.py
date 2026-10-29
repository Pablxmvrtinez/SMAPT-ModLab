"""Componentes de interfaz: caché de imágenes, saneado de descripciones y controles."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from modlab.ui import images
from modlab.ui.pages.details import safe_html, safe_markdown
from modlab.ui.widgets import SearchBox, Segmented, Shimmer, SkeletonCard


class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_only_official_image_hosts(self):
        self.assertEqual(images.allowed('https://media.forgecdn.net/avatars/1.png'), 'curseforge')
        self.assertEqual(images.allowed('https://cdn.modrinth.com/data/x/icon.webp'), 'modrinth')
        self.assertIsNone(images.allowed('http://cdn.modrinth.com/x.png'))
        self.assertIsNone(images.allowed('https://evil.example/x.png'))

    def test_memory_cache_respects_byte_budget(self):
        loader = images.ImageLoader(disk=False)
        with patch.object(images, 'MEMORY_BYTES', 100 * 100 * 4 * 3):
            for i in range(10):
                pixmap = QPixmap(100, 100)
                pixmap.fill(QColor('red'))
                loader._remember((str(i), 100, 100), pixmap)
        self.assertEqual(len(loader.memory), 3)
        self.assertEqual(list(loader.memory)[0][0], '7')
        self.assertLessEqual(loader.memory_bytes, 100 * 100 * 4 * 3)

    def test_large_images_are_downscaled(self):
        images.ImageLoader.RATIO = 1.0
        big = QImage(2000, 1000, QImage.Format.Format_ARGB32)
        scaled = images.ImageLoader.scaled_image(big, QSize(400, 140))
        self.assertLessEqual(scaled.width(), 400)
        self.assertGreaterEqual(scaled.height(), 140)
        self.assertLessEqual(scaled.height(), 200)

    def test_cached_image_is_delivered_without_network(self):
        loader = images.ImageLoader(disk=False)
        pixmap = QPixmap(10, 10)
        loader._remember(('https://cdn.modrinth.com/a.png', 10, 10), pixmap)
        got = []
        loader.fetch('https://cdn.modrinth.com/a.png', QSize(10, 10), got.append)
        self.assertEqual(len(got), 1)
        self.assertFalse(loader.pending)


class SanitizerTests(unittest.TestCase):
    def test_html_is_stripped_of_active_content(self):
        dirty = ('<script>alert(1)</script><p style="x" onclick="steal()">Texto</p><iframe src="x"></iframe>'
                 '<img src="https://x/y.png"><!-- comentario --><a href="https://ok">enlace</a><center> </center>')
        clean = safe_html(dirty)
        for bad in ('script', 'onclick', 'iframe', '<img', 'comentario', 'style=', '<center'):
            self.assertNotIn(bad, clean)
        self.assertIn('Texto', clean)
        self.assertIn('href="https://ok"', clean)

    def test_markdown_images_and_html_blocks(self):
        text = safe_markdown('[![b](https://x/b.png)](https://d)\nHola\n<h2 id="i">Guía</h2>\nFin')
        self.assertNotIn('b.png', text)
        self.assertIn('## Guía', text)
        self.assertTrue(text.startswith('Hola'))


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_segmented_emits_only_on_change(self):
        control = Segmented([('a', 'A'), ('b', 'B')])
        seen = []
        control.changed.connect(seen.append)
        control.buttons['b'].click()
        control.buttons['b'].click()
        self.assertEqual(seen, ['b'])
        self.assertEqual(control.current, 'b')

    def test_search_box_debounces(self):
        box = SearchBox('buscar')
        box.timer.setInterval(10)
        seen = []
        box.search.connect(seen.append)
        for text in ('c', 'cr', 'cre'):
            box.setText(text)
            box.textEdited.emit(text)
        deadline = time.monotonic() + 1
        while not seen and time.monotonic() < deadline:
            self.qt.processEvents()
            time.sleep(0.005)
        self.assertEqual(seen, ['cre'])

    def test_shimmer_stops_without_skeletons(self):
        card = SkeletonCard()
        self.assertEqual(Shimmer.instance.state(), Shimmer.State.Running)
        card.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.qt.processEvents()
        self.assertEqual(Shimmer.users, 0)
        self.assertNotEqual(Shimmer.instance.state(), Shimmer.State.Running)


if __name__ == '__main__':
    unittest.main()
