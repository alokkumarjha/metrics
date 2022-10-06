import monotonic


class InstrumentationBase(object):
    @property
    def metric_name(self):
        return self.client.get_scoped_metric_name()


class UnitOfWorkMixin(InstrumentationBase):
    @property
    def units_of_work(self):
        return self._units_of_work

    @units_of_work.setter
    def units_of_work(self, uow):
        self._units_of_work = uow


class MonotonicTimerMixin(object):
    def start(self):
        self.elapsed_ms = 0
        self.start_time = monotonic.monotonic()

    def stop(self):
        self.elapsed_ms += (monotonic.monotonic() - self.start_time) * 1000
