#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stray Dogs per 1000 People — India (2019)
- Downloads DAHD district-wise stray dog counts (20th LC, 2019)
- Aggregates to State/UT level
- Merges with 2019 population projections (MoHFW 2011–2036 report)
- Produces a choropleth map like the shared image

Outputs:
  outputs/stray_dogs_per_1000_2019.csv
  outputs/stray_dogs_per_1000_2019.png
"""
import io
import os
import sys
import json
import math
import time
import zipfile
import warnings
import tempfile
from pathlib import Path

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects
from matplotlib.colors import Normalize
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
import requests

OUTDIR = Path("outputs")
DATADIR = Path("data")
OUTDIR.mkdir(exist_ok=True, parents=True)
DATADIR.mkdir(exist_ok=True, parents=True)

# URLs (official / community)
DAHD_XLSX_URL = "https://dahd.gov.in/sites/default/files/2023-11/FinalDistrictWiseStrayCattleDog.xlsx"
# Data{Meet} states repository (GeoJSON)
STATE_GEOJSON_URL = "https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson"
# Population projections PDF (reference only); parsing is optional/hard — we ship a fallback CSV
POP_PROJ_PDF_URL = "https://nhm.gov.in/New_Updates_2018/Report_Population_Population_2019.pdf"

# Fallback MoHFW-based 2019 projection CSV included in data/
POP_FALLBACK_CSV = DATADIR / "pop_projection_2019.csv"

# Simple state name resolver to align across sources
NAME_MAP = {
	"nct of delhi": "Delhi",
	"delhi": "Delhi",
	"andaman & nicobar islands": "Andaman & Nicobar Islands",
	"andaman and nicobar islands": "Andaman & Nicobar Islands",
	"dadra & nagar haveli": "Dadra & Nagar Haveli and Daman & Diu",
	"dadra and nagar haveli": "Dadra & Nagar Haveli and Daman & Diu",
	"daman & diu": "Dadra & Nagar Haveli and Daman & Diu",
	"daman and diu": "Dadra & Nagar Haveli and Daman & Diu",
	"dadra & nagar haveli and daman & diu": "Dadra & Nagar Haveli and Daman & Diu",
	"dnh & dd": "Dadra & Nagar Haveli and Daman & Diu",
	"dnh and dd": "Dadra & Nagar Haveli and Daman & Diu",
	"odisha": "Odisha",
	"orissa": "Odisha",
	"jk": "Jammu & Kashmir",
	"jammu and kashmir": "Jammu & Kashmir",
	"jammu & kashmir": "Jammu & Kashmir",
	"uttaranchal": "Uttarakhand",
	"pondicherry": "Puducherry",
	"chattisgarh": "Chhattisgarh",
	"cg": "Chhattisgarh",
	"andhra pradesh": "Andhra Pradesh",
	"telangana": "Telangana",
	"sikkim": "Sikkim",
	"mizoram": "Mizoram",
	"meghalaya": "Meghalaya",
	"nagaland": "Nagaland",
	"manipur": "Manipur",
	"arunachal pradesh": "Arunachal Pradesh",
}

def std_name(x: str) -> str:
    if not isinstance(x, str):
        return x
    s = x.strip().lower().replace(".", "")
    s = s.replace(" union territory", "").replace("(ut)", "").strip()
    return NAME_MAP.get(s, s.title())

def download(url: str, dest: Path):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest

def load_dahd():
    xlsx_path = DATADIR / "FinalDistrictWiseStrayCattleDog.xlsx"
    if not xlsx_path.exists():
        print(f"Downloading DAHD stray dogs Excel -> {xlsx_path}")
        download(DAHD_XLSX_URL, xlsx_path)
    # The Excel has multiple sheets; look for the one with district-wise figures
    # Try reading all sheets and pick the one having 'Stray Dog' column.
    xls = pd.ExcelFile(xlsx_path)
    chosen = None
    for sh in xls.sheet_names:
        df = xls.parse(sh)
        cols = [str(c).strip().lower() for c in df.columns]
        if any(("dog" in c and "stray" in c) for c in cols):
            chosen = sh
            break
    if chosen is None:
        # fallback: just take first sheet
        chosen = xls.sheet_names[0]
    df = xls.parse(chosen)
    # try to locate columns
    df.columns = [str(c).strip() for c in df.columns]

    # Build a known state set from population CSV if available
    known_states = set()
    try:
        pop_ref = pd.read_csv(POP_FALLBACK_CSV)
        known_states = set(pop_ref["state"].apply(std_name).astype(str).unique())
    except Exception:
        pass

    def is_mostly_numeric(series: pd.Series) -> float:
        non_null = series.dropna()
        if non_null.empty:
            return 0.0
        numeric = pd.to_numeric(non_null.astype(str).str.replace(",", ""), errors="coerce").notna()
        return float(numeric.sum()) / float(len(non_null))

    # Choose state column via scoring
    best_state_col = None
    best_score = -1.0
    for c in df.columns:
        ser = df[c]
        # Skip if column is mostly numeric (likely codes or totals)
        numeric_ratio = is_mostly_numeric(ser)
        if numeric_ratio > 0.3:
            continue
        # Score by match to known states
        sample = ser.dropna().astype(str).head(300)
        std_vals = sample.apply(std_name).astype(str)
        match_ratio = 0.0
        if known_states:
            matches = std_vals.isin(known_states).sum()
            match_ratio = matches / max(1, len(std_vals))
        # Name-based clues
        name = c.lower()
        name_bonus = 0.0
        if "state" in name or "state/ut" in name or "state - ut" in name or ("ut" in name and "district" not in name):
            name_bonus += 0.3
        if "district" in name:
            name_bonus -= 0.5
        score = match_ratio + name_bonus
        if score > best_score:
            best_score = score
            best_state_col = c

    # Fallback heuristics if scoring failed
    st_col = best_state_col
    if st_col is None or best_score < 0.2:
        possible_state = [c for c in df.columns if "state" in c.lower()]
        possible_ut = [c for c in df.columns if "ut" in c.lower() and "district" not in c.lower()]
        possible_district = [c for c in df.columns if "district" in c.lower()]
        st_col = possible_state[0] if possible_state else (possible_ut[0] if possible_ut else None)
        if st_col is None and possible_district:
            # Sometimes 'State/UT' is in the same column name
            candidates = [c for c in df.columns if "state/ut" in c.lower() or "state - ut" in c.lower()]
            st_col = candidates[0] if candidates else df.columns[0]

    # Choose a stray dog numeric column with name clues
    dog_candidates = []
    for c in df.columns:
        name = c.lower()
        if ("dog" in name and "stray" in name) or ("dog (stray" in name):
            dog_candidates.append((c, is_mostly_numeric(df[c])))
    if dog_candidates:
        dog_col = sorted(dog_candidates, key=lambda x: x[1], reverse=True)[0][0]
    else:
        # fallback to the last mostly numeric column
        numeric_cols = [(c, is_mostly_numeric(df[c])) for c in df.columns]
        numeric_cols = [c for c in numeric_cols if c[1] > 0.8]
        dog_col = (numeric_cols[-1][0] if numeric_cols else df.columns[-1])

    # Clean and aggregate
    df = df[[st_col, dog_col]].copy()
    df.columns = ["state_raw", "stray_dogs"]
    df["state"] = df["state_raw"].apply(std_name).astype(str)
    # Drop rows where stray_dogs is NA or not numeric
    df["stray_dogs"] = pd.to_numeric(df["stray_dogs"], errors="coerce")
    df = df.dropna(subset=["stray_dogs", "state"]) 
    # Remove rows where state parsed into a numeric-looking token (e.g., '1.0')
    df = df[~pd.to_numeric(df["state"], errors="coerce").notna()]
    g = df.groupby("state", as_index=False)["stray_dogs"].sum()
    return g

def load_population_2019():
    # Attempt to parse from local curated CSV first (to avoid PDF parsing headaches)
    if POP_FALLBACK_CSV.exists():
        pop = pd.read_csv(POP_FALLBACK_CSV)
        pop["state"] = pop["state"].apply(std_name).astype(str)
        pop = pop[["state", "population_2019"]]
        return pop
    else:
        raise FileNotFoundError("Population CSV missing and PDF parsing not implemented in this minimal script.")

def load_states_geojson():
    gj = DATADIR / "india_states.geojson"
    if not gj.exists():
        print(f"Downloading state boundaries -> {gj}")
        download(STATE_GEOJSON_URL, gj)
    gdf = gpd.read_file(gj)
    # Standardize name column
    name_col = None
    for c in gdf.columns:
        if c.lower() in ("st_nm", "state", "state_name", "name", "name_1"):
            name_col = c
            break
    if name_col is None:
        # create one from the first string-looking column
        name_col = [c for c in gdf.columns if gdf[c].dtype == object][0]
    gdf["state"] = gdf[name_col].apply(std_name).astype(str)
    
    # Handle special cases: merge Dadra and Daman into combined UT
    dadra_mask = gdf["state"] == "Dadra & Nagar Haveli and Daman & Diu"
    if dadra_mask.sum() > 1:
        # Dissolve multiple geometries into one
        dadra_combined = gdf[dadra_mask].dissolve(by="state").reset_index()
        gdf = pd.concat([gdf[~dadra_mask], dadra_combined], ignore_index=True)
    
    return gdf[["state", "geometry"]]

# Safe figure saver with fallback filename on Windows file locks
def safe_savefig(fig, target_path: Path, **kwargs) -> Path:
    try:
        fig.savefig(target_path, **kwargs)
        return target_path
    except PermissionError:
        ts = time.strftime("%Y%m%d_%H%M%S")
        fallback = target_path.with_name(f"{target_path.stem}_{ts}{target_path.suffix}")
        print(f"Permission denied writing {target_path}. Saving as {fallback} instead.")
        fig.savefig(fallback, **kwargs)
        return fallback

def main():
    stray = load_dahd()
    pop = load_population_2019()

    # Merge and compute metric
    df = stray.merge(pop, on="state", how="left")
    missing_pop = df[df["population_2019"].isna()]["state"].tolist()
    if missing_pop:
        print("WARNING: Missing populations for:", missing_pop)
    df["stray_per_1000"] = (df["stray_dogs"] / df["population_2019"]) * 1000.0
    out_csv = OUTDIR / "stray_dogs_per_1000_2019.csv"
    df.to_csv(out_csv, index=False)

    # Map
    gdf = load_states_geojson()
    gdf = gdf.merge(df, on="state", how="left")

    fig, ax = plt.subplots(figsize=(11, 13))
    ax.set_axis_off()
    # Ensure no grid lines are shown
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    # Use a higher-contrast colormap and visible borders; style missing data distinctly
    gdf.plot(
        column="stray_per_1000",
        cmap="RdPu",
        linewidth=0.6,
        edgecolor="#555555",
        legend=False,
        ax=ax,
        vmin=0,
        zorder=1,
        missing_kwds={"color": "#f0f0f0", "edgecolor": "#cccccc", "hatch": "///", "label": "No data"},
    )
    # Draw state boundaries on top for clarity (white outline under dark line for contrast)
    gdf.boundary.plot(ax=ax, color="#ffffff", linewidth=1.2, zorder=3)
    gdf.boundary.plot(ax=ax, color="#333333", linewidth=0.7, zorder=4)

    # Annotate each state with its value only, using representative points of the largest polygon
    label_offsets = {
        "Goa": (-0.7, -0.5),
        "Karnataka": (0.0, 0.7),
        "Delhi": (0.4, -0.4),
        "Sikkim": (0.8, 0.3),
        "Tripura": (0.9, -0.3),
        "Manipur": (0.9, 0.0),
        "Meghalaya": (0.7, 0.0),
        "Nagaland": (1.0, 0.4),
        "Mizoram": (0.9, -0.4),
        "Arunachal Pradesh": (1.0, 0.1),
        "Jammu & Kashmir": (1.0, 0.8),
        "Puducherry": (0.5, -0.7),
        "Dadra & Nagar Haveli and Daman & Diu": (-0.5, -0.4),
        "Chandigarh": (0.3, -0.4),
        "Andaman & Nicobar Islands": (1.0, -0.8),
        "Lakshadweep": (-0.8, -0.4),
        "Maharashtra": (0.0, 0.2),
        "Madhya Pradesh": (-0.4, 0.1),
        "Uttar Pradesh": (0.2, 0.4),
        "Rajasthan": (-0.3, 0.3),
        "Gujarat": (-0.4, -0.1),
        "West Bengal": (0.4, -0.1),
        "Odisha": (0.2, 0.3),
        "Andhra Pradesh": (0.2, -0.4),
        "Telangana": (-0.2, 0.2),
        "Tamil Nadu": (-0.1, -0.3),
        "Kerala": (0.0, 0.0),
        "Bihar": (0.2, 0.3),
        "Jharkhand": (0.1, -0.1),
        "Chhattisgarh": (-0.1, 0.1),
        "Haryana": (-0.1, -0.3),
        "Punjab": (-0.2, 0.1),
        "Himachal Pradesh": (0.1, 0.2),
        "Uttarakhand": (0.2, 0.1),
        "Assam": (0.3, -0.1),
    }
    
    # State name abbreviations for better fit
    state_abbrev = {
        "Andaman And Nicobar": "A&N Islands",
        "Andaman & Nicobar Islands": "A&N Islands", 
        "Dadra & Nagar Haveli and Daman & Diu": "DNH & DD",
        "Jammu & Kashmir": "J&K",
        "Himachal Pradesh": "H.P.",
        "Madhya Pradesh": "M.P.",
        "Uttar Pradesh": "U.P.",
        "Arunachal Pradesh": "Arunachal",
        "Andhra Pradesh": "A.P.",
        "West Bengal": "W. Bengal",
        "Tamil Nadu": "T.N.",
        "Chhattisgarh": "CG",
    }

    from shapely.geometry import Polygon, MultiPolygon

    def largest_part_point(geometry):
        if isinstance(geometry, MultiPolygon):
            parts = list(geometry.geoms)
            if not parts:
                return None
            largest = max(parts, key=lambda g: g.area)
            return largest.representative_point()
        elif isinstance(geometry, Polygon):
            return geometry.representative_point()
        else:
            return geometry.representative_point()

    for _, row in gdf.iterrows():
        geom = row.get("geometry")
        if geom is None or geom.is_empty:
            continue
        pt = largest_part_point(geom)
        if pt is None:
            continue
        x, y = pt.x, pt.y
        # Apply small manual offsets for crowded regions
        off = label_offsets.get(row["state"], (0.0, 0.0))
        x += off[0]
        y += off[1]
        val = row.get("stray_per_1000")
        state_name = state_abbrev.get(row["state"], row["state"])
        if pd.isna(val):
            label_text = f"{state_name}\nN/A"
        else:
            label_text = f"{state_name}\n{val:.1f}"
        
        # Use different font sizes based on state size/importance
        if row["state"] in ["Goa", "Delhi", "Sikkim", "Tripura", "Manipur", "Meghalaya", "Nagaland", "Mizoram", "Chandigarh", "Puducherry", "Lakshadweep", "Dadra & Nagar Haveli and Daman & Diu"]:
            fontsize = 8
        else:
            fontsize = 10
            
        txt = ax.text(x, y, label_text, ha="center", va="center", 
                     fontsize=fontsize, fontweight="bold", color="#000000", 
                     zorder=5, family="sans-serif")
    title = "Number of Stray Dogs Per\n1000 People (2019)"
    fig.suptitle(title, fontsize=22, fontweight="bold", y=0.985)

    # Horizontal colorbar in the upper right
    vmax = float(pd.to_numeric(df["stray_per_1000"], errors="coerce").max()) if "stray_per_1000" in df else float(gdf["stray_per_1000"].max())
    vmax = 39.7  # Match the reference image max value
    cmap = plt.get_cmap("RdPu")
    norm = Normalize(vmin=0, vmax=vmax)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    # Place colorbar relative to figure
    cbar_ax = fig.add_axes([0.58, 0.905, 0.33, 0.02])  # [left, bottom, width, height]
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cbar.set_label("Stray Dogs per 1000 people", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    # Set specific ticks to match reference
    cbar.set_ticks([0, 13.2, 26.5, 39.7])
    # Reserve top margin to avoid overlap between title and colorbar
    fig.subplots_adjust(top=0.88)

    # Source text on the left
    source_lines = [
        "Source",
        "MINISTRY OF FISHERIES, ANIMAL",
        "HUSBANDRY AND DAIRYING",
        "DEPARTMENT OF ANIMAL",
        "HUSBANDRY AND DAIRYING",
        "",
        "https://dahd.nic.in/sites/default/",
        "files/LS2760.pdf",
    ]
    fig.text(0.06, 0.82, "\n".join(source_lines), fontsize=9, va="top")

    # National average big number near bottom-right
    try:
        nat_avg = (df["stray_dogs"].sum() / df["population_2019"].sum()) * 1000.0
        fig.text(0.77, 0.22, f"{nat_avg:.0f}", fontsize=64, fontweight="bold")
        fig.text(0.73, 0.155, "Stray Dogs per 1000 people", fontsize=11)
    except Exception:
        pass

    # Add "Created by" text at bottom left
    fig.text(0.06, 0.05, "Created by\nNaveen_Srinivas", fontsize=10, va="bottom")
    
    # Add attribution text at bottom left  
    fig.text(0.06, 0.15, "Naveen_Srinivas", fontsize=10, va="bottom")

    # Optional dog image if available at data/dog.png
    dog_img_path = DATADIR / "dog.png"
    if dog_img_path.exists():
        try:
            arr = mpimg.imread(str(dog_img_path))
            imagebox = OffsetImage(arr, zoom=0.25)
            ab = AnnotationBbox(imagebox, (0.88, 0.23), xycoords='figure fraction', frameon=False)
            fig.add_artist(ab)
        except Exception:
            pass

    out_png = OUTDIR / "stray_dogs_per_1000_2019.png"
    saved_png = safe_savefig(fig, out_png, dpi=300, bbox_inches="tight")
    print(f"Saved map to: {saved_png.resolve()}")
    print(f"Saved table to: {(OUTDIR / 'stray_dogs_per_1000_2019.csv').resolve()}")

if __name__ == "__main__":
    main()
