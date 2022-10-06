from .metric import Metric


class UnitsOfWorkMetric(Metric):
    def __init__(self, name, value, timestamp=None, units_of_work=1, override_tags=None):
        super(UnitsOfWorkMetric, self).__init__(
            name,
            value,
            timestamp=timestamp,
            override_tags=override_tags)
        self.units_of_work = units_of_work

    def to_dict(self):
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "uowCount": self.units_of_work,
        }
