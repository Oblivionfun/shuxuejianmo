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
from matplotlib.patches import Circle, Polygon
from matplotlib.colors import LogNorm
from quality_tools import load_tool
from cumcm_b.geometry import unit, Belief
from cumcm_b.synthetic import generate_sources
from cumcm_b.policy import triangular_cover

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
        contracts.append(
            {
                "name": name,
                "claim": claim,
                "source": source,
                "statistics": stat,
                "size_inches": [6.3, 4.2],
                "dpi": 300,
                "origin": "本地合成或构造数据，非官方测试",
                "layout": "single quantitative panel",
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
    fig, ax = start()
    ax.plot(
        [h["observations"] for h in b.history],
        [h["area_m2"] for h in b.history],
        "-o",
        color=PALETTE["primary"],
    )
    ax.set_yscale("log")
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("累计检测点数")
    ax.set_ylabel("外包定位区域面积 (m²，对数轴)")
    save(
        fig,
        "process_q1_intersection",
        "逐次增加测向约束压缩可行外包。",
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

    fig, ax = start()
    sub = val[val.travel_weight == 0.02].copy()
    ax.scatter(
        sub.source_range_m,
        sub.posterior_radius_m,
        s=23,
        alpha=0.65,
        color=PALETTE["primary"],
        label="后验最小包围半径",
    )
    ax.axhline(20, color=PALETTE["contrast"], ls="--", label="光学清除半径20 m")
    ax.set_xlabel("构造真位置距首测点 (m)")
    ax.set_ylabel("后验包围半径 (m)")
    ax.legend()
    save(
        fig,
        "result_q2_posterior",
        "精确后验半径随真位置和两次误差变化，选点代理不等于保证。",
        "q2_validation.csv；λ=0.02",
        "6个距离×3个首次误差×3个第二次误差=54个确定性组合；散点重合未抖动",
    )

    runs = pd.read_csv(args.results / "runs.csv")
    for question in (3, 4):
        trace = json.loads((args.results / f"q{question}_trace.json").read_text())
        src = pd.DataFrame(trace["sources"])
        if question == 3:
            fig, ax = start(True)
            ax.add_patch(Circle((0, 0), 1800, fill=False, color=PALETTE["neutral"], ls="--"))
            ax.scatter(src.x, src.y, s=40, color=PALETTE["primary"])
            ax.set_xlim(-1950, 1950)
            ax.set_ylim(-1950, 1950)
            save(
                fig,
                "raw_q3_sources",
                "展示首个合成全向场景的源空间分布。",
                "q3_trace.json；仅评价与可视化可读真值",
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
            fig, ax = start()
            ax.hist(
                bearings, bins=np.arange(0, 361, 30), color=PALETTE["primary"], edgecolor="white"
            )
            ax.set_xlabel("合成定向源发射方向 (°)")
            ax.set_ylabel("定向源个数")
            ax.set_xticks([0, 90, 180, 270, 360])
            save(
                fig,
                "raw_q4_orientations",
                "说明本地基准场景包含多种定向朝向，不代表官方分布。",
                "固定种子场景；generate_sources 与 runs.csv 对应",
                f"n={len(bearings)} 个合成定向源；30°分箱",
            )
        fig, ax = start(True)
        positions = [np.zeros(2)]
        cleared = []
        for rec in trace["records"]:
            if rec["endpoint"] in ("/measure", "/clear") and rec["response"]["accepted"]:
                p = np.array([rec["request"]["position"][a] for a in ("x", "y")])
                if np.linalg.norm(p - positions[-1]) > 1e-8:
                    positions.append(p)
                if rec["response"].get("clear_result") == "success":
                    cleared.append(p)
        path = np.array(positions)
        cleared = np.array(cleared)
        ax.plot(path[:, 0], path[:, 1], color=PALETTE["primary"], lw=0.8, label="实际动作轨迹")
        ax.scatter(
            cleared[:, 0],
            cleared[:, 1],
            s=27,
            marker="x",
            color=PALETTE["contrast"],
            label="成功清除点",
        )
        ax.scatter([0], [0], s=50, marker="*", color=PALETTE["dark"], label="起点")
        ax.add_patch(Circle((0, 0), 1800, fill=False, color=PALETTE["neutral"], ls="--"))
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
        save(
            fig,
            f"process_q{question}_trajectory",
            "完整日志复现搜索、定位和清除移动过程。",
            f"q{question}_trace.json；种子20260911；重复坐标仅在画线时合并",
        )
        base = runs[
            (runs.question == question)
            & (runs.stress == "none")
            & (runs.error_mode == "fixed_location")
        ]
        pair = base.pivot(index="seed", columns="strategy", values="mean_clear_time_s")
        fig, ax = start()
        if question == 3:
            ax.scatter(pair.fixed, pair.adaptive, s=25, color=PALETTE["primary"])
            bounds = [min(pair.min()) * 0.9, max(pair.max()) * 1.05]
            ax.plot(bounds, bounds, "--", color=PALETTE["neutral"], label="两策略相等")
            ax.set_xlabel("固定站次序：平均清除时间 (s/源)")
            ax.set_ylabel("动态站次序：平均清除时间 (s/源)")
            ax.legend()
            save(
                fig,
                "result_q3_paired",
                "同一合成场景内对比两种站点访问次序的耗时。",
                "runs.csv；q3非压力场景配对",
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
    points, cells = triangular_cover()
    fig, ax = start(True)
    for tri in cells:
        ax.add_patch(Polygon(tri, closed=True, fill=False, edgecolor=PALETTE["sky"], lw=0.6))
    ax.add_patch(
        Circle((0, 0), 1800, fill=False, color=PALETTE["dark"], ls="--", label="源区域边界")
    )
    ax.scatter(points[1:, 0], points[1:, 1], s=24, color=PALETTE["primary"], label="27个网格站")
    ax.scatter([0], [0], s=70, marker="*", color=PALETTE["contrast"], label="起点站")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.14), ncol=3)
    save(
        fig,
        "process_q4_coverage",
        "相交闭三角形的顶点提供任意方向覆盖证书。",
        "triangular_cover 确定性构造：边长950 m，37个三角形，28站",
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
