import logging
import os

from logging.handlers import TimedRotatingFileHandler
from ..models.metric import MetricMetadata
from .log_emitter import LogEmitter
from ..formatters import T2MetricLogFormatter

log = logging.getLogger(__name__)

METRIC_LOGGER_PREFIX = "Metric-Logger"
METADATA_FILENAME_PREFIX = "metric-log-tap"
METRIC_LOG_FILE_PREFIX = "Metrics_v1.0"

METRIC_LOG_LEVEL = 100


class T2MetricLogEmitter(LogEmitter):
    def __init__(self, region, availabilityDomain, project, fleet, hostname, logdir):
        self.default_metadata = MetricMetadata(region=region, availabilityDomain=availabilityDomain, project=project,
                                               fleet=fleet, hostname=hostname)
        super(T2MetricLogEmitter, self).__init__(self.default_metadata)
        self.logdir = logdir
        self.formatter = T2MetricLogFormatter()

    def emit(self, metric_or_metrics, dimensions=None):
        if isinstance(metric_or_metrics, list):
            metrics = metric_or_metrics
        else:
            metrics = [metric_or_metrics]

        for metric in metrics:
            metric_metadata = self.default_metadata.copy_with(metric.override_tags)

            # Create the logger if it doesn't exist
            if self._logger_name_for_metric(metric_metadata) not in logging.Logger.manager.loggerDict:
                self.create_metric_logger(metric_metadata)

                # If we created a new logger, we also need to create the metadata file
                # if it doesn't already exist
                if not os.path.exists(os.path.join(self.logdir, self._filename_for_metadata(metric_metadata))):
                    self.create_metadata_file(metric_metadata)

            metric_logger = logging.getLogger(self._logger_name_for_metric(metric_metadata))
            metric_logger.log(METRIC_LOG_LEVEL, self.format(metric))

    def create_metadata_file(self, metric_metadata):
        with open(os.path.join(self.logdir, self._filename_for_metadata(metric_metadata)), "w") as metadata_fp:
            metadata_fp.write(metric_metadata.json_string)

    def create_metric_logger(self, metric_metadata):
        metric_logger = logging.getLogger(self._logger_name_for_metric(metric_metadata))
        metric_logger.propagate = False
        metric_logger.setLevel(METRIC_LOG_LEVEL)

        rolling_handler = TimedRotatingFileHandler(
            filename=os.path.join(self.logdir, self._filename_for_metric_log(metric_metadata)),
            when="h")
        log.debug("Metrics logging to {}".format(rolling_handler.baseFilename))
        formatter = logging.Formatter('%(message)s')
        rolling_handler.setFormatter(formatter)

        metric_logger.addHandler(rolling_handler)

    def _filename_for_metadata(self, metadata):
        return "{}-{}.metadata".format(METADATA_FILENAME_PREFIX, metadata.md5_hash)

    def _filename_for_metric_log(self, metadata):
        return "{}-{}.log".format(METRIC_LOG_FILE_PREFIX, metadata.md5_hash)

    def _logger_name_for_metric(self, metadata):
        return "{}-{}".format(METRIC_LOGGER_PREFIX, metadata.md5_hash)
