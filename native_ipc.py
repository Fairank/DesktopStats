"""Current-user named-pipe IPC. The desktop app never opens a web port."""

import hashlib
import json

from PySide6.QtNetwork import QLocalSocket

from stats_config import BASE


def name():
    return "DesktopStatsNative-" + hashlib.sha256(str(BASE).encode()).hexdigest()[:20]


def send(command, timeout=1800):
    socket = QLocalSocket()
    socket.connectToServer(name())
    if not socket.waitForConnected(timeout):
        return None
    socket.write(json.dumps(command).encode() + b"\n")
    socket.flush()
    socket.waitForBytesWritten(timeout)
    response = bytearray()
    while b"\n" not in response and len(response) < 65536:
        if socket.bytesAvailable() or socket.waitForReadyRead(timeout):
            response.extend(socket.readAll().data())
        else:
            break
    socket.disconnectFromServer()
    try:
        return json.loads(bytes(response))
    except ValueError:
        return None
