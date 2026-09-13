"""Figures from actual local result files; all captions distinguish constructed/synthetic data."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Wedge
from matplotlib.colors import LogNorm
from quality_tools import load_tool
from cumcm_b.geometry import unit, Belief
from cumcm_b.synthetic import generate_sources
from cumcm_b.policy import q4_station_route, ring25_cover

style = load_tool("cumcm_plot_style", "references/roles/编程手/scripts/plot_style.py")
apply_publication_style = style.apply_publication_style
PALETTE = style.PALETTE
audit_layout = style.audit_layout
audit_design = style.audit_design
_save_grayscale_preview = style._save_grayscale_preview
export_figure = load_tool(
    "cumcm_export_figure", "tools/figure/scripts/export_figure.py"
).export_figure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results/synthetic"))
    parser.add_argument("--out", type=Path, default=Path("reports/figures"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    apply_publication_style("zh")
    plt.rcParams.update(
        {
            "svg.fonttype": "none",
            "font.size": 9,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
        }
    )
    contracts = []

    def start(spatial=False):
        fig, ax = plt.subplots(figsize=(6.3, 4.2), layout="constrained")
        if spatial:
            ax.set_aspect("equal")
            ax.set_xlabel("x 坐标 (m)")
            ax.set_ylabel("y 坐标 (m)")
        return fig, ax

    def save(fig, name, claim, source, stat="确定性计算，无统计推断"):
        issues = audit_layout(fig) + audit_design(fig)
        if issues:
            raise ValueError(f"{name}: {issues}")
        export_figure(
            fig,
            str(args.out / name),
            formats=["svg", "png"],
            dpi=300,
            size_inches=(6.3, 4.2),
            tight=False,
            grayscale_preview=False,
        )
        _save_grayscale_preview(args.out / (name + ".png"), 300)
        two_panel = {
            "process_q1_intersection",
            "result_q2_posterior",
            "raw_q3_sources",
            "process_q3_trajectory",
            "result_q3_paired",
            "process_q4_trajectory",
        }
        contracts.append(
            {
                "name": name,
                "claim": claim,
                "source": source,
                "statistics": stat,
                "size_inches": [6.3, 4.2],
                "dpi": 300,
                "origin": "本地合成或构造数据，非官方测试",
                "layout": (
                    "circular bar chart"
                    if name == "raw_q4_orientations"
                    else "two-panel analytical figure"
                    if name in two_panel
                    else "single quantitative panel"
                ),
                "backend": "matplotlib",
                "layout_issues": issues,
            }
        )
        plt.close(fig)

    q1 = json.loads((args.results / "q1.json").read_text())
    poly = np.array(q1["polygon"])
    cc = np.array(q1["circle_center"])
    rr = q1["circle_radius_m"]
    fig, ax = start(True)
    for i, obs in enumerate(q1["observations"]):
        p = np.array(obs["position"])
        end = p + 1400 * unit(obs["bearing_deg"])
        ax.plot(
            [p[0], end[0]],
            [p[1], end[1]],
            color=list(PALETTE.values())[i],
            ls=["-", "--", ":"][i],
            label=f"检测 {i + 1}",
        )
        ax.scatter(*p, s=35, marker=["o", "s", "^"][i], color=list(PALETTE.values())[i])
    ax.scatter(*poly.mean(axis=0), s=45, marker="x", color=PALETTE["dark"], label="可行真位置")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
    save(fig, "raw_q1_bearings", "三次合法带误差测向形成反例输入。", "q1.json；3 个构造检测点")

    b = Belief(error_deg=1.0)
    for obs in q1["observations"]:
        b.observe(obs["position"], obs["bearing_deg"])
    fig, (ax0, ax1) = plt.subplots(
        1,
        2,
        figsize=(6.3, 4.2),
        layout="constrained",
        gridspec_kw={"width_ratios": [1.12, 1]},
    )
    steps = np.array([h["observations"] for h in b.history])
    areas = np.array([h["area_m2"] for h in b.history])
    radii = np.array([h["radius_m"] for h in b.history])
    ax0.plot(
        steps,
        areas / areas[0],
        "-o",
        color=PALETTE["primary"],
        label="外包面积",
    )
    ax0.plot(
        steps,
        radii / radii[0],
        "--s",
        color=PALETTE["contrast"],
        label="MEC 半径",
    )
    ax0.set_yscale("log")
    ax0.set_xticks(steps)
    ax0.set_xlabel("累计检测点数")
    ax0.set_ylabel("相对初始值（对数轴）")
    ax0.set_title("约束逐步收缩", loc="left")
    ax0.grid(axis="y", color="#D9E1E8", lw=0.6, alpha=0.8)
    ax0.legend(frameon=False, loc="lower left")
    ax0.annotate(
        f"A={areas[-1]:.1f} m²",
        (steps[-1], areas[-1] / areas[0]),
        xytext=(-4, 8),
        textcoords="offset points",
        ha="right",
        fontsize=7,
        color=PALETTE["primary"],
    )
    ax0.annotate(
        f"R*={radii[-1]:.2f} m",
        (steps[-1], radii[-1] / radii[0]),
        xytext=(-4, -14),
        textcoords="offset points",
        ha="right",
        fontsize=7,
        color=PALETTE["contrast"],
    )

    final = b.history[-1]
    final_poly = np.asarray(final["polygon"])
    final_center = np.asarray(final["center"])
    final_radius = final["radius_m"]
    ax1.add_patch(
        Polygon(
            final_poly,
            closed=True,
            facecolor=PALETTE["sky"],
            edgecolor=PALETTE["primary"],
            alpha=0.32,
            lw=1.1,
            label="最终可行集",
        )
    )
    ax1.add_patch(
        Circle(
            final_center,
            final_radius,
            fill=False,
            color=PALETTE["contrast"],
            ls="--",
            lw=1.1,
            label=f"MEC，r={final_radius:.2f} m",
        )
    )
    ax1.add_patch(
        Circle(
            final_center,
            20,
            fill=False,
            color=PALETTE["neutral"],
            ls=":",
            lw=1.0,
            label="20 m 清除半径",
        )
    )
    ax1.scatter(*final_center, marker="+", s=65, color=PALETTE["dark"], zorder=3)
    ax1.set_aspect("equal")
    margin = 8
    x_min = min(final_poly[:, 0].min(), final_center[0] - final_radius, final_center[0] - 20)
    x_max = max(final_poly[:, 0].max(), final_center[0] + final_radius, final_center[0] + 20)
    y_min = min(final_poly[:, 1].min(), final_center[1] - final_radius, final_center[1] - 20)
    y_max = max(final_poly[:, 1].max(), final_center[1] + final_radius, final_center[1] + 20)
    ax1.set_xlim(x_min - margin, x_max + margin)
    ax1.set_ylim(y_min - margin, y_max + margin)
    ax1.set_xlabel("x 坐标 (m)")
    ax1.set_ylabel("y 坐标 (m)")
    ax1.set_title("最终定位外包", loc="left")
    ax1.legend(frameon=False, fontsize=7, loc="upper right")
    fig.text(0.01, 0.99, "a", ha="left", va="top", fontweight="bold", fontsize=9)
    fig.text(0.56, 0.99, "b", ha="left", va="top", fontweight="bold", fontsize=9)
    save(
        fig,
        "process_q1_intersection",
        "逐次增加测向约束压缩可行外包，并核对最终最小包围圆。",
        "q1.json 的三次测向；相同数据精确计算",
    )

    fig, ax = start(True)
    ax.add_patch(
        Polygon(
            poly, closed=True, facecolor="#dddddd", edgecolor=PALETTE["dark"], label="定位三角形"
        )
    )
    endpoints = np.array(q1["diameter_pair"])
    mid = endpoints.mean(axis=0)
    ax.add_patch(
        Circle(
            mid,
            q1["diameter_m"] / 2,
            fill=False,
            color=PALETTE["contrast"],
            ls="--",
            label="直径圆：r=19.50 m",
        )
    )
    ax.add_patch(
        Circle(cc, rr, fill=False, color=PALETTE["primary"], label=f"最小包围圆：r={rr:.2f} m")
    )
    ax.scatter(poly[:, 0], poly[:, 1], s=20, c=PALETTE["dark"])
    ax.set_xlim(-15, 55)
    ax.set_ylim(-25, 45)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=1)
    save(
        fig,
        "result_q1_circle",
        "D=39 m 不能保证半径20 m内一次清除。",
        "q1.json：直径、支撑点、最小包围圆",
    )

    candidates = pd.read_csv(args.results / "q2_candidates.csv")
    selected = candidates[candidates.travel_weight == 0.02].sort_values("rank")
    val = pd.read_csv(args.results / "q2_validation.csv")
    b = Belief()
    b.observe([0, 0], 0)
    fig, ax = start(True)
    ax.fill(
        b.polygon[:, 0],
        b.polygon[:, 1],
        color=PALETTE["sky"],
        alpha=0.5,
        label="首次观测的保守外包",
    )
    ax.scatter([0], [0], marker="s", s=40, color=PALETTE["dark"], label="首个检测点")
    ax.plot([0, 1500], [0, 0], "--", color=PALETTE["neutral"], label="示向度 0°")
    ax.set_ylim(-180, 180)
    ax.set_xlim(-60, 1560)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.38), ncol=1)
    save(
        fig,
        "raw_q2_prior",
        "一次示向度只限制方位，不给出准确距离。",
        "理论误差1.01°、接收上界1500 m；本地构造",
    )

    fig, ax = start(True)
    dots = ax.scatter(
        selected.x_m,
        selected.y_m,
        c=selected.worst_linearized_m,
        cmap="viridis",
        norm=LogNorm(),
        s=25,
    )
    ax.scatter(
        selected.iloc[0].x_m,
        selected.iloc[0].y_m,
        marker="*",
        s=160,
        c=PALETTE["contrast"],
        edgecolors=PALETTE["dark"],
        label="候选集内所选点",
    )
    outline = np.vstack((b.polygon, b.polygon[0]))
    ax.plot(outline[:, 0], outline[:, 1], color=PALETTE["neutral"], lw=0.7)
    cb = fig.colorbar(dots, ax=ax)
    cb.set_label("最坏线性化评分 (m，对数色阶)")
    cb.solids.set_rasterized(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12))
    save(
        fig,
        "process_q2_candidates",
        "在保证全向可接收的候选点内比较几何评分。",
        "q2_candidates.csv；λ=0.02；颜色是代理评分，非严格误差界",
    )

    sub = val[val.travel_weight == 0.02].copy()
    fig, (ax0, ax1) = plt.subplots(
        1,
        2,
        figsize=(6.3, 4.2),
        layout="constrained",
        gridspec_kw={"width_ratios": [1.15, 0.85]},
    )
    error_markers = {-1.0: "o", 0.0: "s", 1.0: "^"}
    error_colors = {-1.0: PALETTE["primary"], 0.0: PALETTE["sky"], 1.0: PALETTE["contrast"]}
    for error in (-1.0, 0.0, 1.0):
        subset = sub[sub.second_error_deg == error]
        ax0.scatter(
            subset.source_range_m,
            subset.posterior_radius_m,
            marker=error_markers[error],
            color=error_colors[error],
            s=32,
            alpha=0.78,
            edgecolors="white",
            linewidths=0.35,
            label=f"二次误差 {error:+.0f}°",
        )
    ax0.axhline(20, color=PALETTE["contrast"], ls="--", lw=1.0, label="20 m 清除阈值")
    ax0.set_xlabel("构造真位置距首测点 (m)")
    ax0.set_ylabel("后验包围半径 (m)")
    ax0.set_title("误差组合的后验结果", loc="left")
    ax0.grid(axis="y", color="#D9E1E8", lw=0.6, alpha=0.8)
    ax0.legend(frameon=False, loc="upper left")
    ranges = sorted(sub.source_range_m.unique())
    groups = [sub.loc[sub.source_range_m == distance, "posterior_radius_m"].to_numpy() for distance in ranges]
    bp = ax1.boxplot(groups, widths=0.48, patch_artist=True, showfliers=False, tick_labels=[f"{int(x)}" for x in ranges])
    for patch_box in bp["boxes"]:
        patch_box.set_facecolor(PALETTE["sky"])
        patch_box.set_alpha(0.45)
        patch_box.set_edgecolor(PALETTE["primary"])
    rng = np.random.default_rng(2048)
    for i, values in enumerate(groups, start=1):
        ax1.scatter(i + rng.uniform(-0.08, 0.08, len(values)), values, s=10, color=PALETTE["primary"], alpha=0.6)
    ax1.axhline(20, color=PALETTE["contrast"], ls="--", lw=1.0)
    ax1.set_xlabel("源距分组 (m)")
    ax1.set_ylabel("后验半径 (m)")
    ax1.set_title("按源距汇总", loc="left")
    ax1.grid(axis="y", color="#D9E1E8", lw=0.6, alpha=0.8)
    fig.text(0.01, 0.99, "a", ha="left", va="top", fontweight="bold", fontsize=9)
    fig.text(0.56, 0.99, "b", ha="left", va="top", fontweight="bold", fontsize=9)
    save(
        fig,
        "result_q2_posterior",
        "精确后验半径随真位置和误差组合变化，选点代理不等于保证。",
        "q2_validation.csv；λ=0.02",
        "6个距离×3个首次误差×3个第二次误差=54个确定性组合；散点重合未抖动",
    )

    runs = pd.read_csv(args.results / "runs.csv")
    for question in (3, 4):
        current_trace_path = args.results / f"q{question}_current_trace.json"
        trace_path = current_trace_path if current_trace_path.exists() else args.results / f"q{question}_trace.json"
        trace = json.loads(trace_path.read_text())
        trace_meta = trace.get("metadata", {})
        src = pd.DataFrame(trace["sources"])
        if question == 3:
            fig, (ax0, ax1) = plt.subplots(
                1,
                2,
                figsize=(6.3, 4.2),
                layout="constrained",
                gridspec_kw={"width_ratios": [1.2, 0.8]},
            )
            ax0.set_aspect("equal")
            ax0.add_patch(Circle((0, 0), 1800, fill=False, color=PALETTE["neutral"], ls="--", lw=0.9, label="目标圆域"))
            radius_bins = [
                (0, 1200, PALETTE["primary"], "≤1200 m"),
                (1200, 1400, PALETTE["positive"], "1200–1400 m"),
                (1400, 1801, PALETTE["contrast"], ">1400 m"),
            ]
            for low, high, color, label in radius_bins:
                subset = src[(src.radius > low) & (src.radius <= high)]
                if not subset.empty:
                    ax0.scatter(
                        subset.x,
                        subset.y,
                        color=color,
                        s=50,
                        edgecolors="white",
                        linewidths=0.4,
                        label=label,
                    )
            ax0.scatter([0], [0], marker="+", s=55, color=PALETTE["dark"], label="起点")
            ax0.set_xlim(-1950, 1950)
            ax0.set_ylim(-1950, 1950)
            ax0.set_xlabel("x 坐标 (m)")
            ax0.set_ylabel("y 坐标 (m)")
            ax0.set_title("空间分布", loc="left")
            ax0.legend(frameon=False, fontsize=7, loc="upper left")
            radial_bins = np.linspace(0, 1800, 7)
            ax1.hist(src.radius, bins=radial_bins, orientation="horizontal", color=PALETTE["sky"], edgecolor="white", alpha=0.9)
            ax1.axhline(900, color=PALETTE["contrast"], ls="--", lw=1.0, label="七站证明分界 900 m")
            ax1.set_xlabel("源个数")
            ax1.set_ylabel("源距 (m)")
            ax1.set_title("径向分布", loc="left")
            ax1.grid(axis="x", color="#D9E1E8", lw=0.6, alpha=0.8)
            ax1.legend(frameon=False, fontsize=7, loc="upper right")
            fig.text(0.01, 0.99, "a", ha="left", va="top", fontweight="bold", fontsize=9)
            fig.text(0.58, 0.99, "b", ha="left", va="top", fontweight="bold", fontsize=9)
            save(
                fig,
                "raw_q3_sources",
                "展示首个合成全向场景的空间与径向分布。",
                f"{trace_path.name}；策略={trace_meta.get('strategy', '历史记录')}；仅评价与可视化可读真值",
                f"n={len(src)} 个本地合成源",
            )
        else:
            bearings = []
            seed_rows = runs[
                (runs.question == 4)
                & (runs.stress == "none")
                & (runs.error_mode == "fixed_location")
            ]
            for seed in sorted(seed_rows.seed.unique()):
                bearings.extend(
                    s.orientation
                    for s in generate_sources(int(seed), 4)
                    if s.orientation is not None
                )
            fig, ax = start(True)
            counts, edges = np.histogram(bearings, bins=np.arange(0, 361, 30))
            ax.clear()
            ax.set_aspect("equal")
            ax.set_axis_off()
            max_count = max(int(counts.max()), 1)
            for radius in (0.25, 0.5, 0.75, 1.0):
                ax.add_patch(Circle((0, 0), radius, fill=False, color="#D9E1E8", lw=0.65))
            for angle, count in zip(edges[:-1], counts):
                outer = 0.16 + 0.82 * float(count) / max_count
                ax.add_patch(
                    Wedge(
                        (0, 0),
                        outer,
                        float(angle) - 13,
                        float(angle) + 13,
                        facecolor=PALETTE["primary"],
                        edgecolor="white",
                        linewidth=0.8,
                        alpha=0.84,
                    )
                )
            for angle, label in zip((0, 90, 180, 270), ("0°", "90°", "180°", "270°")):
                theta = np.deg2rad(angle)
                ax.text(1.12 * np.cos(theta), 1.12 * np.sin(theta), label, ha="center", va="center", fontsize=8)
            ax.set_xlim(-1.28, 1.28)
            ax.set_ylim(-1.28, 1.28)
            ax.set_title("定向源发射方向的合成分布", loc="left", pad=12)
            ax.text(
                0.02,
                -0.10,
                f"n={len(bearings)}；30° 分箱",
                transform=ax.transAxes,
                ha="left",
                va="bottom",
                fontsize=8,
                color=PALETTE["neutral"],
            )
            save(
                fig,
                "raw_q4_orientations",
                "说明本地基准场景包含多种定向朝向，不代表官方分布。",
                "固定种子场景；generate_sources 与 runs.csv 对应",
                f"n={len(bearings)} 个合成定向源；30°分箱",
            )
        actions = []
        cleared = []
        for rec in trace["records"]:
            if rec["endpoint"] not in ("/measure", "/clear") or not rec["response"]["accepted"]:
                continue
            p = np.array([rec["request"]["position"][a] for a in ("x", "y")], dtype=float)
            action = {
                "position": p,
                "time": float(rec["response"].get("virtual_time_s", 0.0)),
                "endpoint": rec["endpoint"],
                "result": rec["response"].get("measure_result", rec["response"].get("clear_result", "")),
            }
            actions.append(action)
            if rec["response"].get("clear_result") == "success":
                cleared.append(p)
        positions = [np.zeros(2)] + [item["position"] for item in actions]
        path = np.asarray(positions)
        cleared = np.asarray(cleared).reshape(-1, 2)
        if question in {3, 4}:
            fig, (ax0, ax1) = plt.subplots(
                1,
                2,
                figsize=(6.3, 4.2),
                layout="constrained",
                gridspec_kw={"width_ratios": [1.2, 0.95]},
            )
            for prev, curr, item in zip(path[:-1], path[1:], actions):
                color = PALETTE["primary"] if item["endpoint"] == "/measure" else PALETTE["contrast"]
                ax0.plot([prev[0], curr[0]], [prev[1], curr[1]], color=color, lw=0.65, alpha=0.64)
            ax0.scatter(path[1:, 0], path[1:, 1], s=6, color=PALETTE["primary"], alpha=0.35, label="接受动作点")
            if len(cleared):
                ax0.scatter(cleared[:, 0], cleared[:, 1], s=30, marker="x", color=PALETTE["contrast"], label="成功清除")
            ax0.scatter([0], [0], s=55, marker="*", color=PALETTE["dark"], label="起点")
            ax0.add_patch(Circle((0, 0), 1800, fill=False, color=PALETTE["neutral"], ls="--", lw=0.9, label="源区域边界"))
            ax0.set_aspect("equal")
            ax0.set_xlim(-1950, 1950)
            ax0.set_ylim(-1950, 1950)
            ax0.set_xlabel("x 坐标 (m)")
            ax0.set_ylabel("y 坐标 (m)")
            ax0.set_title("空间轨迹", loc="left")
            ax0.legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(0, 1.02))

            action_index = np.arange(1, len(actions) + 1)
            times = np.asarray([item["time"] for item in actions])
            ax1.step(action_index, times, where="post", color=PALETTE["dark"], lw=1.2, label="累计虚拟时间")
            measure_index = [i + 1 for i, item in enumerate(actions) if item["endpoint"] == "/measure"]
            clear_index = [i + 1 for i, item in enumerate(actions) if item["endpoint"] == "/clear"]
            ax1.scatter(measure_index, times[np.asarray(measure_index) - 1], s=9, color=PALETTE["primary"], alpha=0.55, label="测量动作")
            if clear_index:
                ax1.scatter(clear_index, times[np.asarray(clear_index) - 1], s=18, marker="x", color=PALETTE["contrast"], label="清除动作")
            ax1.set_xlabel("累计接受动作数")
            ax1.set_ylabel("累计虚拟时间 (s)")
            ax1.set_title("动作计时", loc="left")
            ax1.grid(axis="y", color="#D9E1E8", lw=0.6, alpha=0.8)
            ax1.legend(frameon=False, fontsize=7, loc="upper left")
            fig.text(0.01, 0.99, "a", ha="left", va="top", fontweight="bold", fontsize=9)
            fig.text(0.56, 0.99, "b", ha="left", va="top", fontweight="bold", fontsize=9)
        else:
            fig, ax0 = start(True)
            ax0.plot(path[:, 0], path[:, 1], color=PALETTE["primary"], lw=0.8, label="实际动作轨迹")
            if len(cleared):
                ax0.scatter(cleared[:, 0], cleared[:, 1], s=27, marker="x", color=PALETTE["contrast"], label="成功清除点")
            ax0.scatter([0], [0], s=50, marker="*", color=PALETTE["dark"], label="起点")
            ax0.add_patch(Circle((0, 0), 1800, fill=False, color=PALETTE["neutral"], ls="--"))
            ax0.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
        save(
            fig,
            f"process_q{question}_trajectory",
            "完整日志复现搜索、定位和清除移动过程，并展示累计虚拟时间。",
            f"{trace_path.name}；策略={trace_meta.get('strategy', '历史记录')}；种子20260911；重复坐标仅在画线时合并",
        )
        if question == 3:
            comparison_path = args.results / "q3_strategy_comparison" / "runs.csv"
            comparison = pd.read_csv(comparison_path) if comparison_path.exists() else runs
            base = comparison[
                (comparison.question == question)
                & (comparison.get("stress", "none") == "none")
                & (comparison.get("error_mode", "fixed_location") == "fixed_location")
            ]
            pair = base.pivot(index="seed", columns="strategy", values="mean_clear_time_s")
            pair = pair[["adaptive", "adaptive_q10_dynamic"]].dropna()
        else:
            base = runs[
                (runs.question == question)
                & (runs.stress == "none")
                & (runs.error_mode == "fixed_location")
            ]
            pair = base.pivot(index="seed", columns="strategy", values="mean_clear_time_s")
        fig, ax = start()
        if question == 3:
            fig, (ax0, ax1) = plt.subplots(
                1,
                2,
                figsize=(6.3, 4.2),
                layout="constrained",
                gridspec_kw={"width_ratios": [1.15, 0.85]},
            )
            ax0.scatter(pair.adaptive, pair.adaptive_q10_dynamic, s=29, color=PALETTE["primary"], alpha=0.82, edgecolors="white", linewidths=0.35)
            bounds = [float(pair.min().min() * 0.96), float(pair.max().max() * 1.04)]
            ax0.plot(bounds, bounds, "--", color=PALETTE["neutral"], lw=1.0, label="两策略相等")
            ax0.set_xlabel("adaptive：平均时间 (s/源)")
            ax0.set_ylabel("adaptive_q10_dynamic：平均时间 (s/源)")
            ax0.set_title("逐局配对", loc="left")
            ax0.legend(frameon=False, loc="upper left")
            delta = pair.adaptive_q10_dynamic - pair.adaptive
            ax1.hist(delta, bins=7, color=PALETTE["sky"], edgecolor="white", alpha=0.9)
            ax1.axvline(0, color=PALETTE["contrast"], ls="--", lw=1.0)
            ax1.axvline(delta.mean(), color=PALETTE["dark"], lw=1.1, label=f"均值 {delta.mean():.1f}")
            ax1.set_xlabel("q10_dynamic − adaptive (s/源)")
            ax1.set_ylabel("种子数")
            ax1.set_title("差值分布", loc="left")
            ax1.legend(frameon=False, fontsize=7, loc="upper left")
            ax1.grid(axis="y", color="#D9E1E8", lw=0.6, alpha=0.8)
            fig.text(0.01, 0.99, "a", ha="left", va="top", fontweight="bold", fontsize=9)
            fig.text(0.58, 0.99, "b", ha="left", va="top", fontweight="bold", fontsize=9)
            save(
                fig,
                "result_q3_paired",
                "同一合成场景内对比 adaptive 与动态 q10 站点次序的耗时及逐局差值。",
                "q3_strategy_comparison/runs.csv；q3 非压力场景配对",
                f"n={len(pair)} 个种子；每点一对完整运行；未做显著性检验",
            )
        else:
            values = [pair.fixed.to_numpy(), pair.adaptive.to_numpy()]
            ax.boxplot(
                values, tick_labels=["固定站次序", "动态站次序"], showfliers=False, widths=0.4
            )
            rng = np.random.default_rng(903)
            for i, vals in enumerate(values):
                ax.scatter(
                    i + 1 + rng.uniform(-0.09, 0.09, len(vals)),
                    vals,
                    s=20,
                    alpha=0.65,
                    color=[PALETTE["neutral"], PALETTE["primary"]][i],
                )
            ax.set_xlabel("站点访问策略")
            ax.set_ylabel("平均定位清除时间 (s/源)")
            save(
                fig,
                "result_q4_time",
                "展示定向混合场景耗时的完整分布与不稳定性。",
                "runs.csv；q4非压力场景配对",
                f"每组n={len(pair)}；箱体IQR、中位数线、1.5IQR须、叠加全部原始点；未做显著性检验",
            )
    points, cells = ring25_cover()
    route_points = q4_station_route(points)
    fig, ax = start(True)
    for i, tri in enumerate(cells):
        ax.add_patch(
            Polygon(
                tri,
                closed=True,
                facecolor=PALETTE["sky"] if i < 24 else "#E7EEF3",
                alpha=0.22,
                edgecolor=PALETTE["sky"],
                lw=0.55,
            )
        )
    ax.add_patch(
        Circle((0, 0), 1800, fill=False, color=PALETTE["dark"], ls="--", lw=1.1, label="源区域边界")
    )
    ax.plot(route_points[:, 0], route_points[:, 1], color=PALETTE["primary"], lw=1.4, alpha=0.9, label="开放访问路线")
    ax.scatter(points[1:17, 0], points[1:17, 1], s=25, color=PALETTE["primary"], label="外环站（16）")
    ax.scatter(points[17:, 0], points[17:, 1], s=25, color=PALETTE["contrast"], label="内环站（8）")
    ax.scatter([0], [0], s=80, marker="*", color=PALETTE["dark"], label="起点站")
    for i, p in enumerate(route_points):
        if i == 0 or i in {1, 8, 9, 16, 24}:
            ax.annotate(str(i + 1), p, xytext=(4, 4), textcoords="offset points", fontsize=8, color=PALETTE["dark"])
    ax.set_xlim(-2050, 2050)
    ax.set_ylim(-2050, 2050)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=2, frameon=False)
    save(
        fig,
        "process_q4_coverage",
                "展示25站同心环三角覆盖与固定访问路线；相对26站的路程改进由配对实验核验。",
        "ring25_cover 确定性构造：32个三角形，25站；路线为离线固定的开放路径",
    )
    grid = pd.read_csv(args.results / "coverage_comparison.csv")
    paired = grid.pivot(index="seed", columns="coverage", values="mean_clear_time_s")
    fig, ax = start()
    ax.scatter(paired.square, paired.triangular, s=25, color=PALETTE["primary"])
    bounds = [min(paired.min()) * 0.9, max(paired.max()) * 1.05]
    ax.plot(bounds, bounds, "--", color=PALETTE["neutral"], label="两覆盖方案相等")
    ax.set_xlabel("49站方格：平均清除时间 (s/源)")
    ax.set_ylabel("28站三角网格：平均清除时间 (s/源)")
    ax.legend()
    save(
        fig,
        "result_q4_coverage",
        "相同源配置和动态调度下比较覆盖构造的实测耗时。",
        "coverage_comparison.csv；相同20个合成种子，定位器和兜底相同",
        f"n={len(paired)} 对完整运行；未做显著性检验",
    )
    ring_runs_path = args.results / "q4_optimization_ring25" / "runs.csv"
    if ring_runs_path.is_file():
        ring_runs = pd.read_csv(ring_runs_path)
        ring_pair = ring_runs.pivot(index="seed", columns="variant", values="mean_clear_time_s")
        fig, ax = start()
        ax.scatter(
            ring_pair["optimized_q4_joint"],
            ring_pair["ring25_q4_joint"],
            s=26,
            color=PALETTE["primary"],
            alpha=0.82,
            edgecolors="white",
            linewidths=0.35,
        )
        values = ring_pair[["optimized_q4_joint", "ring25_q4_joint"]].to_numpy().ravel()
        bounds = [float(values.min() * 0.95), float(values.max() * 1.08)]
        ax.plot(bounds, bounds, "--", color=PALETTE["neutral"], lw=1.0, label="两方案相等")
        reduction = 100 * (1 - ring_pair["ring25_q4_joint"].mean() / ring_pair["optimized_q4_joint"].mean())
        wins = int((ring_pair["ring25_q4_joint"] < ring_pair["optimized_q4_joint"]).sum())
        ax.text(
            0.04,
            0.95,
            f"环形方案均值降低 {reduction:.2f}%\n{wins}/{len(ring_pair)} 个种子更快",
            transform=ax.transAxes,
            va="top",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82},
        )
        ax.set_xlabel("26站三角联合：平均清除时间 (s/源)")
        ax.set_ylabel("25站环形联合：平均清除时间 (s/源)")
        ax.legend(loc="lower right", frameon=False)
        save(
            fig,
            "result_q4_ring25",
            "相同源配置下，25站环形联合策略在多数种子中更快。",
            "q4_optimization_ring25/runs.csv；50个共同种子",
            "每点为一对完整本地合成运行；虚线为相等线；未做显著性检验",
        )
    (args.out / "图表契约.json").write_text(
        json.dumps(contracts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    captions = [
        "# 候选图说明\n\n全部为本地合成/构造结果，不能标注为官方测试。PNG为300 DPI，SVG文字可编辑，物理尺寸6.3×4.2英寸。\n"
    ]
    for c in contracts:
        captions.append(
            f"## {c['name']}\n\n{c['claim']} 数据：{c['source']}。统计口径：{c['statistics']}。\n"
        )
    (args.out / "图注.md").write_text("\n".join(captions), encoding="utf-8")
    html = '<!doctype html><html lang="zh"><meta charset="utf-8"><title>B题本地实验候选图</title><style>body{font:16px sans-serif;margin:32px;max-width:1100px}img{width:100%;max-width:900px}section{margin-bottom:44px}small{color:#555}</style><h1>B题本地实验候选图</h1><p>以下均非官方测试。请结合模型报告与CSV核验。</p>'
    for c in contracts:
        html += f'<section><h2>{c["name"]}</h2><p>{c["claim"]}</p><img src="{c["name"]}.png"><p><small>{c["source"]}；{c["statistics"]}</small></p></section>'
    (args.out / "图表面板.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
