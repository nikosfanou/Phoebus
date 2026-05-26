from collections import deque
import numpy as np

class PerformanceDegradationDetector:
    BASELINE_WINDOW_SIZE = SLIDING_WINDOW_SIZE = 10

    def __init__(self, total_deployments):
        self.baseline_window = deque(maxlen=self.BASELINE_WINDOW_SIZE)
        self.sliding_window = deque(maxlen=self.SLIDING_WINDOW_SIZE)
        self.count = 0
        self.total_deployments = total_deployments
        self.baseline_q3 = 0

    def update(self, value):
        self.count += 1

        # Fill baseline window
        if len(self.baseline_window) < self.BASELINE_WINDOW_SIZE:
            self.baseline_window.append(value)
            return False
        
        if self.baseline_q3 == 0:
            baseline = np.array(self.baseline_window)
            self.baseline_q3 = np.percentile(baseline, 75)

        # Fill sliding window
        self.sliding_window.append(value)
        if len(self.sliding_window) < self.SLIDING_WINDOW_SIZE:
            return False

        sliding = np.array(self.sliding_window)
        sliding_q1 = np.percentile(sliding, 25)

        # Decision rule (distribution shift)
        should_reboot = sliding_q1 > self.baseline_q3 # quadriles

        if should_reboot:
            self.sliding_window.clear()

        return should_reboot
    