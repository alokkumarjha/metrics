from datetime import datetime
import json
import hashlib

REGION_KEY = 'region'
AVAILABILTY_DOMAIN_KEY = 'availabilityDomain'
PROJECT_KEY = 'project'
FLEET_KEY = 'fleet'
HOSTNAME_KEY = 'hostname'


class MetricMetadata(object):

    def __init__(self, project, fleet=None, hostname=None, availabilityDomain=None, region=None):
        """
        MetricMetadata is data about the metric that's not the name or value.
        This metadata is used by the T2 system.

        :param project: The name of the project the metric belongs to
        :param fleet: The name of the fleet this metric belongs to
        :param hostname: The hostname that emitted this metric
        :param availabilityDomain: The availability domain for this metric
        """
        self.project = project
        self.fleet = fleet
        self.hostname = hostname
        self.availabilityDomain = availabilityDomain
        self.region = region

    def to_dict(self, include_region=False):
        d = {
            AVAILABILTY_DOMAIN_KEY: self.availabilityDomain,
            PROJECT_KEY: self.project,
            FLEET_KEY: self.fleet,
            HOSTNAME_KEY: self.hostname,
        }

        if include_region:
            d[REGION_KEY] = self.region

        return d

    def copy_with(self, override_tags, include_region=False):
        if override_tags is None:
            override_tags = {}
        new_metadata = self.to_dict(include_region=include_region)
        new_metadata.update(override_tags)
        return MetricMetadata(**new_metadata)

    @property
    def json_string(self):
        return json.dumps(self.to_dict(), sort_keys=True)

    @property
    def md5_hash(self):
        return hashlib.md5(self.json_string.encode('utf-8')).hexdigest()

    def __hash__(self):
        return hash(tuple((k, self.to_dict()[k]) for k in sorted(self.to_dict())))

    def __eq__(self, other):
        return type(self) == type(other) and self.__hash__() == other.__hash__()


class Metric(object):
    def __init__(self, name, value, timestamp=None, override_tags=None):
        """
        A metric is a single data point. A metric has a name and a value
        (and a timestamp representing when it was created)

        :param name: The name of this metric
        :param value: The value of this metric.
        :param timestamp: When this metric was created. Defaults to utcnow()
        :param override_tags: Optional dictionary of tags to override the default metadata
        """
        self.name = name
        self.value = value
        self.timestamp = timestamp or datetime.utcnow()
        self.override_tags = override_tags
        self.metric_type = "gauge"

    def to_dict(self):
        return {
            "value": self.value,
            "timestamp": self.timestamp,
        }
