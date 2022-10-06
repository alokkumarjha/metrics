import logging
import datetime

from . import metric
from . import gauge_metric
from . import timer_metric
from . import delta_counter_metric
from . import cumulative_counter_metric

logger = logging.getLogger(__name__)

MODELS_TO_JSON_KEY_MAP = {
    metric.Metric: 'metrics',
    gauge_metric.GaugeMetric: 'gauges',
    timer_metric.TimerMetric: 'timers',
    delta_counter_metric.DeltaCounterMetric: 'deltaCounters',
    cumulative_counter_metric.CumulativeCounterMetric: 'cumulativeCounters',
}

epoch = datetime.datetime.utcfromtimestamp(0)


class Payload(object):
    def __init__(self, metadata):
        self.metadata = metadata
        self.metrics = {}

    def add_metric(self, new_metric):
        metric_type_key = MODELS_TO_JSON_KEY_MAP.get(type(new_metric))

        if metric_type_key is None:
            logger.warning("Cannot add a metric type of '{}'".format(type(new_metric)))
            return

        if metric_type_key not in self.metrics.keys():
            self.metrics[metric_type_key] = {}

        if new_metric.name not in self.metrics[metric_type_key].keys():
            self.metrics[metric_type_key][new_metric.name] = []

        self.metrics[metric_type_key][new_metric.name].append(new_metric)


class OverlayPayload(object):
    def __init__(self, metadata):
        self.metadata = metadata
        self.metrics = []

    def add_metric(self, new_metric):
        for m in self.metrics:
            if new_metric.name == m.name:
                m.add_metric_values(new_metric)
                return

        m = OverlayMetric(new_metric.name)
        m.add_metric_values(new_metric)
        self.metrics.append(m)


class OverlayMetric(object):
    def __init__(self, name):
        self.name = name
        self.series = []

    def add_metric_values(self, m):
        for s in self.series:
            if s.t2_timestamp == _format_t2_timestamp(m.timestamp):
                s.add_value(m.value)
                return

        new_series = Series(m.timestamp)
        new_series.add_value(m.value)
        self.series.append(new_series)


class Series(object):
    def __init__(self, timestamp):
        self.t2_timestamp = _format_t2_timestamp(timestamp)
        self.values = []

    def add_value(self, raw_value):
        for value in self.values:
            if value.value == raw_value:
                value.count += 1
                return

        self.values.append(Value(1, raw_value))


class Value(object):
    def __init__(self, count, value):
        self.count = count
        self.value = value


def _format_t2_timestamp(timestamp):
    return int((timestamp - epoch).total_seconds() * 1000 + .5)  # timestamps are in ms, monotonic() returns ns
