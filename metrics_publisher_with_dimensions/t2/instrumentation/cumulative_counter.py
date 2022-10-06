import logging

from .gauge import Gauge

logger = logging.getLogger(__name__)


class CumulativeCounter(Gauge):
    def __init__(self, client, name, override_tags=None):
        """
        A cumulative counter is a counter whose value always increases. A canonical
        use-case for this kind of counter would be a "bytes in" counter on a network
        device, or a "total requests served" counter on a web service. The interface is the
        same as :py:class: `t2.instrumentation.gauge.Gauge`, so read the docs for that class
        if you require more information.

        :param client: The metrics client
        :param name: The name of the metric to be submitted.
        :param override_tags: Optional dictionary of metadata to override the default metadata
        """
        super(CumulativeCounter, self).__init__(client, name, override_tags=override_tags)

    @property
    def value(self):
        """
        Get the value of the gauge
        :return: The current value of the Gauge
        """
        return self._value

    @value.setter
    def value(self, v):
        if v <= self.value:
            logger.warning("New value must be greater than old value for CumulativeCounter metrics.")
            return
        self._value = v
