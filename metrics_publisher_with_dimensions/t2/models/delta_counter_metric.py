from .unit_of_work_metric import UnitsOfWorkMetric


class DeltaCounterMetric(UnitsOfWorkMetric):
    def __init__(self, name, value, timestamp=None, units_of_work=1, override_tags=None):
        super(DeltaCounterMetric, self).__init__(
            name,
            value,
            timestamp=timestamp,
            units_of_work=units_of_work,
            override_tags=override_tags)
