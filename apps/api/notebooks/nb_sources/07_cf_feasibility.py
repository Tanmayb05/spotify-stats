# %% [markdown]
# # 07 · Collaborative filtering feasibility at n=10
#
# **Question:** can collaborative filtering work with ten users — and if not,
# how much weight should the hybrid give the user-similarity term?
#
# **Feeds:** Phase 15's decision to build (or not build) Model 2, and the
# hybrid's **β** weight (`reco/config.py`, default 0.15).
#
# This is a **reality check run before writing the model**, which is the cheap
# order. CF's whole premise is that other users' histories inform yours. With ten
# users that premise is under strain, and the question is whether there is enough
# item overlap between people to learn anything.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _common as C

USERS = None
SINCE = None

C.use_style()
DB = C.db_available()

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()

# %% [markdown]
# ## The user × item matrix
#
# Built on `track_key` (normalised), because CF asks "is this the same track",
# not "how was it displayed".

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    ui = (
        fact.groupby(["user", "track_key"]).size().rename("plays").reset_index()
    )
    n_users = ui["user"].nunique()
    n_items = ui["track_key"].nunique()
    nnz = len(ui)
    density = nnz / (n_users * n_items)

    print(f"users           : {n_users}")
    print(f"distinct tracks : {n_items:,}")
    print(f"non-zero cells  : {nnz:,}")
    print(f"density         : {density:.2%}  ({nnz:,} of {n_users * n_items:,} cells)")
    print(f"sparsity        : {1 - density:.2%}")
    print(
        "\nDensity looks high only because there are 10 rows: with so few users a\n"
        "matrix is 'dense' while still carrying almost no collaborative signal.\n"
        "The number that matters is item overlap, below — not this one."
    )

# %% [markdown]
# ## Item overlap — the number that decides it
#
# A track played by exactly one user contributes nothing to CF: there is no
# second user whose taste it can connect to. The share of plays landing on
# such tracks is the ceiling on how much CF can possibly help.

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    per_track_users = ui.groupby("track_key")["user"].nunique()
    dist = per_track_users.value_counts().sort_index()

    print("tracks by number of distinct listeners:")
    for k, v in dist.items():
        print(f"  {k:>2} listener(s): {v:>7,} tracks ({v / n_items:.1%})")

    shared = per_track_users[per_track_users >= 2].index
    plays_on_shared = ui[ui["track_key"].isin(shared)]["plays"].sum()
    total_plays = ui["plays"].sum()

    print(f"\ntracks with >= 2 listeners : {len(shared):,} of {n_items:,} "
          f"({len(shared) / n_items:.1%})")
    print(f"plays on those tracks      : {plays_on_shared:,} of {total_plays:,} "
          f"({plays_on_shared / total_plays:.1%})")
    print(f"cold-start mass (1 listener only): "
          f"{1 - plays_on_shared / total_plays:.1%} of plays")

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(dist.index, dist.to_numpy(), color=C.SERIES_COLORS[0])
    ax.set_yscale("log")
    ax.set_xlabel("distinct listeners for a track")
    ax.set_ylabel("tracks (log)")
    ax.set_xticks(dist.index)
    ax.set_title("Item overlap across users — CF has only the right-hand bars to work with")
    C.save_fig("07_item_overlap", aggregate=True)
    plt.show()

