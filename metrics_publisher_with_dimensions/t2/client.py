import logging
import os
import socket
import threading
from collections import defaultdict

import telemetry_endpoint_provider
from pic.environment import environment
from pyhocon import ConfigFactory

from .emitters.t2_emitter import T2Emitter
from .emitters.t2_metric_log_emitter import T2MetricLogEmitter
from .instrumentation.cumulative_counter import CumulativeCounter
from .instrumentation.delta_counter import DeltaCounter
from .instrumentation.gauge import Gauge
from .instrumentation.timer import _Timer
from .instrumentation.scope import Scope
from .models.metric import MetricMetadata
from .formatters.t2_overlay_formatter import T2OverlayFormatter

logger = logging.getLogger(__name__)

METRICS_CONFIG_KEY_NAME = "metricsConfig"
SYNCHRONOUS_CONFIG_KEY_NAME = "synchronous"
T2_CONFIG_KEY_NAME = "t2Config"
MTLS_CLIENT_CERT_CONFIG_KEY_NAME = "mtlsClientCertFile"
MTLS_CLIENT_KEY_CONFIG_KEY_NAME = "mtlsClientKeyFile"
CA_CERT_CONFIG_KEY_NAME = "caCertFile"

REGION_KEY_NAME = "region"
PROJECT_KEY_NAME = "project"
DESIRED_BATCH_SIZE_NAME = "desiredBatchSize"
DEFAULT_BATCH_SIZE = 100
MAX_METRICS_TO_BUFFER_NAME = "maxMetricsToBuffer"
DEFAULT_MAX_BUFFER_SIZE = 10000
MAX_BUFFER_TIME_MS_NAME = "maxBufferTimeMillis"
DEFAULT_MAX_BUFFER_TIME = 10000  # 10 seconds
MAX_JITTER_MS_NAME = "maxJitterMillis"
DEFAULT_JITTER_TIME = 1000  # 1 second

FLEET_KEY_NAME = "fleet"
METRIC_LOG_TAP_CONFIG_KEY_NAME = "metricLogTapConfig"
HOSTNAME_KEY_NAME = "hostname"
AVAILABILITY_DOMAIN_KEY_NAME = "availabilityDomain"
ENDPOINT_OVERRIDE_KEY_NAME = 'endpointOverride'
LOG_DIR_KEY = 'logDirectory'

AVAILABILITY_DOMAIN_VARIABLE = "AVAILABILITY_DOMAIN"
REGION_VARIABLE = "REGION"


