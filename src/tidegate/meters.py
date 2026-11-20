"""Live level meters: one tiny `parec` per watched source, peak-detected."""
from PySide6.QtCore import QObject, QProcess, QTimer

from .engine import level_from_pcm


class Meters(QObject):
    DECAY = 0.035

    def __init__(self):
        super().__init__()
        self.procs, self.levels = {}, {}
        QTimer(self, interval=33, timeout=self._decay).start()

    def watch(self, sources):
        for name in [n for n in self.procs if n not in sources]:
            self._stop(name)
        for name in sources:
            proc = self.procs.get(name)
            if proc is None or proc.state() == QProcess.NotRunning:
                self._start(name)

    def level(self, source):
        return self.levels.get(source, 0.0)

    def _start(self, name):
        proc = QProcess(self)
        proc.setProgram("parec")
        proc.setArguments(["-d", name, "--raw", "--format=s16le", "--rate=8000",
                           "--channels=1", "--latency-msec=25", "--client-name=tidegate-meter"])
        proc.readyReadStandardOutput.connect(lambda n=name, p=proc: self._read(n, p))
        self.procs[name] = proc
        proc.start()

    def _stop(self, name):
        proc = self.procs.pop(name, None)
        self.levels.pop(name, None)
        if proc is not None:
            proc.kill()
            proc.deleteLater()

    def _read(self, name, proc):
        level = level_from_pcm(bytes(proc.readAllStandardOutput()))
        if level > self.levels.get(name, 0.0):
            self.levels[name] = level

    def _decay(self):
        for name, value in self.levels.items():
            if value > 0:
                self.levels[name] = max(0.0, value - self.DECAY)

    def stop_all(self):
        for name in list(self.procs):
            self._stop(name)
