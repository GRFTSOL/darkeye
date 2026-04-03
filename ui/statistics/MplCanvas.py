# 所有的画图的函数
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.cm as cm
import logging

from matplotlib import rcParams

rcParams["font.family"] = "SimHei"  # 设置全局字体为黑体
rcParams["axes.unicode_minus"] = False  # 解决负号显示为方块的问题
import numpy as np
from core.database.query import get_actress_by_plane, get_actress_body_data


def weighted_percentile(data: list, weights: list, percentile: float):
    """计算加权分位数（纯 Python 实现）"""
    # 将 data 和 weights 按 data 排序
    combined = sorted(zip(data, weights), key=lambda x: x[0])
    data_sorted, weights_sorted = zip(*combined)

    # 计算累积权重
    cum_weights = []
    total = 0
    for w in weights_sorted:
        total += w
        cum_weights.append(total)

    total_weight = cum_weights[-1]
    target = percentile * total_weight

    # 插值查找分位值
    for i, cw in enumerate(cum_weights):
        if cw >= target:
            if i == 0:
                return data_sorted[0]
            prev_cw = cum_weights[i - 1]
            prev_data = data_sorted[i - 1]
            curr_data = data_sorted[i]
            # 线性插值
            frac = (target - prev_cw) / (cw - prev_cw)
            return prev_data + frac * (curr_data - prev_data)

    return data_sorted[-1]  # fallback：100%分位时返回最大值


def float_range(start, stop=None, step=1.0):
    if stop is None:
        stop = start
        start = 0.0
    if step == 0:
        raise ValueError("step must not be zero")

    result = []
    while (step > 0 and start < stop) or (step < 0 and start > stop):
        result.append(start)
        start += step
    return result


def gaussian_kde_manual(x_vals, weights, grid, bandwidth):
    kde_vals = np.zeros_like(grid)
    norm_factor = np.sum(weights) * (bandwidth * np.sqrt(2 * np.pi))

    for xi, wi in zip(x_vals, weights):
        kde_vals += wi * np.exp(-0.5 * ((grid - xi) / bandwidth) ** 2)

    return kde_vals / norm_factor


from enum import Enum