# %% [markdown]
# ## Pairwise user similarity
#
# How much do any two people actually share? Jaccard over track sets, plus the
# raw count of co-played tracks — a high Jaccard on tiny sets would be noise.

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    track_sets = {u: set(g["track_key"]) for u, g in ui.groupby("user")}
    users_sorted = sorted(track_sets)

    jac = pd.DataFrame(index=users_sorted, columns=users_sorted, dtype=float)
    overlap = pd.DataFrame(index=users_sorted, columns=users_sorted, dtype=float)
    for a in users_sorted:
        for b in users_sorted:
            inter = len(track_sets[a] & track_sets[b])
            union = len(track_sets[a] | track_sets[b])
            jac.loc[a, b] = inter / union if union else 0.0
            overlap.loc[a, b] = inter

    off = ~np.eye(len(users_sorted), dtype=bool)
    print(f"pairwise Jaccard  : mean={jac.to_numpy()[off].mean():.4f}  "
          f"max={jac.to_numpy()[off].max():.4f}")
    print(f"co-played tracks  : median={np.median(overlap.to_numpy()[off]):.0f}  "
          f"max={overlap.to_numpy()[off].max():.0f}")
    print("\nJaccard matrix:")
    print(jac.round(3).to_string())

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    fig, ax = plt.subplots(figsize=(7, 5.5))
    im = ax.imshow(jac.to_numpy(dtype=float), cmap="viridis")
    ax.set_xticks(range(len(users_sorted)))
    ax.set_xticklabels(users_sorted, rotation=90)
    ax.set_yticks(range(len(users_sorted)))
    ax.set_yticklabels(users_sorted)
    ax.set_title("Pairwise track-set Jaccard")
    fig.colorbar(im, ax=ax)
    C.save_fig("07_user_similarity", aggregate=True)
    plt.show()

# %% [markdown]
# ## What could CF actually recommend?
#
# For each user, the reachable set is tracks that *someone else* played and they
# did not. Its size is the real ceiling on CF's candidate supply.

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    rows = []
    for u in users_sorted:
        mine = track_sets[u]
        others = set().union(*(track_sets[o] for o in users_sorted if o != u))
        rows.append({
            "user": u,
            "own_tracks": len(mine),
            "reachable_via_others": len(others - mine),
            "shared_with_others": len(mine & others),
            "share_of_own_shared": len(mine & others) / len(mine) if mine else 0.0,
        })
    reach = pd.DataFrame(rows).set_index("user")
    print(reach.round(3).to_string())

# %% [markdown]
# ## Verdict and a β proposal
#
# β is the hybrid's weight on user-similarity. It should scale with how much
# signal the user-similarity term actually carries.

# %%
BETA_DEFAULT = 0.15  # roadmap default in reco/config.py

if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    shared_play_share = plays_on_shared / total_plays
    mean_jac = float(jac.to_numpy()[off].mean())

    # Two independent conditions. Play mass says "is there anything to learn
    # from"; Jaccard says "are any two users actually alike". Both must hold
    # before CF deserves more weight than the roadmap default.
    if shared_play_share >= 0.5 and mean_jac >= 0.15:
        verdict, beta = "CF viable — users genuinely overlap", 0.25
    elif shared_play_share >= 0.5:
        verdict = (
            "CF usable on shared items, but users are weakly alike "
            f"(mean Jaccard {mean_jac:.3f}) — keep the roadmap default"
        )
        beta = 0.15
    elif shared_play_share >= 0.25:
        verdict, beta = "CF marginal — keep as a weak signal", 0.10
    else:
        verdict, beta = "CF weak — down-weight, report the ceiling honestly", 0.05

    print(f"plays on multi-listener tracks : {shared_play_share:.1%}")
    print(f"mean pairwise Jaccard          : {mean_jac:.4f}")
    print(f"\nVERDICT: {verdict}")
    print(f"proposed beta: {beta}  (roadmap default {BETA_DEFAULT})")
    print(
        "\nPhase 15 must still BUILD Model 2 — the n=10 ceiling is a finding to\n"
        "report (experiment E2 asks 'does CF help at n=10?'), not a reason to\n"
        "skip the model. This notebook sets the expectation before the work."
    )

# %% [markdown]
# ## Decision inputs

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    C.decision(
        feeds="P15 Model 2 (implicit ALS) expectations + hybrid beta weight",
        users=int(n_users),
        distinct_tracks=int(n_items),
        matrix_density=float(density),
        tracks_with_multiple_listeners=int(len(shared)),
        share_of_tracks_multi_listener=float(len(shared) / n_items),
        share_of_plays_on_multi_listener_tracks=float(shared_play_share),
        cold_start_play_mass=float(1 - shared_play_share),
        mean_pairwise_jaccard=mean_jac,
        max_pairwise_jaccard=float(jac.to_numpy()[off].max()),
        median_reachable_tracks_via_others=float(
            reach["reachable_via_others"].median()
        ),
        verdict=verdict,
        proposed_beta=beta,
        roadmap_default_beta=BETA_DEFAULT,
    )
