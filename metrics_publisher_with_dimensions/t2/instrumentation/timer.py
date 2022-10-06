import contextdecorator

from t2.models import TimerMetric
from .mixins import MonotonicTimerMixin, UnitOfWorkMixin


class _Timer(contextdecorator.ContextDecorator, MonotonicTimerMixin, UnitOfWorkMixin):
    def __init__(self, client, name, units_of_work=1, override_tags=None):
        """
        A Timer is used to time events. It returns a non-typed metric, which
        can be thought of as a simple Gauge whose units are in milliseconds.
        This class may be used as either a context manager or as a decorator;
        see https://confluence.oci.oraclecorp.com/display/Telemetry/Python+Metrics+Library
        for details.
        :param client: A metrics Client must be injected into a Timer instance.
        :param name: The name of the metric that this Timer will produce.
        :param override_tags: Optional dictionary of metadata/tags to override the default metadata
        """
        self.client = client
        self.name = name
        self._units_of_work = units_of_work
        self.override_tags = override_tags

    def __enter__(self):
        self.client.enter_scope(self.name)
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.submit()
        self.client.leave_scope()

    def submit(self, units_of_work=None):
        uow = units_of_work or self.units_of_work
        self.client.submit(TimerMetric(self.metric_name, self.elapsed_ms, units_of_work=uow,
                                       override_tags=self.override_tags))
