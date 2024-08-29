import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import io
from PIL import Image
import weave

matplotlib.use("agg")


@weave.op(render_info={"type": "function"})
def histogram(
    val_series: list[list[float]],
    bin_size: float = 1.0,
    chart_title: str = "Composite Histogram",
    series_names: list[str] = [],
) -> Image.Image:
    """Generate a composite histogram from one or more series of float values provided, using the same bins.
    Return a static image of the result"""
    # TODO: make an even better default x-axis?
    # TODO: check that this will work for e.g. runs.history.accuracy
    #       "displaying the first 10 runs"  in weave.js, vals needs to be at least 2 and no more than 10
    # wouldn't be TYPE ASSIGNABLE
    # TODO: render as a model card/pretty panel...?
    # compute range for values

    fig, ax = plt.subplots(figsize=(15, 5))

    min_val = np.min([np.min(val_list) for val_list in val_series])
    max_val = np.max([np.max(val_list) for val_list in val_series])

    # generate bins across the full value range, where each bin has size bin_size
    bins = np.arange(min_val - bin_size, max_val + bin_size, step=bin_size)
    num_bins = len(bins)

    kwargs = {"edgecolor": "black"}

    num_series = len(val_series)
    # if no names are provided for the series, name each according to its index in the list
    if not series_names:
        series_names = [str(i) for i in range(num_series)]

    # improve color settings for the base cases of 1 or 2 series
    # TODO: I tried manual tuning for 3 series, r/c/b and r/b/m are both not great without hover interaction
    default_colors = {1: ["b"], 2: ["r", "b"]}
    # distribute series evenly across the hue spectrum
    color_map = plt.get_cmap("hsv")
    scale_color = lambda val_id: val_id / len(val_series)

    for series_id, vals in enumerate(val_series):
        curr_color = (
            default_colors[num_series][series_id]
            if num_series < 3
            else color_map(scale_color(series_id))
        )
        ax.hist(
            vals,
            bins,
            alpha=0.5,
            label=series_names[series_id],
            color=curr_color,
            **kwargs
        )

    ax.set_xticks(np.arange(min_val - bin_size, max_val + bin_size, bin_size))
    ax.set_xlim([min_val - bin_size, max_val + bin_size])
    # TODO: may want to improve y-axis as well?
    ax.legend()

    ax.set_xlabel("Values Across Series")
    ax.set_ylabel("Value Count")
    ax.set_title(chart_title)

    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png")
    im = Image.open(img_buf)
    plt.close(fig)
    return im
