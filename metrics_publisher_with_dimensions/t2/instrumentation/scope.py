from t2.models import Metric

import contextdecorator

from t2.models import TimerMetric
from .mixins import MonotonicTimerMixin, UnitOfWorkMixin


class Scope(contextdecorator.ContextDecorator, MonotonicTimerMixin, UnitOfWorkMixin):
    def __init__(self, client, name, units_of_work=1, override_tags=None):
        """
        This scope creates .Time and .Fault metrics.  It is based on:
        https://bitbucket.oci.oraclecorp.com/projects/TEL/repos/metrics-lib/browse/src/main/java/com/oracle/pic/telemetry/commons/metrics/Scope.java

        :param client: A metrics Client must be injected into a MetricsScope instance.
        :param name: The name of the scope prefix this metric will produce.
        :param override_tags: Optional dictionary of metadata/tags to override the default metadata
        """
        self.client = client
        self.name = name
        self._units_of_work = units_of_work
        self.override_tags = override_tags
        self.successful = False

    def __enter__(self):
        self.client.enter_scope(self.name)
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.submit()
        self.client.leave_scope()

    def record_success(self):
        self.successful = True

    def submit(self, units_of_work=None):
        uow = units_of_work or self.units_of_work
        self.client.submit(TimerMetric(self.metric_name + ".Time", self.elapsed_ms, units_of_work=uow,
                                       override_tags=self.override_tags))
        self.client.submit(Metric(self.metric_name + ".Fault", (0.0 if self.successful else 1.0),
                                  override_tags=self.override_tags))
