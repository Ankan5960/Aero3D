import pytest

from app.gesture_processor import GestureConfig, GestureProcessor
from tests.landmarks import obs


def feed(proc, frames):
    out = []
    for f in frames:
        out += proc.process(f, 0)
    return out


def start_rotate(proc):
    return feed(proc, [obs("open")] * 3)


def test_start_requires_stable_frames():
    p = GestureProcessor()
    assert feed(p, [obs("open")] * 2) == []
    msgs = feed(p, [obs("open")])
    assert [m["phase"] for m in msgs] == ["start"]
    assert msgs[0]["gesture"] == "rotate"


def test_rotate_delta_sign_and_zero_movement():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    start_rotate(p)
    assert p.process(obs("open"), 0) == []  # zero movement -> no events
    msgs = p.process(obs("open", offset=(0.05, -0.03)), 0)
    assert msgs[0]["phase"] == "update"
    assert msgs[0]["delta"]["x"] > 0 and msgs[0]["delta"]["y"] < 0
    assert msgs[0]["scale_delta"] is None


def test_dead_zone_suppresses_tiny_movement():
    p = GestureProcessor(GestureConfig(smoothing=1.0, dead_zone=0.01))
    start_rotate(p)
    assert p.process(obs("open", offset=(0.003, 0.0)), 0) == []


def test_outlier_delta_clamped():
    p = GestureProcessor(GestureConfig(smoothing=1.0, max_delta=0.1))
    start_rotate(p)
    msgs = p.process(obs("open", offset=(0.4, 0.0)), 0)
    assert msgs[0]["delta"]["x"] == pytest.approx(0.1)


def test_fist_is_pan():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    msgs = feed(p, [obs("fist")] * 3)
    assert msgs[0]["gesture"] == "pan"
    msgs = p.process(obs("fist", offset=(0.0, 0.04)), 0)
    assert msgs[0]["delta"]["y"] > 0


def test_zoom_scale_direction_and_bounds():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    feed(p, [obs("pinch", pinch_gap=0.1)] * 3)
    out = p.process(obs("pinch", pinch_gap=0.3), 0)
    assert out[0]["gesture"] == "zoom" and out[0]["scale_delta"] > 1.0
    assert out[0]["delta"] == {"x": 0.0, "y": 0.0}
    assert out[0]["scale_delta"] <= 1.1 + 1e-6
    out = p.process(obs("pinch", pinch_gap=0.1), 0)
    assert 1 / 1.1 - 1e-6 <= out[0]["scale_delta"] < 1.0


def test_zoom_hysteresis_keeps_gesture_while_spreading():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    feed(p, [obs("pinch", pinch_gap=0.1)] * 3)
    out = p.process(obs("pinch", pinch_gap=0.6), 0)  # above enter threshold, below exit
    assert out and out[0]["gesture"] == "zoom" and out[0]["phase"] == "update"


def test_brief_glitch_does_not_end_or_move():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    start_rotate(p)
    assert p.process(obs("fist"), 0) == []  # single differing frame
    # recovery re-baselines: no jump even though position differs
    assert p.process(obs("open", offset=(0.2, 0.0)), 0) == []
    msgs = p.process(obs("open", offset=(0.25, 0.0)), 0)
    assert msgs and msgs[0]["phase"] == "update"


def test_gesture_change_ends_previous_first():
    p = GestureProcessor()
    start_rotate(p)
    msgs = feed(p, [obs("fist")] * 3)
    assert [m["phase"] for m in msgs] == ["end"] and msgs[0]["gesture"] == "rotate"
    msgs = feed(p, [obs("fist")] * 3)
    assert msgs[0]["phase"] == "start" and msgs[0]["gesture"] == "pan"


def test_tracking_loss_ends_gesture_and_sets_lost():
    p = GestureProcessor()
    start_rotate(p)
    assert p.tracking == "tracking"
    msgs = feed(p, [None] * 4)
    assert [m["phase"] for m in msgs] == ["end"]
    assert p.tracking == "lost"


def test_no_hand_never_moves_and_stays_searching():
    p = GestureProcessor()
    assert feed(p, [None] * 10) == []
    assert p.tracking == "searching"


def test_baseline_reset_after_reacquisition():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    start_rotate(p)
    feed(p, [None] * 4)
    msgs = feed(p, [obs("open", offset=(0.3, 0.0))] * 3)
    assert [m["phase"] for m in msgs] == ["start"]
    assert msgs[0]["delta"] == {"x": 0.0, "y": 0.0}


def test_low_confidence_treated_as_missing():
    p = GestureProcessor()
    assert feed(p, [obs("open", confidence=0.2)] * 5) == []
    assert p.tracking == "searching"


def test_disable_ends_active_gesture_and_blocks_processing():
    p = GestureProcessor()
    start_rotate(p)
    msgs = p.set_enabled(False, 0)
    assert [m["phase"] for m in msgs] == ["end"]
    assert p.tracking == "disabled"
    assert feed(p, [obs("open")] * 5) == []
    p.set_enabled(True, 0)
    assert p.tracking == "searching"


def test_sensitivity_scales_delta_and_is_clamped():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    p.set_sensitivity(100)
    assert p.config.sensitivity == 2.0
    p.set_sensitivity(0.0)
    assert p.config.sensitivity == 0.25
    p.set_sensitivity(2.0)
    start_rotate(p)
    msgs = p.process(obs("open", offset=(0.02, 0)), 0)
    assert msgs[0]["delta"]["x"] == pytest.approx(0.04, abs=1e-3)


def test_seq_is_monotonic():
    p = GestureProcessor(GestureConfig(smoothing=1.0))
    msgs = start_rotate(p) + p.process(obs("open", offset=(0.05, 0)), 0)
    seqs = [m["seq"] for m in msgs]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
