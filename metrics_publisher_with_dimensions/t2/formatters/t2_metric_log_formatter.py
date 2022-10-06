import logging
import json
import datetime

logger = logging.getLogger(__name__)


class T2MetricLogFormatter(object):
    epoch = datetime.datetime.utcfromtimestamp(0)

    def format(self, metric):
        """
        Formats a metric for writing to the metric log
        Args:
            metric: t2.models.metric.Metric

        Returns: a single log line formatted as a json string
        """
        return json.dumps({
            "name": metric.name,
            "metricType": metric.metric_type,
            "series":
                [
                    {
                        "second": self._get_t2_timestamp(metric.timestamp),
                        "values": [{"value": metric.value, "count": 1}]
                    }

                ]
        }, sort_keys=True)

    def _get_t2_timestamp(self, timestamp):
        return (timestamp - self.epoch).total_seconds() * 1000