class Client(object):
    def __init__(self, config_file_or_dict, authentication_provider=None, formatter=None):
        """
        A t2.Client is a way to get metrics into T2 from your Python code.
        It provides a Timer interface, which may be used as a context manager or
        a decorator. This client is thread-safe.

        :param config_file: The path to a typesafe-compatible config file used to
                 configure the behavior of the client. See the documentation at
                 https://confluence.oci.oraclecorp.com/display/Telemetry/Python+Metrics+Library
                 for more details.
        """
        if isinstance(config_file_or_dict, dict):
            logger.info("Loading config from dictionary")
            typesafe_config = ConfigFactory.from_dict(config_file_or_dict)
        else:
            logger.info("Loading config from file: {}".format(config_file_or_dict))
            typesafe_config = ConfigFactory.parse_file(config_file_or_dict)

        self.metrics_config = typesafe_config.get(METRICS_CONFIG_KEY_NAME)

        self._scope = defaultdict(list)
        self.emitters = []

        self.project = self.metrics_config.get(PROJECT_KEY_NAME)
        self.fleet = None

        logger.debug(self.metrics_config)
        self.region = self.metrics_config.get(REGION_KEY_NAME, default=self._resolve_region())
        self.availabilityDomain = self.metrics_config.get(AVAILABILITY_DOMAIN_KEY_NAME, default=self._resolve_ad())
        try:
            self.hostname = self.metrics_config.get(HOSTNAME_KEY_NAME, socket.gethostname())
        except Exception as e:
            logger.warning("Could not get hostname")
            logger.warning(e)
            self.hostname = None

        t2_config = self.metrics_config.get(T2_CONFIG_KEY_NAME, None)
        if t2_config:
            self.fleet = t2_config.get(FLEET_KEY_NAME)
            if METRIC_LOG_TAP_CONFIG_KEY_NAME in t2_config.keys():
                logdir = t2_config[METRIC_LOG_TAP_CONFIG_KEY_NAME][LOG_DIR_KEY]
                self.add_emitter(
                    T2MetricLogEmitter(
                        region=self.region,
                        availabilityDomain=self.availabilityDomain,
                        project=self.project,
                        fleet=self.fleet,
                        hostname=self.hostname,
                        logdir=logdir
                    )
                )
            else:
                self.add_emitter(
                    T2Emitter(
                        self.metric_metadata,
                        endpoint=self.get_t2_endpoint(t2_config),
                        synchronous=self.metrics_config.get(SYNCHRONOUS_CONFIG_KEY_NAME, False),
                        max_pending_metrics=self.metrics_config.get(DESIRED_BATCH_SIZE_NAME, DEFAULT_BATCH_SIZE),
                        queue_size=self.metrics_config.get(MAX_METRICS_TO_BUFFER_NAME, DEFAULT_MAX_BUFFER_TIME),
                        max_wait_time=self.metrics_config.get(MAX_BUFFER_TIME_MS_NAME, DEFAULT_MAX_BUFFER_SIZE),
                        jitter=self.metrics_config.get(MAX_JITTER_MS_NAME, DEFAULT_JITTER_TIME),
                        mtls_client_cert_file=t2_config.get(MTLS_CLIENT_CERT_CONFIG_KEY_NAME, None),
                        mtls_client_key_file=t2_config.get(MTLS_CLIENT_KEY_CONFIG_KEY_NAME, None),
                        ca_cert_file=t2_config.get(CA_CERT_CONFIG_KEY_NAME, None),
                        authentication_provider=authentication_provider,
                        formatter=formatter
                    )
                )

    def get_t2_endpoint(self, t2_config):
        # Use the configured endpoint if there is one, otherwise use the endpoint provider
        endpoint = t2_config.get(ENDPOINT_OVERRIDE_KEY_NAME, None)
        if endpoint is not None:
            logger.info("Using override T2 endpoint from config: {}".format(endpoint))
        else:
            endpoint = telemetry_endpoint_provider.get_t2_endpoint()
            logger.info("Using T2 endpoint provider endpoint: {}".format(endpoint))

        return endpoint

    # see https://docs.python.org/2/library/threading.html#threading.Thread.ident
    # (and then https://docs.python.org/2/library/thread.html#thread.get_ident)
    def enter_scope(self, scope_name):
        self._scope[threading.current_thread().ident].append(scope_name)

    def leave_scope(self):
        thread_id = threading.current_thread().ident
        self._scope[thread_id].pop()
        # Clean up after ourselves; no telling how big this dictionary will get.
        if len(self._scope[thread_id]) == 0:
            del self._scope[thread_id]

    def get_scoped_metric_name(self):
        return ".".join(self._scope[threading.current_thread().ident])

    @property
    def metric_metadata(self):
        return MetricMetadata(self.project, fleet=self.fleet, hostname=self.hostname,
                              availabilityDomain=self.availabilityDomain, region=self.region)

    def add_emitter(self, emitter):
        self.emitters.append(emitter)

    def close(self):
        for emitter in self.emitters:
            emitter.close()

    def submit(self, metric_or_metrics, dimensions=None):
        """
        Submit given metric(s) to all emitters
        :param metric_or_metrics: A metric (or metrics) to emit
        :return: None
        """
        for emitter in self.emitters:
            emitter.emit(metric_or_metrics, dimensions)

    def time(self, name, override_tags=None):
        """
        Client.time() will let you time how long something takes.

        :param name: The name of the metric to time
        :param override_tags: Optional dictionary of metadata to override the default metadata
        :return: a _Timer instance that can be used as a decorator or context manager
        """
        return _Timer(self, name, override_tags=override_tags)

    def scope(self, name, override_tags=None):
        """
        Client.metric_scope() will let you submit multiple metrics from same scope (including auto time and fault)

        :param name: The name of the scope
        :param override_tags: Optional dictionary of metadata to override the default metadata
        :return: a MetricScope instance that can be used as a decorator or context manager
        """
        return Scope(self, name, override_tags=override_tags)

    def delta_counter(self, name, override_tags=None):
        """
        Client.delta_counter() will let you send a delta counter metric.

        :param name: The name of the metric
        :param override_tags: Optional dictionary of metadata to override the default metadata
        :return: a Delta Counter
        """
        return DeltaCounter(self, name, override_tags=override_tags)

    def cumulative_counter(self, name, override_tags=None):
        """
        Client.cumulative_counter() will let you send a cumulative counter metric.

        :param name: The name of the metric
        :param override_tags: Optional dictionary of metadata to override the default metadata
        :return: a Cumulative Counter
        """
        return CumulativeCounter(self, name, override_tags=override_tags)

    def gauge(self, name, override_tags=None):  # pragma: no cover
        """
        Client.gauge() will let you send a simple Gauge metric.

        :param name: The name of the metric
        :param override_tags: Optional dictionary of metadata to override the default metadata
        :return: a Gauge instance that can be used as a decorator or context manager.
        """
        return Gauge(self, name, override_tags=override_tags)

    def _resolve_region(self):
        if REGION_VARIABLE in os.environ.keys():
            return os.getenv(REGION_VARIABLE)
        else:
            try:
                return environment.get_region()
            except environment.RegionNotFoundException:
                return None

    def _resolve_ad(self):
        if AVAILABILITY_DOMAIN_VARIABLE in os.environ.keys():
            return os.getenv(AVAILABILITY_DOMAIN_VARIABLE)
        else:
            try:
                return environment.get_ad()
            except environment.AvailabilityDomainNotFoundException:
                return None


class OverlayClient(Client):
    def __init__(self, config_file_or_dict, authentication_provider):
        """
        A T2 Client for Overlay customers.

        E.g.:

        import oci
        from t2 import client

        auth_provider = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        metrics = client.OverlayClient("/path/to/typesafe/config/file.conf", authentication_provider=auth_provider)

        :param config_file_or_dirct:
        :param authentication_provider:
        """
        super(OverlayClient, self).__init__(
            config_file_or_dict,
            authentication_provider=authentication_provider,
            formatter=T2OverlayFormatter()
        )
