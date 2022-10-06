import logging

from ..formatters import LogFormatter
from .base_emitter import BaseEmitter

logger = logging.getLogger(__name__)


class LogEmitter(BaseEmitter):
    def __init__(self, metadata, formatter=None):
        """
        A LogEmitter simply logs the metrics emitted using the Python Logging library.
        :param metadata: A metric metadata object to log, along with the metric
        """
        super(LogEmitter, self).__init__()
        self.metadata = metadata
        self.formatter = formatter or LogFormatter()

    def format(self, metric_or_metrics):
        formatted_metrics = self.formatter.format(metric_or_metrics)
        return formatted_metrics

    def emit(self, metric_or_metrics):
        record = self.metadata.to_dict()
        record["metric"] = self.format(metric_or_metrics)
        logger.info(record)

    def close(self):
        pass
