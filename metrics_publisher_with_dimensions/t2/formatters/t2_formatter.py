import datetime

from .. import models

import logging

logger = logging.getLogger(__name__)


class T2Formatter(object):
    epoch = datetime.datetime.utcfromtimestamp(0)

    def format(self, metric_or_metrics, default_metadata=None):
        """
        This will format a list of metric payloads suitable for
        JSON-serialization. Different emitters will need their formatters
        to format metrics differently.

        T2 does not allow a single transaction to contain multiple metrics with different
        metadata. If a list of metrics is provided, then they will be grouped by like metadata
        and a payload generate for each unique set of metadata.

        If there are multiple metrics that share the same metadata, then they will be grouped
        into a single payload such as:
        [
            {"project": "project_name"
             "fleet": "fleet_name",
             "hostname": "host_name",
             "availabilityDomain": "ad_name",
             "metrics": [
                {"name": "first_metric",
                 "datapoints": [{"timestamp": 5, "value": 1.0}, {"timestamp": 10, "value": 7.5}]}
                {"name": "second_metric",
                 "datapoints": [{"timestamp": 7, "value": 2.2}, {"timestamp": 20, "value": 80}]}
                 ... etc
             ]}
         ]

         In the case of a single metric, the "metrics" list above will have only one entry.

        :param metric_or_metrics:  The metric or metrics to format
        :param default_metadata: The metric metadata common to all metrics being sent. Metadata attached
            to a metric will override any of the default_metadata values.
        :return: List of payloads ready for serialization to the T2 service
        """
        indexed_metric_payloads = {}
        # If we get a single metric, make it a list with one element
        if not isinstance(metric_or_metrics, list):
            metrics = [metric_or_metrics]
        else:
            metrics = metric_or_metrics

        for metric in metrics:
            payload_metadata = default_metadata.copy_with(metric.override_tags)

            if payload_metadata not in indexed_metric_payloads:
                payload = models.Payload(payload_metadata)
                indexed_metric_payloads[payload_metadata] = payload

            indexed_metric_payloads[payload_metadata].add_metric(metric)

        return self.serialize_payloads(indexed_metric_payloads.values())

    def serialize_payloads(self, metric_payloads):
        all_serialized_payloads = []
        for payload in metric_payloads:
            payload_body = payload.metadata.to_dict()

            for metric_type in payload.metrics.keys():
                payload_body[metric_type] = []
                for metric_name in payload.metrics[metric_type].keys():
                    datapoints = []
                    for metric in payload.metrics[metric_type][metric_name]:
                        datapoints.append(self._format_single_metric(metric))
                    payload_body[metric_type].append({'name': metric_name, 'series': datapoints})

            all_serialized_payloads.append(payload_body)

        return all_serialized_payloads

    def _format_single_metric(self, metric):
        dispatch_table = {
            models.TimerMetric: self._format_single_uow_metric,
            models.DeltaCounterMetric: self._format_single_uow_metric,

            models.GaugeMetric: self._format_single_raw_metric,
            models.CumulativeCounterMetric: self._format_single_raw_metric,
            models.Metric: self._format_single_raw_metric,
        }

        f = dispatch_table.get(type(metric))
        if f is None:
            return None

        return self._format_series_metric(metric)

    def _format_series_metric(self, metric):
        return {'second': metric.timestamp, 'values': [{'value': metric.value, 'count': 1}]}

    def _format_single_raw_metric(self, metric):
        return {
                    "timestamp": self._get_t2_timestamp(metric.timestamp),
                    "value": metric.value,
               }

    def _format_single_uow_metric(self, metric):
        return {
                    "timestamp": self._get_t2_timestamp(metric.timestamp),
                    "value": metric.value,
                    "uowCount": metric.units_of_work,
               }

    def _get_t2_timestamp(self, timestamp):
        return (timestamp - self.epoch).total_seconds() * 1000  # timestamps are in ms, monotonic() returns ns
