"""분석 백그라운드 워커 (QThread 기반)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThread, Signal, Slot


class WorkerSignals(QObject):
    status_update = Signal(str)
    progress = Signal(int)
    finished = Signal(object)   # AnalysisResult
    error = Signal(str)


class AnalysisWorker(QRunnable):
    """QThreadPool에서 실행되는 분석 워커."""

    def __init__(self, source_code: str, output_dir: str):
        super().__init__()
        self.source_code = source_code
        self.output_dir = output_dir
        self.signals = WorkerSignals()
        self._cancel = False
        self.setAutoDelete(True)

    def cancel(self):
        self._cancel = True

    @Slot()
    def run(self):
        try:
            from ..core.pipeline import AnalysisPipeline

            pipeline = AnalysisPipeline()

            def status_cb(msg: str):
                self.signals.status_update.emit(msg)

            def cancel_fn() -> bool:
                return self._cancel

            result = pipeline.run(
                source_code=self.source_code,
                output_dir=self.output_dir,
                cancel_fn=cancel_fn,
                status_fn=status_cb,
            )
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
