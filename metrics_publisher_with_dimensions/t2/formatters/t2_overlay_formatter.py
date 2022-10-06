from .. import models

import logging

logger = logging.getLogger(__name__)


class T2OverlayFormatter(object):
    def format(self, metric_or_metrics, default_metadata=None):
        """
        Formatter for Overlay metrics.

        E.g.:

        {
            "project": "t2-test",
            "fleet": "telemetry-beet",
            "hostname": "horus-api-beta-ocicorp-01001.ad1.us-ashburn-1.oraclevcn.com",
            "region": "phx"
            "availabilityDomain": "phx-ad-2",
            "metrics": [
                {
                    "name": "DianogaBeetInstancePrincipal",
                    "series": [
                        {
                            "second": 1557847566,
                            "values": [
                                {
                                    "count": 1,
                                    "value": 10.0
                                },
                                {
                                    "count": 5,
                                    "value": 12.1
                                }
                            ]
                        }
                    ]
                }
            ],
        }

        :param metric_or_metrics:  The metric or metrics to format
        :param default_metadata: The metric metadata common to all metrics being sent. Metadata attached
            to a metric will override any of the default_metadata values.
        :return: List of payloads ready for serialization to the T2 service
        """
        metrics_by_metadata = {}

        # If we get a single metric, make it a list with one element
        if not isinstance(metric_or_metrics, list):
            metrics = [metric_or_metrics]
        else:
            metrics = metric_or_metrics

        for metric in metrics:
            payload_metadata = default_metadata.copy_with(metric.override_tags, include_region=True)

            if payload_metadata not in metrics_by_metadata:
                payload = models.OverlayPayload(payload_metadata)
                metrics_by_metadata[payload_metadata] = payload

            metrics_by_metadata[payload_metadata].add_metric(metric)

        return self.serialize_payloads(metrics_by_metadata.values())

    def serialize_payloads(self, metric_payloads):
        all_serialized_payloads = []
        for payload in metric_payloads:
            payload_body = payload.metadata.to_dict(include_region=True)
            payload_body["metrics"] = self.serialize_payload(payload)

            all_serialized_payloads.append(payload_body)

        return all_serialized_payloads

    def serialize_payload(self, payload):
        return [self.serialize_overlay_metric(m) for m in payload.metrics]

    def serialize_overlay_metric(self, metric):
        return {
            "name": metric.name,
            "series": [self.serialize_series(s) for s in metric.series]
        }

    def serialize_series(self, series):
        return {
            "second": series.t2_timestamp,
            "values": [self.serialize_value(v) for v in series.values]
        }

    def serialize_value(self, value):
        return {
            "count": value.count,
            "value": value.value
        }
