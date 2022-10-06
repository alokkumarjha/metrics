import oci
import logging
import os
import json
import socket

from .t2 import client

DESKTOP_REGION = "desktop"
DESKTOP_AD = "dev-1"
DESKTOP_ODO_APP_ID = "nm-erm-commons"

HOSTNAME = "hostname"
PROJECT = "project"
FLEET = "fleet"
END_POINT_OVERRIDE = "endpointOverride"
CA_CERT_FILE = "caCertFile"
METRIC_LOG_TAP_CONFIG = "metricLogTapConfig"
CLIENT_TYPE = "clientType"
AD = "availabilityDomain"

METRICS_CONFIG = "metricsConfig"
T2_CONFIG = "t2Config"

OVERLAY_CLIENT = "OVERLAY_CLIENT"
DESKTOP_CLIENT = "DESKTOP_CLIENT"
SYNCHRONOUS_CONFIG_KEY_NAME = "synchronous"

logger = logging.getLogger(__name__)


class MetricsPublisherWithDimensions(object):
    """
    This class is intended to create a client for T2
    The client is intended to be a singleton and will be initialized at the service startup
    To avoid specifying different service configurations for different region, all the requisite parameters are defined
    as dictionaries in one global config file. The dictionaries are indexed by the specific deployment's region or ODO
    app name to get the appropriate values
    """
    client = None

    def __init__(self, config, desktop_odo_app_id=DESKTOP_ODO_APP_ID, region_file="/etc/region"):
        """
        Singleton constructor
        """
        if MetricsPublisherWithDimensions.client is not None:
            return

        self._region_file = region_file
        self._config = config
        self._region = None
        self._client_type = None
        self._odo_app_id = None
        self._client_config = None
        self._desktop_odo_app_id = desktop_odo_app_id
        MetricsPublisherWithDimensions.client = self._init()

    @staticmethod
    def close():
        if MetricsPublisherWithDimensions.client is not None:
            MetricsPublisherWithDimensions.client.close()

    def region(self):
        return self._region

    def odo_app_id(self):
        return self._odo_app_id

    def client_type(self):
        return self._client_type

    def client_config(self):
        return self._client_config

    def _init(self):
        self._region = self._get_region()
        self._odo_app_id = self._get_odo_application_id()
        logger.debug("Region : {} , ODO_APP_ID : {}".format(self._region, self._odo_app_id))

        self._client_config = self._make_config()
        logger.debug("metrics publisher config is {}".format(self._client_config))

        logger.info("Initializing MetricsPublisherWithDimensions client for region {} ODO_APP_ID {} of "
                    "type {} with config {}".format(self._region, self._odo_app_id, self._client_type,
                                                    self._client_config))
        if self._client_type == OVERLAY_CLIENT:
            auth_provider = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            return client.OverlayClient(self._client_config, authentication_provider=auth_provider)
        else:
            return client.Client(self._client_config)

    def _get_region(self):
        """
        Reads the value of the region from the "/etc/region" file
        Returns DESKTOP_REGION if this file is not present
        """
        if os.path.exists(self._region_file):
            with open(self._region_file, "r") as file:
                return file.readline().rstrip()
        return DESKTOP_REGION

    def _get_odo_application_id(self):
        """
        Reads the environment variable ODO_APPLICATION_ID and retuns it
        If the environment variable is not set, returns DESKTOP_ODO_APP_ID
        :return:
        """
        return os.environ.get('ODO_APPLICATION_ID', self._desktop_odo_app_id)

    def _make_config(self):
        """
        Creates a dictionary with configuration parameters for creating the T2 client
        If any of the parameters or files are not present an exception will be raised and will
        stop the startup of the service
        """

        with open(self._config, "r") as f:
            params = json.load(f)

        client_config = {
            METRICS_CONFIG: {
                PROJECT: params.get(PROJECT),
                T2_CONFIG: {
                    FLEET: params.get(FLEET).get(self._odo_app_id)
                },
                SYNCHRONOUS_CONFIG_KEY_NAME: True
            }
        }

        self._client_type = params.get(CLIENT_TYPE).get(self._odo_app_id)
        if self._client_type == OVERLAY_CLIENT:
            client_config[METRICS_CONFIG][T2_CONFIG][END_POINT_OVERRIDE] = params.get(END_POINT_OVERRIDE).get(
                self._region)
            client_config[METRICS_CONFIG][T2_CONFIG][CA_CERT_FILE] = params.get(CA_CERT_FILE)
            client_config[METRICS_CONFIG][HOSTNAME] = socket.gethostname() + "." + self._get_region()
        else:  # Desktop client
            client_config[METRICS_CONFIG][T2_CONFIG][METRIC_LOG_TAP_CONFIG] = {
                "logDirectory": params.get(METRIC_LOG_TAP_CONFIG)}
            client_config[METRICS_CONFIG][AD] = DESKTOP_AD

        return client_config
