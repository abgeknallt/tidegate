"""Single instance + remote control over a local socket.

Commands: show, ping, toggle-mic-mute, profile NAME, quit.
Bind `tidegate --mic-mute` etc. to a global shortcut in your desktop settings.
"""
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAME = f"tidegate-{os.getuid()}"


def send(command):
    """Send a command to the running instance; False if none is running."""
    sock = QLocalSocket()
    sock.connectToServer(NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write(command.encode() + b"\n")
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


class Server(QObject):
    received = Signal(str)

    def __init__(self):
        super().__init__()
        QLocalServer.removeServer(NAME)
        self.server = QLocalServer(self)
        self.server.listen(NAME)
        self.server.newConnection.connect(self._accept)

    def _accept(self):
        sock = self.server.nextPendingConnection()
        sock.readyRead.connect(lambda s=sock: self._read(s))
        sock.disconnected.connect(lambda s=sock: (self._read(s), s.deleteLater()))

    def _read(self, sock):
        for line in bytes(sock.readAll()).decode(errors="ignore").splitlines():
            if line.strip():
                self.received.emit(line.strip())
