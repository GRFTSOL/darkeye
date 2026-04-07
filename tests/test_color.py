"""utils.color：OKLCH/sRGB 转换与 HEX 解析。"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.color import (  # noqa: E402
    linear_to_srgb,
    oklch_to_srgb,
    srgb_to_linear,
    srgb_to_oklch,
)


def test_oklch_to_srgb_black_and_white():
    black = oklch_to_srgb(0.0, 0.0, 0.0)
    assert np.allclose(black, [0, 0, 0])

    white = oklch_to_srgb(1.0, 0.0, 137.0)
    assert np.allclose(white, [255, 255, 255])


def test_oklch_to_srgb_broadcast_shapes():
    """向量 L、标量 C/H 应能广播。"""
    L = np.array([0.0, 1.0])
    out = oklch_to_srgb(L, 0.0, 0.0)
    assert out.shape == (2, 3)
    assert np.allclose(out[0], [0, 0, 0])
    assert np.allclose(out[1], [255, 255, 255])


def test_linear_to_srgb_and_srgb_to_linear_roundtrip():
    linear = np.array([0.0, 0.5, 1.0], dtype=np.float64)
    srgb = linear_to_srgb(linear)
    back = srgb_to_linear(srgb)
    assert np.allclose(back, linear, atol=1e-6)


def test_srgb_to_oklch_hex_black_white():
    lab0 = srgb_to_oklch("#000000")
    assert lab0.shape == (3,)
    assert lab0[0] < 0.05 and lab0[1] < 0.05

    lab1 = srgb_to_oklch("#ffffff")
    assert lab1[0] > 0.95 and lab1[1] < 0.05


def test_srgb_to_oklch_accepts_hash_strip():
    a = srgb_to_oklch("#FF0000")
    b = srgb_to_oklch("FF0000")
    assert np.allclose(a, b)


@pytest.mark.parametrize(
    "bad",
    ["", "12", "gg0000", "#abcde", "#00112233"],
)
def test_srgb_to_oklch_invalid_hex_raises(bad):
    with pytest.raises(ValueError):
        srgb_to_oklch(bad)


@pytest.mark.filterwarnings("ignore:invalid value encountered in power:RuntimeWarning")
def test_oklch_autopair_false_masks_out_of_gamut():
    """autopair=False 时超域向量在某一维可被遮成白。"""
    out = oklch_to_srgb(0.5, 0.5, 0.0, autopair=False)
    assert out.shape == (3,)
    assert np.all(out >= 0) and np.all(out <= 255)
