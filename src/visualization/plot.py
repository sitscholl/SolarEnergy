import matplotlib.pyplot as plt
from io import BytesIO
import base64

def encode_plot(fig):
    img = BytesIO()

    fig.savefig(img, format='png', dpi = 300)
    #fig.close()
    img.seek(0)
    return(base64.b64encode(img.getvalue()).decode('utf8'))

def optim_lines(optim_tbl, observed_tbl, st_id, t_opt, d_opt):
    fig, ax = plt.subplots()
    station_tbl = optim_tbl.loc[
        st_id, ["transmittivity", "diffuse_proportion", "global_ave", "rmse"]
    ]
    for (tr, di), data in station_tbl.groupby(["transmittivity", "diffuse_proportion"]):
        rmse = data["rmse"].unique()[0]
        ax.plot(data.index, data["global_ave"], alpha=0.5)
    ax.plot(
        observed_tbl.loc[st_id].index,
        observed_tbl.loc[st_id],
        label="Observed",
        color="black",
        lw=2,
    )
    best_tbl = optim_tbl.loc[
        (optim_tbl.index.get_level_values(0) == st_id)
        & (optim_tbl["transmittivity"] == t_opt)
        & (optim_tbl["diffuse_proportion"] == d_opt)
    ]
    ax.plot(
        best_tbl.index.get_level_values(1),
        best_tbl["global_ave"],
        label="Optimized",
        color="red",
        lw=2,
    )
    plt.legend()
    return(fig)
