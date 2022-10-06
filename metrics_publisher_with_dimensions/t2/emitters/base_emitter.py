import logging

logger = logging.getLogger(__name__)


class BaseEmitter(object):
    def __init__(self):
        """
        A BaseEmitter should be the parent class of all emitters.
        All subclasses should implement .format() and .send()
        """
        self._formatter = None

    @property
    def formatter(self):
        """
        Get the configured formatter
        :return: A Formatter object
        """
        return self._formatter

    @formatter.setter
    def formatter(self, f):
        """
        Set the formatter
        :param f: The formatter to use
        :return: None
        """
        self._formatter = f

    def format(self, metric_or_metrics):
        """
        Format a metric (or metrics) for sending over the wire
        :param metric_or_metrics: The metric or metrics to format
        :return: Data ready to be sent over the wire
        """
        raise NotImplementedError("Must implement in a child class")

    def emit(self, metric_or_metrics):
        """
        Emit a metric.
        :param metric_or_metrics: A metric (or metrics) to emit
        :return: None
        """
        raise NotImplementedError("Must implement in a child class")

    def close(self):
        """
        Close any open connections or handles and flush metrics.
        :return: None
        """
        raise NotImplementedError("Must implement in a child class")
