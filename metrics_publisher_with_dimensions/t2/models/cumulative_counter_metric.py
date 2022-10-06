from .metric import Metric


class CumulativeCounterMetric(Metric):
    def __init__(self, name, value, timestamp=None, override_tags=None):
        super(CumulativeCounterMetric, self).__init__(name, value, timestamp, override_tags=override_tags)
