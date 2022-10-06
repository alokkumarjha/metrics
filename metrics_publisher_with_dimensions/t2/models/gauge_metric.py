from .metric import Metric


class GaugeMetric(Metric):
    def __init__(self, name, value, timestamp=None, override_tags=None):
        super(GaugeMetric, self).__init__(name, value, timestamp, override_tags=override_tags)
