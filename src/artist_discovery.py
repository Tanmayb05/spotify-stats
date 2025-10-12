"""
Artist Discovery and Loyalty Analysis
Analyzes when you discovered artists and how your relationship with them evolved
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

sns.set_style("whitegrid")
DATA_DIR = Path(__file__).parent.parent / 'data'
OUTPUT_DIR = Path(__file__).parent.parent / 'outputs'
IMAGES_DIR = OUTPUT_DIR / 'images'
DATA_OUTPUT_DIR = OUTPUT_DIR / 'data'
DASHBOARDS_DIR = OUTPUT_DIR / 'dashboards'

# Create output directories
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)

def load_and_preprocess():
    """Load and preprocess audio data"""
    print("Loading streaming data...")

    audio_files = sorted(DATA_DIR.glob('streaming_*.json'))
    all_data = []

    for file in audio_files:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_data.extend(data)

    df = pd.DataFrame(all_data)
    df['ts'] = pd.to_datetime(df['ts'])
    df['date'] = df['ts'].dt.date
    df['year'] = df['ts'].dt.year
    df['year_month'] = df['ts'].dt.to_period('M')

    print(f"Loaded {len(df):,} records")
    return df

def analyze_artist_discovery(df):
    """Analyze when artists were first discovered"""
    print("\nAnalyzing artist discovery timeline...")

    # Get first listen date for each artist
    first_listens = df.groupby('master_metadata_album_artist_name')['ts'].min().reset_index()
    first_listens.columns = ['artist', 'first_listen']
    first_listens['year'] = first_listens['first_listen'].dt.year
    first_listens['year_month'] = first_listens['first_listen'].dt.to_period('M')

    # Count artists discovered per year
    discoveries_per_year = first_listens['year'].value_counts().sort_index()

    # Count artists discovered per month
    discoveries_per_month = first_listens['year_month'].value_counts().sort_index()

    # Export yearly discoveries
    discoveries_yearly_df = pd.DataFrame({
        'Year': discoveries_per_year.index,
        'New Artists Discovered': discoveries_per_year.values
    })
    discoveries_yearly_df.to_csv(DATA_OUTPUT_DIR / 'artists_discovered_per_year.csv', index=False)
    print(f"  Saved: outputs/data/artists_discovered_per_year.csv")

    # Export monthly discoveries
    discoveries_monthly_df = pd.DataFrame({
        'Month': discoveries_per_month.index.astype(str),
        'New Artists Discovered': discoveries_per_month.values
    })
    discoveries_monthly_df.to_csv(DATA_OUTPUT_DIR / 'artists_discovered_per_month.csv', index=False)
    print(f"  Saved: outputs/data/artists_discovered_per_month.csv")

    # Visualize discoveries over time
    plt.figure(figsize=(14, 6))
    plt.bar(discoveries_per_year.index, discoveries_per_year.values, color='teal', edgecolor='black', alpha=0.7)
    plt.xlabel('Year')
    plt.ylabel('New Artists Discovered')
    plt.title('Artist Discovery Over Time (by Year)', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'artist_discovery_by_year.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/artist_discovery_by_year.png")

    return first_listens

def analyze_artist_loyalty(df, first_listens):
    """Analyze how long you've been listening to artists"""
    print("\nAnalyzing artist loyalty...")

    # Get last listen date for each artist
    last_listens = df.groupby('master_metadata_album_artist_name')['ts'].max().reset_index()
    last_listens.columns = ['artist', 'last_listen']

    # Merge with first listens
    loyalty = first_listens[['artist', 'first_listen']].merge(last_listens, on='artist')

    # Calculate listening span in days
    loyalty['listening_span_days'] = (loyalty['last_listen'] - loyalty['first_listen']).dt.days

    # Get total streams per artist
    artist_streams = df.groupby('master_metadata_album_artist_name').size().reset_index(name='total_streams')
    loyalty = loyalty.merge(artist_streams, left_on='artist', right_on='master_metadata_album_artist_name')

    # Calculate loyalty score (streams per day since discovery)
    loyalty['loyalty_score'] = loyalty['total_streams'] / (loyalty['listening_span_days'] + 1)  # +1 to avoid division by zero

    # Top loyal artists (high streams + long span)
    top_loyal = loyalty.nlargest(30, 'loyalty_score')[['artist', 'first_listen', 'last_listen', 'listening_span_days', 'total_streams', 'loyalty_score']]
    top_loyal.to_csv(DATA_OUTPUT_DIR / 'most_loyal_artists.csv', index=False)
    print(f"  Saved: outputs/data/most_loyal_artists.csv")

    # Artists with longest listening span
    longest_span = loyalty.nlargest(30, 'listening_span_days')[['artist', 'first_listen', 'last_listen', 'listening_span_days', 'total_streams']]
    longest_span.to_csv(DATA_OUTPUT_DIR / 'longest_listening_span_artists.csv', index=False)
    print(f"  Saved: outputs/data/longest_listening_span_artists.csv")

    # Visualize loyalty
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Top loyal artists
    top_10_loyal = loyalty.nlargest(15, 'loyalty_score')
    axes[0].barh(range(len(top_10_loyal)), top_10_loyal['loyalty_score'], color='purple', alpha=0.7)
    axes[0].set_yticks(range(len(top_10_loyal)))
    axes[0].set_yticklabels(top_10_loyal['artist'])
    axes[0].set_xlabel('Loyalty Score (streams per day)')
    axes[0].set_title('Most Loyal Artists (Highest Consistency)', fontsize=12, fontweight='bold')
    axes[0].invert_yaxis()

    # Longest relationships
    top_10_span = loyalty.nlargest(15, 'listening_span_days')
    axes[1].barh(range(len(top_10_span)), top_10_span['listening_span_days'], color='darkgreen', alpha=0.7)
    axes[1].set_yticks(range(len(top_10_span)))
    axes[1].set_yticklabels(top_10_span['artist'])
    axes[1].set_xlabel('Listening Span (days)')
    axes[1].set_title('Longest Artist Relationships', fontsize=12, fontweight='bold')
    axes[1].invert_yaxis()

    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'artist_loyalty_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/artist_loyalty_analysis.png")

