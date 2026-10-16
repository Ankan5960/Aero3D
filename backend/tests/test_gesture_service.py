import threading
import time

from app.camera import CameraUnavailableError
from app.gesture_processor import GestureConfig, GestureProcessor
from app.gesture_service import GestureService
from tests.landmarks import obs


class FakeCamera:
    def __init__(self, fail_open=False):
        self.fail_open = fail_open
        self.opened = False
        self.released = False

    def open(self):
        if self.fail_open:
            raise CameraUnavailableError("nope")
        self.opened = True

    def read(self):
        time.sleep(0.001)
        return object()

    def release(self):
        self.released = True


class FakeTracker:
    def __init__(self, frames):
        self.frames = list(frames)
        self.closed = False

    def detect(self, frame, ts):
        return self.frames.pop(0) if self.frames else None

    def close(self):
        self.closed = True


def run_service(camera, tracker, wait=0.4, tune=None):
    msgs, lock = [], threading.Lock()

    def sink(m):
        with lock:
            msgs.append(m)

    svc = GestureService(
        sink=sink,
        camera_factory=lambda: camera,
        tracker_factory=lambda: tracker,
        processor=GestureProcessor(GestureConfig(smoothing=1.0)),
        target_fps=200,
    )
    svc.start()
    time.sleep(wait)
    svc.stop()
    return svc, msgs


def test_camera_failure_surfaces_error_without_crash():
    cam = FakeCamera(fail_open=True)
    svc, msgs = run_service(cam, FakeTracker([]), wait=0.2)
    assert any(m["type"] == "error" and m["code"] == "CAMERA_UNAVAILABLE" for m in msgs)
    assert [m for m in msgs if m["type"] == "status"][-1]["camera"] == "error"
    assert not svc.is_running


def test_normal_flow_releases_camera_and_ends_gestures():
    cam, trk = FakeCamera(), FakeTracker([obs("open")] * 5 + [obs("open", offset=(0.05, 0))])
    svc, msgs = run_service(cam, trk)
    phases = [m["phase"] for m in msgs if m["type"] == "gesture"]
    assert phases[0] == "start" and "update" in phases and phases[-1] == "end"
    statuses = [m for m in msgs if m["type"] == "status"]
    assert statuses[0]["camera"] == "starting"
    assert any(s["camera"] == "ready" for s in statuses)
    assert statuses[-1]["camera"] == "stopped"
    assert cam.opened and cam.released and trk.closed
    assert not svc.is_running


def test_tracker_unavailable_reports_error():
    from app.hand_tracker import TrackerUnavailableError

    def bad_tracker():
        raise TrackerUnavailableError("model missing")

    msgs = []
    svc = GestureService(
        sink=msgs.append,
        camera_factory=lambda: FakeCamera(),
        tracker_factory=bad_tracker,
        processor=GestureProcessor(),
    )
    svc.start()
    time.sleep(0.2)
    svc.stop()
    assert any(m["type"] == "error" and m["code"] == "INTERNAL_ERROR" for m in msgs)
