from app.gesture_classifier import classify, extended_finger_count, pinch_distance
from tests.landmarks import make_hand


def test_open_palm_is_rotate():
    assert classify(make_hand("open")) == "rotate"


def test_fist_is_pan():
    assert classify(make_hand("fist")) == "pan"


def test_pinch_is_zoom():
    assert classify(make_hand("pinch")) == "zoom"


def test_single_finger_is_no_gesture():
    assert classify(make_hand("point")) is None


def test_wrong_landmark_count_is_none():
    assert classify(make_hand("open")[:10]) is None


def test_degenerate_hand_is_none():
    from app.models import Landmark

    assert classify([Landmark(0.5, 0.5)] * 21) is None


def test_pinch_hysteresis_threshold():
    hand = make_hand("pinch", pinch_gap=0.6)
    assert classify(hand, pinch_threshold=0.35) == "rotate"  # not a pinch yet
    assert classify(hand, pinch_threshold=1.1) == "zoom"  # still zoom once active


def test_distances_and_counts():
    assert extended_finger_count(make_hand("open")) == 4
    assert extended_finger_count(make_hand("fist")) == 0
    assert abs(pinch_distance(make_hand("pinch", pinch_gap=0.5)) - 0.5) < 1e-6