def analyze_artist_phases(df):
    """Identify distinct phases of artist preference"""
    print("\nAnalyzing artist preference phases...")

    # Get monthly top artist
    monthly_top = df.groupby(['year_month', 'master_metadata_album_artist_name']).size().reset_index(name='streams')
    idx = monthly_top.groupby('year_month')['streams'].idxmax()
    monthly_top_artist = monthly_top.loc[idx][['year_month', 'master_metadata_album_artist_name', 'streams']]
    monthly_top_artist.columns = ['Month', 'Top Artist', 'Streams']
    monthly_top_artist['Month'] = monthly_top_artist['Month'].astype(str)

    monthly_top_artist.to_csv(DATA_OUTPUT_DIR / 'monthly_top_artist.csv', index=False)
    print(f"  Saved: outputs/data/monthly_top_artist.csv")

    # Identify "obsession" periods (artist dominates a month with >30% of streams)
    monthly_total = df.groupby('year_month').size().reset_index(name='total_monthly_streams')
    monthly_artist_share = df.groupby(['year_month', 'master_metadata_album_artist_name']).size().reset_index(name='artist_streams')
    monthly_artist_share = monthly_artist_share.merge(monthly_total, on='year_month')
    monthly_artist_share['share_pct'] = (monthly_artist_share['artist_streams'] / monthly_artist_share['total_monthly_streams']) * 100

    obsessions = monthly_artist_share[monthly_artist_share['share_pct'] > 30].sort_values('share_pct', ascending=False)
    obsessions = obsessions[['year_month', 'master_metadata_album_artist_name', 'artist_streams', 'share_pct']]
    obsessions.columns = ['Month', 'Artist', 'Streams', 'Share of Month (%)']
    obsessions['Month'] = obsessions['Month'].astype(str)

    obsessions.to_csv(DATA_OUTPUT_DIR / 'artist_obsession_periods.csv', index=False)
    print(f"  Saved: outputs/data/artist_obsession_periods.csv")
    print(f"  Found {len(obsessions)} obsession periods (>30% monthly share)")

def analyze_one_hit_wonders(df):
    """Identify artists you only listened to briefly"""
    print("\nAnalyzing one-hit wonders and brief encounters...")

    artist_stats = df.groupby('master_metadata_album_artist_name').agg({
        'ts': ['min', 'max', 'count'],
        'date': 'nunique'
    })

    artist_stats.columns = ['first_listen', 'last_listen', 'total_streams', 'unique_days']
    artist_stats['listening_span_days'] = (artist_stats['last_listen'] - artist_stats['first_listen']).dt.days

    # One-hit wonders: listened once or on a single day
    one_hit = artist_stats[
        (artist_stats['total_streams'] <= 5) &
        (artist_stats['unique_days'] == 1)
    ].sort_values('first_listen', ascending=False)

    one_hit = one_hit.reset_index()[['master_metadata_album_artist_name', 'first_listen', 'total_streams']]
    one_hit.columns = ['Artist', 'Listen Date', 'Total Streams']

    one_hit.head(100).to_csv(DATA_OUTPUT_DIR / 'one_hit_wonders.csv', index=False)
    print(f"  Saved: outputs/data/one_hit_wonders.csv")
    print(f"  Found {len(one_hit)} one-hit wonder artists")

def analyze_artist_evolution(df):
    """Track how top artists evolved over the years"""
    print("\nAnalyzing artist evolution over years...")

    top_artists = df['master_metadata_album_artist_name'].value_counts().head(20).index

    artist_yearly = df[df['master_metadata_album_artist_name'].isin(top_artists)].groupby(
        ['year', 'master_metadata_album_artist_name']
    ).size().reset_index(name='streams')

    artist_yearly_pivot = artist_yearly.pivot(index='year', columns='master_metadata_album_artist_name', values='streams').fillna(0)

    # Plot evolution for top 10 artists
    plt.figure(figsize=(14, 8))
    top_10 = df['master_metadata_album_artist_name'].value_counts().head(10).index

    for artist in top_10:
        if artist in artist_yearly_pivot.columns:
            plt.plot(artist_yearly_pivot.index, artist_yearly_pivot[artist], marker='o', label=artist, linewidth=2)

    plt.xlabel('Year')
    plt.ylabel('Number of Streams')
    plt.title('Top 10 Artists: Listening Evolution Over Years', fontsize=14, fontweight='bold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'artist_evolution_over_years.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/artist_evolution_over_years.png")

    # Export the data
    artist_yearly_pivot.to_csv(DATA_OUTPUT_DIR / 'artist_yearly_streams.csv')
    print(f"  Saved: outputs/data/artist_yearly_streams.csv")

def main():
    print("="*60)
    print("ARTIST DISCOVERY AND LOYALTY ANALYSIS")
    print("="*60)

    df = load_and_preprocess()

    first_listens = analyze_artist_discovery(df)
    analyze_artist_loyalty(df, first_listens)
    analyze_artist_phases(df)
    analyze_one_hit_wonders(df)
    analyze_artist_evolution(df)

    print("\n" + "="*60)
    print("ARTIST DISCOVERY ANALYSIS COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
