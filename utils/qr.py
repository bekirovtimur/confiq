"""Bounded QR generation shared by all configuration views."""

import base64
import io
from dataclasses import dataclass, field
from typing import Optional

import qrcode
from qrcode.exceptions import DataOverflowError


MAX_VERSION = 15
ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_M
BORDER = 4
BOX_SIZE = 6

TOO_LARGE_MESSAGE = (
    'Конфигурация слишком большая для удобного сканирования. '
    'Скачайте файл и импортируйте его в приложение.'
)
EMPTY_MESSAGE = 'Конфигурация пуста. QR-код недоступен.'


@dataclass(frozen=True)
class QRResult:
    # Do not expose configuration contents (including private keys) in repr/logs.
    _qr: Optional[qrcode.QRCode] = field(default=None, repr=False)
    reason: str = ''

    @property
    def available(self):
        return self._qr is not None

    @property
    def version(self):
        return self._qr.version if self.available else None

    @property
    def total_modules(self):
        return self._qr.modules_count + 2 * BORDER if self.available else 0

    def png(self):
        if not self.available:
            raise ValueError('Cannot render an unavailable QR code')
        buffer = io.BytesIO()
        self._qr.make_image(fill_color='black', back_color='white').save(
            buffer, format='PNG'
        )
        return buffer.getvalue()

    def data_uri(self):
        return 'data:image/png;base64,' + base64.b64encode(self.png()).decode('ascii')


def prepare_qr(text):
    """Find the smallest allowed QR, without rendering PNG or changing the text.

    Never use automatic fitting: oversized payloads must not advance to version
    41. Only the first version that fits completes the QR matrix. Availability
    checks do not create images.
    """
    if not text:
        return QRResult(reason=EMPTY_MESSAGE)

    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECTION,
        box_size=BOX_SIZE,
        border=BORDER,
    )
    qr.add_data(text)
    for version in range(1, MAX_VERSION + 1):
        qr.version = version
        try:
            qr.make(fit=False)
        except DataOverflowError:
            continue
        return QRResult(_qr=qr)

    return QRResult(reason=TOO_LARGE_MESSAGE)
