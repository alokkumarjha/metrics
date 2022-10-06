import contextdecorator

from ..models.delta_counter_metric import DeltaCounterMetric
from .mixins import UnitOfWorkMixin


class DeltaCounter(contextdecorator.ContextDecorator, UnitOfWorkMixin):
    def __init__(self, client, name, units_of_work=0, override_tags=None):
        """
        A Delta counter keeps track of count, as well as units of work. This is an appropriate metric type
        for success/error counts, files/rows processed, etc. If you want to increment the units of work but not the
        result count, you can increment the counter by 0. This class will almost always be used by calling
        Client.delta_counter(), but here's a short example:

        >>> d = DeltaCounter(metrics_client, "transaction_success_rate")
        >>> rows = db.get_all_recent_transactions()
        >>> for row in rows:
        >>>     if row.success:
        >>>         d.increment(1)  # 1 is the default, we could have written d.increment()
        >>>     else:
        >>>         d.increment(0)
        >>> d.submit()

        For more information, see:
        https://confluence.oci.oraclecorp.com/display/Telemetry/Java+Metrics+Library#JavaMetricsLibrary-DeltaCounter
        :param client: A Metrics Client
        :param name: The name of the metric to submit
        :param units_of_work: If you want to instantiate this counter at >0 units of work
        :param override_tags: Optional dictionary of metadata to override the default metadata
        """
        self.client = client
        self.name = name
        self._value = 0
        self._units_of_work = units_of_work
        self.override_tags = override_tags

    def __enter__(self):
        self.client.enter_scope(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.submit()
        self.client.leave_scope()

    def increment(self, v=1):
        """
        Increment the counter by a value. This will also increment units of work by 1.
        :param v: The value by which to increment (default 1)
        :return: None
        """
        self._value += v
        self.units_of_work += 1

    def submit(self, units_of_work=None):
        """
        Submit the metric from this counter
        :param units_of_work: And alternate value to submit for units of work
        :return: None -- side-effect is to submit the metric to the client.
        """
        uow = units_of_work or self.units_of_work
        self.client.submit(DeltaCounterMetric(self.metric_name, self._value, units_of_work=uow,
                                              override_tags=self.override_tags))
