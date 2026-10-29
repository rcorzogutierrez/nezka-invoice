from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nezka_invoice.db import ProductRepository
from nezka_invoice.models import Product
from nezka_invoice.ui.theme import brand_stripe
from nezka_invoice.ui.widgets import dialog_header, form_section

MAX_IMAGE_SIDE = 600
IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"


def image_to_png_bytes(image: QImage) -> bytes:
    """Downscale large photos so the database stays small, and store them as PNG."""
    if max(image.width(), image.height()) > MAX_IMAGE_SIDE:
        image = image.scaled(MAX_IMAGE_SIDE, MAX_IMAGE_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


class ProductDialog(QDialog):
    """Form used both to create a new product and to edit an existing one."""

    def __init__(self, repo: ProductRepository, product: Product | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repo = repo
        self.product = product
        self.saved_record: Product | None = None
        self.image: bytes | None = product.image if product else None
        self.setWindowTitle("Editar producto" if product else "Nuevo producto")
        self.setMinimumWidth(820)

        self.ref = QLineEdit()
        self.ref.setPlaceholderText("Ej. 49")
        self.description = QLineEdit()
        self.description.setPlaceholderText("Ej. NEZKA PLANTAIN CHIPS SALTED")
        self.upc = QLineEdit()
        self.upc.setPlaceholderText("Código de barras")
        self.size = QLineEdit()
        self.size.setPlaceholderText("Ej. 28 OZ, 100GR")
        self.pack = QLineEdit()
        self.pack.setPlaceholderText("Ej. 6, 12/50PC")
        self.price = QDoubleSpinBox()
        self.price.setPrefix("$ ")
        self.price.setDecimals(2)
        self.price.setMaximum(1_000_000)
        self.price.setGroupSeparatorShown(True)
        self.qty_per_pallet = QLineEdit()
        self.qty_per_pallet.setPlaceholderText("Cajas por pallet")
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(80)
        self.notes.setPlaceholderText("Ej. PRODUCT OF ECUADOR, KOSHER")
        self.active = QCheckBox("Producto activo")
        self.active.setChecked(True)

        self.preview = QLabel(objectName="ImagePreview")
        self.preview.setFixedSize(220, 220)
        self.preview.setAlignment(Qt.AlignCenter)
        choose = QPushButton("Elegir foto…")
        self.remove_image_button = QPushButton("Quitar", objectName="Danger")
        choose.clicked.connect(self.choose_image)
        self.remove_image_button.clicked.connect(self.remove_image)
        image_buttons = QHBoxLayout()
        image_buttons.addWidget(choose, 1)
        image_buttons.addWidget(self.remove_image_button)

        photo = QFrame(objectName="Card")
        photo_layout = QVBoxLayout(photo)
        photo_layout.setContentsMargins(18, 14, 18, 16)
        photo_layout.setSpacing(10)
        photo_layout.addWidget(QLabel("FOTO", objectName="SectionLabel"))
        photo_layout.addWidget(self.preview, 0, Qt.AlignCenter)
        photo_layout.addLayout(image_buttons)
        photo_layout.addStretch(1)

        details = form_section(
            "DATOS DEL PRODUCTO",
            [
                [("Ref.", self.ref, 1), ("UPC", self.upc, 1)],
                [("Descripción *", self.description, 2)],
                [("Tamaño / unidad", self.size, 1), ("Pack", self.pack, 1)],
                [("Precio por caja", self.price, 1), ("Cajas por pallet", self.qty_per_pallet, 1)],
                [("Notas", self.notes, 2)],
            ],
        )
        details.layout().addWidget(self.active, details.layout().rowCount(), 0, 1, 2)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        columns.addWidget(photo)
        columns.addWidget(details, 1)

        save_button = QPushButton("Guardar producto", objectName="Primary")
        save_button.setDefault(True)
        cancel_button = QPushButton("Cancelar")
        save_button.clicked.connect(self.save)
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)

        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 20)
        body.setSpacing(16)
        body.addLayout(columns)
        body.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(brand_stripe())
        layout.addWidget(
            dialog_header(
                "Editar producto" if product else "Nuevo producto",
                "Estos datos aparecen en las líneas de las proformas y facturas.",
            )
        )
        layout.addLayout(body)

        if product:
            self._load(product)
        else:
            self.ref.setText(repo.next_ref())
        self._show_image()

    def _load(self, product: Product) -> None:
        self.ref.setText(product.ref)
        self.description.setText(product.description)
        self.upc.setText(product.upc)
        self.size.setText(product.size)
        self.pack.setText(product.pack)
        self.qty_per_pallet.setText(product.qty_per_pallet)
        self.notes.setPlainText(product.notes)
        self.price.setValue(product.price_per_box)
        self.active.setChecked(product.active)

    def _show_image(self) -> None:
        pixmap = QPixmap()
        if self.image:
            pixmap.loadFromData(self.image)
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Sin foto")
        else:
            self.preview.setText("")
            side = self.preview.width() - 16
            self.preview.setPixmap(pixmap.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.remove_image_button.setEnabled(bool(self.image))

    def choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Elegir foto del producto", "", IMAGE_FILTER)
        if path:
            self.set_image_from_file(path)

    def set_image_from_file(self, path: str) -> bool:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            QMessageBox.warning(self, "Foto no válida", f"No se pudo abrir la imagen:\n{reader.errorString()}")
            return False
        self.image = image_to_png_bytes(image)
        self._show_image()
        return True

    def remove_image(self) -> None:
        self.image = None
        self._show_image()

    def form_product(self) -> Product:
        return Product(
            ref=self.ref.text(),
            description=self.description.text(),
            upc=self.upc.text(),
            size=self.size.text(),
            pack=self.pack.text(),
            qty_per_pallet=self.qty_per_pallet.text(),
            notes=self.notes.toPlainText(),
            price_per_box=self.price.value(),
            image=self.image,
            active=self.active.isChecked(),
            id=self.product.id if self.product else None,
        )

    def save(self) -> None:
        product = self.form_product()
        errors = product.validate()
        if errors:
            QMessageBox.warning(self, "Revisa los datos", "\n".join(errors))
            return
        if self.repo.ref_exists(product.ref, exclude_id=product.id):
            answer = QMessageBox.question(
                self,
                "Referencia duplicada",
                f"Ya existe un producto con la referencia «{product.ref.strip()}». ¿Guardar de todos modos?",
            )
            if answer != QMessageBox.Yes:
                return
        self.saved_record = self.repo.update(product) if product.id else self.repo.add(product)
        self.accept()
