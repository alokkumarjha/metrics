from ..models.gauge_metric import GaugeMetric
import contextdecorator

from .mixins import InstrumentationBase


class Gauge(contextdecorator.ContextDecorator, InstrumentationBase):
    def __init__(self, client, name, override_tags=None):
        """
        A Gauge is a simple counter metric that emits a numeric value. It will almost always
        be used from Client.gauge(), but here's a short example of how to use one:

        >>> with Gauge(metrics_client, "free_mem") as g:
        >>>     free_mem_bytes = get_free_memory()
        >>>     g.value = free_mem_bytes
        >>>     g.dimensions = get_dimensions()

        :param client: A metrics client
        :param name: The name of the metric to be emitted
        :param override_tags: Optional dictionary of metadata to override the default metadata
        """
        self.client = client
        self.name = name
        self._value = 1
        self._dimensions = None
        self.override_tags = override_tags

    def __enter__(self):
        self.client.enter_scope(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.submit()
        self.client.leave_scope()

    @property
    def value(self):
        """
        Get the value of the gauge
        :return: The current value of the Gauge
        """
        return self._value

    @value.setter
    def value(self, v):
        """
        Set the value of the Gauge
        :param v: The new value
        :return: None
        """
        self._value = v

    @property
    def dimensions(self):
        """
        Get the dimensions for the gauge
        :return: The current dimensions of the Gauge
        """
        return self._dimensions

    @dimensions.setter
    def dimensions(self, d):
        """
        Set the dimensions for the Gauge
        :param d: dimensions
        :return: None
        """
        self._dimensions = d

    def submit(self):
        """
        Submit the result to the metric client
        :return: None -- side-effect is to submit the metric to the client.
        """
        self.client.submit(GaugeMetric(self.metric_name, self.value, override_tags=self.override_tags), self.dimensions)
