import pandas
import numpy
import functools
import collections
from typing import Mapping, Callable
from util import flatten1


rel_qois = ["cputime", "walltime", "memory"]
abs_qois = ["storage", "n_ops", "n_unique_files"]


def performance(df: pandas.DataFrame) -> None:
    print(
        df
        .groupby(["workload", "collector"], as_index=True, observed=True)
        .agg(**{
            qoi + "_abs_mean": pandas.NamedAgg(
                column=qoi,
                aggfunc="mean",
            )
            for qoi in rel_qois + abs_qois
        })
        .drop(["cputime_abs_mean", "memory_abs_mean", "n_unique_files_abs_mean"], axis=1)
        .rename(columns={
            "walltime_abs_mean": "Walltime (sec)",
            # "memory_abs_mean": "Memory (MiB)",
            "storage_abs_mean": "Storage (MiB)",
            "n_ops_abs_mean": "Prov Ops (K Ops)",
            # "n_unique_files_abs_mean": "Unique files",
        }).to_string(formatters={
            "Walltime (sec)": lambda val: f"{val:.1f}",
            "Memory (MiB)": lambda val: f"{val / 1024**2:.1f}",
            "Storage (MiB)": lambda val: f"{val / 1024**2:.1f}",
            "Prov Ops (K Ops)": lambda val: f"{val / 1e3:.1f}",
            "Unique files": lambda val: f"{val:.0f}",
        })
    )


def op_freqs(df: pandas.DataFrame) -> None:
    print((
        df
        .drop(["workload", "collector_method", "collector_submethod", "workload_kind"] + rel_qois + abs_qois, axis=1)
        .groupby("collector", observed=True)
        .agg(**{
            "op_count_pairs": pandas.NamedAgg(
                column="operations",
                aggfunc=lambda opss: collections.Counter(op.type for ops in opss for op in ops).most_common(),
            ),
        })
        .explode("op_count_pairs")
        .loc[lambda df: ~pandas.isna(df.op_count_pairs)]
        .assign(**{
            "op_type"  : lambda df: [pair[0] for pair in df.op_count_pairs],
            "op_counts": lambda df: [pair[1] for pair in df.op_count_pairs],
        })
        .drop(["op_count_pairs"], axis=1)
    ).to_string())


@functools.cache
def _workload_baseline(df: pandas.DataFrame, workload: str, qoi: str) -> float:
    return numpy.median(
        df[(df["workload"] == workload) & (df["collector"] == "noprov")][qoi]
    )


def relative_performance(df: pandas.DataFrame):
    for qoi in ["walltime"]:
        collectors = sorted(
            df.collector.cat.categories,
            key=lambda collector: numpy.mean([
                df[(df["workload"] == workload) & (df["collector"] == collector)][qoi]
                for workload in df.workload.cat.categories
            ])
        )
        for collector in collectors:
            print(f"{collector:10s}", end=" ")
            for rank in [5, 50, 95]:
                value = numpy.mean([
                    numpy.percentile(
                        df[(df["workload"] == workload) & (df["collector"] == collector)][qoi],
                        rank,
                    ) / _workload_baseline(df, workload, qoi)
                    for workload in df.workload.cat.categories
                ])
                print(f"{value:4.2f}", end=" ")
            print()

    import matplotlib.figure
    fig = matplotlib.figure.Figure()
    ax = fig.add_subplot(1, 1, 1)
    mat = numpy.array([
        list(flatten1(
            sorted(df[(df["workload"] == workload) & (df["collector"] == collector)]["walltime"] / _workload_baseline(df, workload, "walltime"))
            for collector in collectors
        ))
        for workload in df.workload.cat.categories
    ])
    ax.matshow(mat, vmin=numpy.log(1), vmax=numpy.log(12))
    print(len(df))
    n_samples = len(df) // len(df.workload.cat.categories) // len(df.collector.cat.categories)
    ax.set_xticks(
        ticks=range(0, len(collectors) * n_samples, n_samples),
        labels=[f"{collector}" for collector in collectors],
        rotation=90,
    )
    ax.set_yticks(
        ticks=range(len(df.workload.cat.categories)),
        labels=[
            workload
            for workload in df.workload.cat.categories
        ],
    )
    fig.savefig("output/matrix.png")


stats_list: list[Callable[[pandas.DataFrame], None]] = [
    performance,
    op_freqs,
    relative_performance,
]


STATS: Mapping[str, Callable[[pandas.DataFrame], None]] = {
    stat.__name__: stat
    for stat in stats_list
}
