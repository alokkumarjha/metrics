class LogFormatter(object):
    def format(self, metric):
        """
        This simply returns the metric as a dictionary.
        :param metric: The Metric to format
        :return: dict
        """
        if isinstance(metric, list):
            return [self._format_single_metric(m) for m in metric]
        return [self._format_single_metric(metric)]

    def _format_single_metric(self, metric):
        return {
            "name": metric.name,
            "datapoints": [metric.to_dict()]
        }
