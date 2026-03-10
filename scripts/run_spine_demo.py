"""独立运行书脊检测 demo（固定比例）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core" / "cover"))
sys.path.insert(0, str(ROOT))

from spine_detect import detect_spine_edges


def main() -> None:
    image_path = ROOT / "resources" / "public" / "workcovers" / "abf166pl.jpg"
    if not image_path.exists():
        print(f"错误: 测试图片不存在: {image_path}")
        print("请将 abf166pl.jpg 放入 resources/public/workcovers/")
        sys.exit(1)
    print(f"输入图片: {image_path}")
    x_left, x_right = detect_spine_edges(image_path, method="sobel", visualize=True)
    print(f"书脊左边缘 x = {x_left:.1f}")
    print(f"书脊右边缘 x = {x_right:.1f}")
    print(f"书脊宽度 = {x_right - x_left:.1f} 像素")


if __name__ == "__main__":
    main()
