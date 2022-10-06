try:  # pragma: nocover
    from Queue import Full, Empty
except ImportError:  # pragma: nocover
    # Python 3.5
    from queue import Full, Empty

import datetime
from uuid import uuid4
import os.path
import json
import logging
import multiprocessing
import random

import requests
from retrying import retry as backoff

from .base_emitter import BaseEmitter
from ..formatters import T2Formatter
from ..models import Metric

logger = logging.getLogger(__name__)

MINIMUM_QUEUE_WAIT_TIME = 3  # seconds


class T2Emitter(BaseEmitter):
    HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(
            self,
            metadata,
            endpoint=None,
            synchronous=False,
            retry=True,
            formatter=None,
            max_pending_metrics=100,
            queue_size=None,
            max_wait_time=500,
            jitter=1000,
            request_id=None,
            mtls_client_cert_file=None,
            mtls_client_key_file=None,
            flusher=None,
            authentication_provider=None,
            ca_cert_file=None):
        """

        :param metadata:
        :param request_id:
        """
        super(T2Emitter, self).__init__()
        self.retry = retry
        self._synchronous = synchronous
        self._jitter = jitter
        self.log = logging.getLogger(__name__)
        self.default_metadata = metadata
        self._endpoint = endpoint
        if self._endpoint is None:
            raise ValueError("You must provide a T2 endpoint")
        self.formatter = formatter or T2Formatter()
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)
        self._session.auth = authentication_provider
        self.request_id = request_id

        self._failed_metric_submissions = 0
        self.mtls_client_cert_file = mtls_client_cert_file
        self.mtls_client_key_file = mtls_client_key_file
        self.ca_cert_file = ca_cert_file

        if self.mtls_client_key_file and self.mtls_client_cert_file:
            if not (os.path.isfile(self.mtls_client_key_file) and os.path.isfile(self.mtls_client_cert_file)):
                raise ValueError("Both the certificate and key must be valid files!")
            self._session.cert = (self.mtls_client_cert_file, self.mtls_client_key_file)

        if self.ca_cert_file:
            self._session.verify = self.ca_cert_file

        if not self._synchronous:
            self.q_size_flush_threshold = max_pending_metrics
            self.q_age_flush_threshold = datetime.timedelta(milliseconds=max_wait_time)
            self.q = multiprocessing.Queue(
                maxsize=queue_size or self.q_size_flush_threshold * 10)  # Some breathing room
            self.last_flush = datetime.datetime.utcnow()
            self.condition = multiprocessing.Condition()
            # We allow a flusher to be passed in to help with unit testing.
            # Because of the multiprocess fork() call, mocking doesn't work right.
            self.flusher = flusher or self.flush
            self.watcher = multiprocessing.Process(target=self._watch_queue)
            self.watcher.daemon = True
            self.watcher.start()

    def _watch_queue(self):
        while True:
            self.log.debug("[watcher] Attempting to acquire lock")
            if self.condition.acquire(False):
                self.log.debug("[watcher] waiting %s to flush the queue", self._time_to_next_flush())
                self.condition.wait(self._time_to_next_flush())
                try:
                    self.log.debug("[watcher] Flushing the queue")
                    self.flusher()
                finally:
                    self.condition.release()
            else:
                self.log.debug("[watcher] I couldn't acquire the lock")

    def _generate_request_id(self):
        generated_id = self.default_metadata.project + "-" + uuid4().hex
        request_id = self.request_id or generated_id
        self.log.debug("Request id is %s", request_id)
        self._session.headers.update({"opc-request-id": request_id})

    def emit(self, metric_or_metrics, dimensions=None):
        """
        Emit a metric. The metric will either be recorded immediately or queued
        for later, based on whether we're running in synchronous mode or not.
        :param metric_or_metrics: The metric(s) to send
        :return: None
        """
        if self._synchronous:
            # Send the metric immediately.
            self.log.debug("Sending metric(s) synchronously: %s", metric_or_metrics)
            for payload in self.format(metric_or_metrics):
                if dimensions is not None:
                    payload['metrics'][0]['config'] = dimensions
                self._send_or_complain(payload)
            return

        self._emit_async(metric_or_metrics)

    def flush(self):
        """
        Flush the queue. This compiles all the metrics that are currently in the queue
        into a format appropriate for the wire, then sends them all.
        :return: None
        """
        self.log.debug("Current size of %s: %d", self.q, self.q.qsize())
        if self.q.empty():
            self.log.debug("Queue %s is empty!!!", self.q)
            self.last_flush = datetime.datetime.utcnow()
            return
        metrics = []
        maximum_metrics_to_send = self.q.qsize()
        # Attempt to retrieve up to the current length of the queue. It's okay if we get less. That just means some
        # other thread is also flushing and our batching is slightly less efficient.
        try:
            for _ in range(maximum_metrics_to_send):
                metric = self.q.get(False)
                self.log.debug("Grabbed metric %s from the queue", metric)
                metrics.append(metric)
        except Empty:
            self.log.debug("Concurrent flush in progress. Batched writes may not be optimally packed.")
        self.log.debug("%d metrics have been read from the queue", len(metrics))
        self.last_flush = datetime.datetime.utcnow()
        for payload in self.format(metrics):
            self._send_or_complain(payload)

    def format(self, metric_or_metrics):
        formatted_metrics = self.formatter.format(metric_or_metrics, default_metadata=self.default_metadata)
        self.log.debug("Formatted metrics are %s", formatted_metrics)
        return formatted_metrics

    def close(self):
        self.log.debug("Closing and flushing queue %s", self.q)
        if not self._synchronous:
            self.flusher()
            self.watcher.terminate()

    def send(self, payload):
        self._generate_request_id()
        self._submit_failed_attempts()
        if self.retry:
            return self._send_and_retry(payload)
        return self._send(payload)

    def _send(self, payload):
        # This code will change when we use a real swagger client
        self.log.debug("Sending %s to T2 (without retrying)", payload)
        resp = self._session.put(self._endpoint, data=json.dumps(payload))
        self.log.info("Received response from T2: %s - %s", resp.headers, resp.content)

    def _send_or_complain(self, payload):
        try:
            self.log.debug("Attempting to send payload")
            self.send(payload)
        except Exception as e:
            self.log.error("Encountered exception sending metrics!")
            self.log.exception(e)

    def _emit_async(self, metric_or_metrics):
        try:
            self.log.debug("Placing metric %s on queue %s", metric_or_metrics, self.q)
            self.q.put(metric_or_metrics, block=False)
            self.log.debug("Current queue size: %d", self.q.qsize())
        except Full:
            self._failed_metric_submissions += 1
            self.log.warning("Queue is full! Discarding metric!")
        finally:
            if self._queue_too_full() or self._queue_too_old():
                self.log.debug("Trying to notify queue watcher that it's time to empty the queue")
                if self.condition.acquire(False):
                    try:
                        self.log.debug("Acquired lock. Notifying queue watcher")
                        self.condition.notify_all()
                    finally:
                        self.condition.release()

    @backoff(
        stop_max_attempt_number=7,
        wait_exponential_multiplier=1000,
        wait_exponential_max=10000,
    )
    def _send_and_retry(self, payload):
        # This code will change when we use a real swagger client
        self.log.debug("Sending %s to T2 (and potentially retrying)", payload)
        resp = self._session.put(self._endpoint, data=json.dumps(payload))
        self.log.debug("Received response from T2: %s - %s", resp.headers, resp.content)

    def _submit_failed_attempts(self):
        if self._failed_metric_submissions == 0:
            return
        metric_name = self.default_metadata.project + "-failed-attempts"
        self.log.debug("Submitting %s failed attempts to T2...", self._failed_metric_submissions)
        self._send(self.format(
            Metric(metric_name, self._failed_metric_submissions)))
        self._failed_metric_submissions = 0

    def _queue_too_old(self):
        return datetime.datetime.utcnow() >= self._time_of_next_flush

    def _queue_too_full(self):
        return self.q.qsize() >= self.q_size_flush_threshold

    def _time_to_next_flush(self):
        wait_time = ((self.last_flush + self.q_age_flush_threshold) - datetime.datetime.utcnow()).total_seconds()
        self.log.debug("Last flush was %s, flush threshold is %s, current time is %s",
                       self.last_flush, self.q_age_flush_threshold, datetime.datetime.utcnow())
        return max(wait_time, MINIMUM_QUEUE_WAIT_TIME)

    @property
    def _time_of_next_flush(self):
        return (self.last_flush +
                datetime.timedelta(seconds=self.q_age_flush_threshold.total_seconds()) +
                datetime.timedelta(milliseconds=self.jitter))

    @property
    def jitter(self):
        """
        Get a random jitter amount, according to the jitter parameter passed at instantiation.
        :return: int
        """
        return random.randint(-1 * abs(self._jitter), abs(self._jitter))
