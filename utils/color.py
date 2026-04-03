import numpy as np


def oklch_to_srgb(L, C, H, autopair=True):
    """批量 OKLCH → sRGB (0-255 int)
    #这个转换和官方的没有区别
    """
    L = np.asarray(L)
    C = np.asarray(C)
    h_rad = np.radians(np.asarray(H))

    a = C * np.cos(h_rad)
    b = C * np.sin(h_rad)

    # 广播数组以匹配形状
    L, a, b = np.broadcast_arrays(L, a, b)

    # 构造 (..., 3) 矩阵
    lab = np.stack([L, a, b], axis=-1)

    # OKLCH -> LMS (pre-cube)
    # 矩阵 M1 (转置后用于右乘)
    M1 = np.array(
        [
            [1.0, 1.0, 1.0],
            [0.3963377774, -0.1055613458, -0.0894841775],
            [0.2158037573, -0.0638541728, -1.2914855480],
        ]
    )

    lms_ = lab @ M1
    lms = lms_**3

    # LMS -> Linear sRGB
    # 矩阵 M2 (转置后用于右乘)
    M2 = np.array(
        [
            [4.0767416621, -1.2684380046, -0.0041960863],
            [-3.3077115913, 2.6097574011, -0.7034186147],
            [0.2309699292, -0.3413193965, 1.7076147010],
        ]
    )

    rgb_lin = lms @ M2

    # linear → sRGB gamma + clip
    def gamma(x):
        return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)

    # 超出范围的自动匹配最近的颜色
    if autopair:
        srgb = np.clip(gamma(rgb_lin), 0.0, 1.0)
    else:
        # 选择超出范围的变白色
        srgb_uncapped = gamma(rgb_lin)
        mask1 = np.any(srgb_uncapped > 1.0, axis=-1, keepdims=True)
        mask2 = np.any(srgb_uncapped < 0, axis=-1, keepdims=True)
        mask = mask1 | mask2
        srgb = np.where(mask, 1.0, np.clip(srgb_uncapped, 0.0, 1.0))

    return np.round(srgb * 255).astype(int)


def linear_to_srgb(linear):
    # Gamma 校正 + clipping 到 [0,1]
    gamma = np.where(
        linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055
    )
    return np.clip(gamma, 0, 1)


def linear_srgb_to_oklch(rgb):
    """
    将线性 sRGB 转换为 Oklab 空间
    参数 rgb: numpy 数组，形状为 (..., 3)，取值范围 [0, 1]
    """
    # 确保输入是 float32 以匹配 C++ 的精度
    rgb = np.asarray(rgb, dtype=np.float32)

    # 1. 线性变换到 LMS 锥体响应空间
    # 这里的系数对应 C++ 中的 l, m, s 计算
    l = (
        0.4122214708 * rgb[..., 0]
        + 0.5363325363 * rgb[..., 1]
        + 0.0514459929 * rgb[..., 2]
    )
    m = (
        0.2119034982 * rgb[..., 0]
        + 0.6806995451 * rgb[..., 1]
        + 0.1073969566 * rgb[..., 2]
    )
    s = (
        0.0883024619 * rgb[..., 0]
        + 0.2817188376 * rgb[..., 1]
        + 0.6299787005 * rgb[..., 2]
    )

    # 2. 非线性压缩：开三次方 (Perceptual non-linearity)
    # cbrt 在处理负数时比 x**(1/3) 更鲁棒
    l_ = np.cbrt(l)
    m_ = np.cbrt(m)
    s_ = np.cbrt(s)

    # 3. 线性变换得到 Oklab 分量 (L, a, b)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    # 1. 计算 Chroma (C) - 欧几里得距离
    C = np.hypot(a, b)

    # 2. 计算 Hue (h) - 弧度转角度
    # arctan2(y, x) 自动处理四个象限
    h_rad = np.arctan2(b, a)
    h_deg = np.degrees(h_rad)

    # 将范围从 [-180, 180] 归一化到 [0, 360]
    h_deg = np.mod(h_deg, 360)

    return np.stack([L, C, h_deg], axis=-1)


def srgb_to_linear(c_srgb):
    # 对每个颜色分量进行逆伽马校正
    c_linear = np.where(
        c_srgb <= 0.04045, c_srgb / 12.92, ((c_srgb + 0.055) / 1.055) ** 2.4
    )
    return c_linear


def srgb_to_oklch(hexRGB: str):
    """srgb转oklch
    hex格式
    """
    # 1. 清理并解析 HEX 字符串
    hexRGB = hexRGB.lstrip("#").strip()
    if len(hexRGB) != 6:
        raise ValueError("HEX 颜色必须是 6 位（RRGGBB）格式")

    try:
        r = int(hexRGB[0:2], 16)
        g = int(hexRGB[2:4], 16)
        b = int(hexRGB[4:6], 16)
    except ValueError:
        raise ValueError("无效的 HEX 颜色格式")

    # 2. 转为 0~1 范围的 sRGB 值
    srgb = np.array([r, g, b], dtype=np.float32) / 255.0
    linear = srgb_to_linear(srgb)
    return linear_srgb_to_oklch(linear)