class Scope(Enum):
    PUBLIC = 0
    PRIVATE = 1
    MAS_COUNT = 2
    MAS_WEIGHT = 3


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 4), dpi=100)
        # self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

    def plot_work_actress_age(self, scope):
        """绘制作品的拍摄年龄的分布，频率图"""
        from core.database.query import fetch_work_actress_avg_age

        tuple_list = fetch_work_actress_avg_age(scope)
        age = np.array([item[0] for item in tuple_list])
        weight = np.array([item[1] for item in tuple_list])

        low = weighted_percentile(age, weight, 0.05)
        high = weighted_percentile(age, weight, 0.95)
        mid = (low + high) / 2

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        # 画直方图
        counts, bins, _ = self.ax.hist(
            age,
            bins=50,
            weights=weight,
            color="skyblue",
            edgecolor="#7D9CE8",
            density=True,
        )

        # KDE 平滑频率曲线
        grid = np.linspace(min(age), max(age), 500)
        bandwidth = 1.0  # 控制平滑程度，值越大越平滑
        kde_vals = gaussian_kde_manual(age, weight, grid, bandwidth)
        self.ax.plot(grid, kde_vals, color="blue", linewidth=2, label="频率曲线 (KDE)")
        # 辅助线
        ymin, ymax = self.ax.get_ylim()
        self.ax.axvline(low, color="red", linestyle="--", label="5th percentile")
        self.ax.axvline(high, color="red", linestyle="--", label="95th percentile")
        self.ax.text(
            mid,
            ymax * 0.9,
            "90%区间",
            ha="center",
            fontsize=12,
            color="black",
            fontname="SimHei",
        )

        # 标题设置
        match scope:
            case 0:
                self.ax.set_title("收藏作品女优平均拍摄年龄分布", fontname="SimHei")
                self.ax.set_xlabel("平均拍摄年龄（岁）", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
            case 1:
                self.ax.set_title("撸过作品女优平均拍摄年龄分布", fontname="SimHei")
                self.ax.set_xlabel("平均拍摄年龄（岁）", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
            case 2:
                self.ax.set_title(
                    "起飞次数加权影片中女优平均拍摄年龄分布", fontname="SimHei"
                )
                self.ax.set_xlabel("拍摄年龄", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
            case -1:
                self.ax.set_title("公共库内女优平均拍摄年龄分布", fontname="SimHei")
                self.ax.set_xlabel("拍摄年龄", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
        self.ax.legend()
        self.draw()

    def plot_work_release_year(self, scope):
        """绘制作品发行年份分布直方图"""
        from core.database.query import fetch_work_release_by_year_by_scope

        data = fetch_work_release_by_year_by_scope(scope)
        logging.debug(f"发行年份数据：{data}")
        # 分离年份和数量
        years = [item[0] for item in data]  # ['2000', '2001', ...]
        counts = [item[1] for item in data]  # [1, 2, 5, ...]

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        # 创建柱状图

        bars = self.ax.bar(
            years, counts, color="skyblue", edgecolor="navy", linewidth=1.2
        )
        # 在每个柱子上方显示具体数值
        for bar in bars:
            height = bar.get_height()
            self.ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + max(counts) * 0.01,
                f"{int(height)}",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )

        # 美化
        self.ax.set_title("每年数量统计", fontsize=16, fontweight="bold", pad=20)
        self.ax.set_xlabel("年份", fontsize=12)
        self.ax.set_ylabel("数量", fontsize=12)
        self.draw()

    def plot_actress_debut_year(self, scope):
        """女优出道年份的分布直方图"""
        from core.database.query import fetch_actress_debut_by_year_by_scope

        data = fetch_actress_debut_by_year_by_scope(scope)
        logging.debug(f"女优出道年份统计：{data}")
        # 分离年份和数量
        years = [item[0] for item in data]  # ['2000', '2001', ...]
        counts = [item[1] for item in data]  # [1, 2, 5, ...]

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        # 创建柱状图

        bars = self.ax.bar(
            years, counts, color="skyblue", edgecolor="navy", linewidth=1.2
        )
        # 在每个柱子上方显示具体数值
        for bar in bars:
            height = bar.get_height()
            self.ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + max(counts) * 0.01,
                f"{int(height)}",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )

        # 美化
        self.ax.set_title("每年数量统计", fontsize=16, fontweight="bold", pad=20)
        self.ax.set_xlabel("年份", fontsize=12)
        self.ax.set_ylabel("数量", fontsize=12)
        self.draw()

    def draw_3d_size_dis(self):
        """画女优的3维的散点图，颜色代表罩杯"""
        # 这个现在有问题后面再改
        bodyData = get_actress_body_data()
        cup_colors = {
            # 使用蓝紫渐变到橙红的完整色系，确保15个级别都有良好区分度
            "A": "#F7FBFF",  # 极淡蓝色（几乎白）
            "B": "#E3EFF9",  # 非常浅蓝
            "C": "#C6DBEF",  # 浅天蓝
            "D": "#9ECAE1",  # 淡蓝
            "E": "#6BAED6",  # 柔和蓝
            "F": "#4292C6",  # 标准蓝
            "G": "#2171B5",  # 中蓝
            "H": "#08519C",  # 深蓝
            "I": "#08306B",  # 深靛蓝
            "J": "#6A51A3",  # 蓝紫色（过渡开始）
            "K": "#8C6BB1",  # 紫
            "L": "#8C6BB1",  # 中紫
            "M": "#CC6677",  # 紫红色
            "N": "#E6553E",  # 橙红
            "O": "#FD8D3C",  # 亮橙
        }

        # 2. 映射颜色列表（DataFrame中要先填充空值或剔除）
        colors = [
            cup_colors.get(item.get("cup"), "#999999")  # 找不到就默认灰色
            for item in bodyData
        ]
        xs = [item.get("bust") for item in bodyData]
        ys = [item.get("waist") for item in bodyData]
        zs = [item.get("hip") for item in bodyData]

        self.fig.clf()
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.scatter(xs, ys, zs, c=colors, alpha=0.7)

        for cup, color in cup_colors.items():
            self.ax.scatter([], [], [], c=color, label=cup)

        self.ax.legend(title="cup")
        self.ax.set_xlabel("胸围", fontname="SimHei")
        self.ax.set_ylabel("腰围", fontname="SimHei")
        self.ax.set_zlabel("臀围", fontname="SimHei")

        self.ax.set_title("女优三围分布图", fontname="SimHei")
        self.draw()

    # 绘制女优的罩杯分布
    def draw_cup_distribution_pie(self, scope):
        from core.database.query import fetch_actress_cup_distribution

        tuple_list = fetch_actress_cup_distribution(scope)
        # 数据准备
        labels = [item[0] for item in tuple_list]
        sizes = [item[1] for item in tuple_list]
        # 颜色映射（你可以用之前定义的 cup_colors，也可以自动配色）
        colors = cm.tab20.colors[: len(labels)]  # 选前几个颜色，够用就行
        max_index = max(range(len(sizes)), key=lambda i: sizes[i])
        explode = [0.1 if i == max_index else 0 for i in range(len(sizes))]

        # 清空图像
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        # 绘制饼图
        wedges, texts, autotexts = self.ax.pie(
            sizes,
            labels=labels,
            autopct="%1.1f%%",
            explode=explode,
            startangle=140,
            colors=colors,
            textprops={"fontsize": 10, "fontname": "SimHei"},
        )
        match scope:
            case 0:
                self.ax.set_title(
                    "收藏库女优罩杯分布(日本罩杯比国内大两个)",
                    fontname="SimHei",
                    fontsize=14,
                )
            case 1:
                self.ax.set_title(
                    "撸过女优罩杯分布(日本罩杯比国内大两个)",
                    fontname="SimHei",
                    fontsize=14,
                )
            case 2:
                self.ax.set_title(
                    "按撸管次数加权女优罩杯分布(日本罩杯比国内大两个)",
                    fontname="SimHei",
                    fontsize=14,
                )
            case -1:
                self.ax.set_title(
                    "公共库女优罩杯分布(日本罩杯比国内大两个)",
                    fontname="SimHei",
                    fontsize=14,
                )

        self.ax.axis("equal")  # 保持饼图为圆形
        self.draw()  # 刷新 FigureCanvas

    # 绘制女优的身高分布
    def draw_height_distribution(self, scope):
        from core.database.query import fetch_actress_height_with_weights

        tuple_list = fetch_actress_height_with_weights(scope)

        height = np.array([item[0] for item in tuple_list])
        weight = np.array([item[1] for item in tuple_list])

        min_val = min(height)
        max_val = max(height)

        bin = float_range(min_val - 0.5, max_val + 1.5, 1)

        low = weighted_percentile(height, weight, 0.05)
        high = weighted_percentile(height, weight, 0.95)
        mid = (low + high) / 2

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        # 画直方图
        counts, bins, _ = self.ax.hist(
            height,
            bins=bin,
            weights=weight,
            color="skyblue",
            edgecolor="#7D9CE8",
            density=True,
        )

        # KDE 平滑频率曲线
        grid = np.linspace(min(height), max(height), 500)
        bandwidth = 2.0  # 控制平滑程度，值越大越平滑
        kde_vals = gaussian_kde_manual(height, weight, grid, bandwidth)
        self.ax.plot(grid, kde_vals, color="blue", linewidth=2, label="频率曲线 (KDE)")
        # 辅助线
        ymin, ymax = self.ax.get_ylim()
        self.ax.axvline(low, color="red", linestyle="--", label="5th percentile")
        self.ax.axvline(high, color="red", linestyle="--", label="95th percentile")
        self.ax.text(
            mid,
            ymax * 0.9,
            "90%区间",
            ha="center",
            fontsize=12,
            color="black",
            fontname="SimHei",
        )

        match scope:
            case 0:
                self.ax.set_title("收藏库内女优身高分布", fontname="SimHei")
                self.ax.set_xlabel("身高", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
            case 1:
                self.ax.set_title("撸过女优身高分布", fontname="SimHei")
                self.ax.set_xlabel("身高", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
            case 2:
                self.ax.set_title("起飞次数加权影片中女优身高分布", fontname="SimHei")
                self.ax.set_xlabel("身高", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
            case -1:
                self.ax.set_title("公共库中女优身高分布", fontname="SimHei")
                self.ax.set_xlabel("身高", fontname="SimHei")
                self.ax.set_ylabel("频率", fontname="SimHei")
        self.ax.legend()
        self.draw()

    # 绘制女优的腰臀比分布
    def draw_actress_body_wh_ratio(self, scope):
        from core.database.query import fetch_actress_waist_hip_stats

        tuple_list = fetch_actress_waist_hip_stats(scope)
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        waist = [item[0] for item in tuple_list]
        hip = [item[1] for item in tuple_list]
        weight = [item[2] for item in tuple_list]
        wh_ratio = [item[3] for item in tuple_list]
        # 统计每个腰围-臀围组合的频次

        # 重映射计算点大小（基于频次，范围10-150）
        min_count = min(weight)
        max_count = max(weight)
        base = max_count - min_count

        if base == 0:
            size = [75] * len(weight)  # 全相同频次时用中间值，避免除零
        else:
            size = [140 * y / base + 10 for y in [x - min_count for x in weight]]
        scatter = self.ax.scatter(
            x=waist,
            y=hip,
            s=size,
            c=wh_ratio,  # 颜色映射腰臀比
            cmap="RdYlBu_r",
            alpha=1,
        )
        # 添加颜色条
        cbar = self.figure.colorbar(scatter, ax=self.ax)
        cbar.set_label("腰臀比", fontsize=10, fontname="SimHei")  # 设置颜色条标签

        self.ax.set_xlabel("腰围 (cm)", fontsize=12, fontname="SimHei")
        self.ax.set_ylabel("臀围 (cm)", fontsize=12, fontname="SimHei")
        match scope:
            case 0:
                self.ax.set_title(
                    "收藏库女优腰臀比（颜色=腰臀比，大小=人数）",
                    fontsize=14,
                    fontname="SimHei",
                )
            case 1:
                self.ax.set_title(
                    "撸过女优腰臀比（颜色=腰臀比，大小=人数）",
                    fontsize=14,
                    fontname="SimHei",
                )
            case 2:
                self.ax.set_title(
                    "撸过加权女优腰臀比（颜色=腰臀比，大小=人数）",
                    fontsize=14,
                    fontname="SimHei",
                )
            case -1:
                self.ax.set_title(
                    "公共库女优腰臀比（颜色=腰臀比，大小=人数）",
                    fontsize=14,
                    fontname="SimHei",
                )
        self.draw()

    # 导演的拍片的数量
    def draw_director_bar(self, scope: int):
        from core.database.query import fetch_top_directors_by_scope

        tuple_list = fetch_top_directors_by_scope(scope)
        # 绘制横向柱状图
        director = [item[0] for item in tuple_list]
        num = [item[1] for item in tuple_list]
        director.reverse()
        num.reverse()
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        bars = self.ax.barh(
            director, num, color="skyblue", edgecolor="black", height=0.6
        )
        for bar in bars:
            width = bar.get_width()
            self.ax.text(
                width + 0.1,  # x位置（柱右侧+0.5单位）
                bar.get_y() + bar.get_height() / 2,  # y位置（柱中心）
                f"{int(width)}",  # 显示整数
                va="center",  # 垂直居中
                ha="left",  # 水平左对齐
            )
            # 装饰图形

            # === 关键修复部分 ===
        # 1. 先固定刻度位置（对应每个柱子的中心）
        y_positions = [bar.get_y() + bar.get_height() / 2 for bar in bars]
        self.ax.set_yticks(y_positions)  # 固定刻度位置

        # 2. 再设置刻度标签（日语字体）
        self.ax.set_yticklabels(director, fontname="MS Gothic")  # 或其他日语字体
        # ===================
        # self.ax.set_yticklabels(df['导演'], fontname='MS Gothic')  # 仅Y轴标签
        self.ax.set_xlabel("影片数量", fontsize=12, fontname="SimHei")
        self.ax.set_title("导演作品数量排名", fontsize=14, fontname="SimHei")
        # self.ax.grid(axis='x', linestyle='--', alpha=0.6,fontname='SimHei')
        self.fig.tight_layout()
        self.draw()

    # 最喜欢的女优
    def draw_most_like_actress(self):
        tuple_list = get_actress_by_plane()
        actress = [item[0] for item in tuple_list]
        num = [item[1] for item in tuple_list]
        actress.reverse()
        num.reverse()
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        bars = self.ax.barh(
            actress, num, color="skyblue", edgecolor="black", height=0.6
        )
        for bar in bars:
            width = bar.get_width()
            self.ax.text(
                width + 0.1,  # x位置（柱右侧+0.5单位）
                bar.get_y() + bar.get_height() / 2,  # y位置（柱中心）
                f"{int(width)}",  # 显示整数
                va="center",  # 垂直居中
                ha="left",  # 水平左对齐
            )
            # 装饰图形

            # === 关键修复部分 ===
        # 1. 先固定刻度位置（对应每个柱子的中心）
        y_positions = [bar.get_y() + bar.get_height() / 2 for bar in bars]
        self.ax.set_yticks(y_positions)  # 固定刻度位置

        # 2. 再设置刻度标签（日语字体）
        self.ax.set_yticklabels(actress, fontname="SimHei")  # 或其他日语字体
        # ===================
        # self.ax.set_yticklabels(df['导演'], fontname='MS Gothic')  # 仅Y轴标签
        self.ax.set_xlabel("撸管次数", fontsize=12, fontname="SimHei")
        self.ax.set_title("女优按撸管次数排名", fontsize=14, fontname="SimHei")
        # self.ax.grid(axis='x', linestyle='--', alpha=0.6,fontname='SimHei')
        self.fig.tight_layout()
        self.draw()

    # 片商的统计数量
    def draw_studio_bar(self, scope: int):
        from core.database.query import fetch_top_studios_by_scope

        tuple_list = fetch_top_studios_by_scope(scope)
        studio = [item[0] for item in tuple_list]
        num = [item[1] for item in tuple_list]
        studio.reverse()
        num.reverse()
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        bars = self.ax.barh(studio, num, color="skyblue", edgecolor="black", height=0.6)
        for bar in bars:
            width = bar.get_width()
            self.ax.text(
                width + 0.1,  # x位置（柱右侧+0.5单位）
                bar.get_y() + bar.get_height() / 2,  # y位置（柱中心）
                f"{int(width)}",  # 显示整数
                va="center",  # 垂直居中
                ha="left",  # 水平左对齐
            )

            # 1. 先固定刻度位置（对应每个柱子的中心）
        y_positions = [bar.get_y() + bar.get_height() / 2 for bar in bars]
        self.ax.set_yticks(y_positions)  # 固定刻度位置

        # 2. 再设置刻度标签（日语字体）
        self.ax.set_yticklabels(studio, fontname="SimHei")  # 或其他日语字体
        # 装饰图形
        self.ax.set_xlabel("数量", fontsize=12, fontname="SimHei")
        self.ax.set_title("片商数量排名", fontsize=14, fontname="SimHei")

        # self.ax.grid(axis='x', linestyle='--', alpha=0.6,fontname='SimHei')
        # self.fig.tight_layout()
        self.draw()

    def draw_add_time_distribution(self):
        """作品数量按添加时间的分布
        横轴时间，纵轴总数量
        未来加上从0开始，类似github的starhistory那种样子的，包括手工样式
        """
        from datetime import datetime, timedelta

        # 读数据
        from core.database.query import get_all_work_addtime

        time_list: list[datetime] = get_all_work_addtime()
        time_list.sort()

        # 步骤2：按天统计累计数量（取每个月的最后一天作为该月代表点）
        daily_cumulative = {}  # key: "YYYY-MM-dd", value: 该日结束时的统计量

        cumulative_count = 0
        for dt in time_list:
            month_key = datetime.strptime(
                dt.strftime("%Y-%m-%d"), "%Y-%m-%d"
            )  # 如 "2024-01"
            cumulative_count += 1
            daily_cumulative[month_key] = cumulative_count

        # 统计出的结果是不连续的

        # 1. 获取最小和最大日期
        dates = sorted(daily_cumulative.keys())
        if not dates:
            print("无数据")
            # 退出或处理空情况

        start_date = dates[0]
        end_date = dates[-1]

        # 2. 生成完整的连续日期序列（包括中间缺失的日子）
        current_date = start_date
        continuous_dates: list[datetime] = []
        while current_date <= end_date:
            continuous_dates.append(current_date)
            current_date += timedelta(days=1)

        # 3. 填充累计数量（缺失日期保持前一天的累计值）
        continuous_counts = []
        prev_count = 0
        for d in continuous_dates:
            if d in daily_cumulative:
                prev_count = daily_cumulative[d]
            continuous_counts.append(prev_count)

        # 4. 直接使用原始累计数据作图（不做平滑处理）
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        self.ax.plot(
            continuous_dates, continuous_counts, linewidth=2, color="steelblue"
        )
        self.ax.set_title("添加到数据库中作品数量随时间分布", fontsize=16)
        self.ax.set_xlabel("Date", fontsize=14)
        self.ax.set_ylabel("Nums", fontsize=14)
        """
        days = sorted(daily_cumulative.keys())  # 自动按日期排序
        
        x_labels = [day for day in days]
        y_data = [daily_cumulative[day] for day in days]
        #self.fig.clf()
        #self.ax = self.fig.add_subplot(111)

        self.ax.plot(x_labels, y_data, marker=None, linestyle='-',linewidth=1, color='red')
        """
        self.draw()

    def draw_work_tag_cloud(self, scope: int):
        """绘制词云
        用wordcloud库
        """
        from core.database.query import get_tag_frequence
        from config import TEMP_PATH
        from pathlib import Path

        tag_freq = get_tag_frequence(scope)
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt

        wc = WordCloud(
            font_path="simhei.ttf",  # 中文字体路径，如黑体
            width=1600,
            height=900,
            background_color="white",
        )
        wc.generate_from_frequencies(tag_freq)
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        self.ax.imshow(wc, interpolation="bilinear")
        self.ax.axis("off")
        self.draw()
        file = Path(TEMP_PATH) / "tag_cloud_1600x900.png"
        wc.to_file(file)  # 保存到临时文件

    def plot_actress_debut_age(self):
        """绘制女优出道年龄的分布，频率图"""
        from core.database.query import fetch_actress_debut_age

        tuple_list = fetch_actress_debut_age()

        age = np.array([item[0] for item in tuple_list])
        weight = np.array([item[1] for item in tuple_list])

        low = weighted_percentile(age, weight, 0.05)
        high = weighted_percentile(age, weight, 0.95)
        mid = (low + high) / 2

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        # 画直方图
        counts, bins, _ = self.ax.hist(
            age,
            bins=40,
            weights=weight,
            color="skyblue",
            edgecolor="#7D9CE8",
            density=True,
        )

        # KDE 平滑频率曲线
        grid = np.linspace(min(age), max(age), 500)
        bandwidth = 1.0  # 控制平滑程度，值越大越平滑
        kde_vals = gaussian_kde_manual(age, weight, grid, bandwidth)
        self.ax.plot(grid, kde_vals, color="blue", linewidth=2, label="频率曲线 (KDE)")
        # 辅助线
        ymin, ymax = self.ax.get_ylim()
        self.ax.axvline(low, color="red", linestyle="--", label="5th percentile")
        self.ax.axvline(high, color="red", linestyle="--", label="95th percentile")
        self.ax.text(
            mid,
            ymax * 0.9,
            "90%区间",
            ha="center",
            fontsize=12,
            color="black",
            fontname="SimHei",
        )

        # 标题设置
        self.ax.set_title(
            "公共库内女优平均出道年龄分布(以出道日期减半年计算)", fontname="SimHei"
        )
        self.ax.set_xlabel("出道年龄", fontname="SimHei")
        self.ax.set_ylabel("频率", fontname="SimHei")
        self.ax.legend()
        self.draw()
