"""Lanes until the lane scheduler takes over their code: the facade still holds `lane_next` and `dispatch`;
this gives that code the scheduler protocol and the lane flavour of the end of run."""

from feature_flow.conductor.schedulers.serial import SerialScheduler


class FacadeLanes(SerialScheduler):
    lanes = True

    def next(self, lane=None):
        return self.c.lane_next(lane)

    def on_passed(self, ws):
        """The ticket is counted once its merge lands; None tells lane_next to merge it."""
        ws.st["phase"] = "merge"
        ws.save()
        return None

    def resume(self):
        return self.c.dispatch()
