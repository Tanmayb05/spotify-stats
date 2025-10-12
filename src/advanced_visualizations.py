"""
Advanced Visualizations
Creates additional advanced charts and visualizations
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
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

def load_data():
    """Load audio data"""
    print("Loading data...")
    audio_files = sorted(DATA_DIR.glob('streaming_*.json'))
    all_data = []

    for file in audio_files:
        with open(file, 'r', encoding='utf-8') as f:
            all_data.extend(json.load(f))

    df = pd.DataFrame(all_data)
    df['ts'] = pd.to_datetime(df['ts'])
    df['date'] = df['ts'].dt.date
    df['hour'] = df['ts'].dt.hour
    df['year'] = df['ts'].dt.year
    df['month'] = df['ts'].dt.month
    df['day_of_week'] = df['ts'].dt.day_name()
    df['minutes_played'] = df['ms_played'] / 60000
    df['hours_played'] = df['ms_played'] / 3600000

    print(f"Loaded {len(df):,} records")
    return df

def create_listening_calendar(df):
    """Create a calendar heatmap of listening activity"""
    print("\nCreating listening calendar heatmap...")

    # Get daily stream counts
    daily_counts = df.groupby('date').size().reset_index(name='streams')
    daily_counts['date'] = pd.to_datetime(daily_counts['date'])
    daily_counts['year'] = daily_counts['date'].dt.year
    daily_counts['month'] = daily_counts['date'].dt.month
    daily_counts['day'] = daily_counts['date'].dt.day

    # Create pivot for recent year
    recent_year = daily_counts['year'].max()
    year_data = daily_counts[daily_counts['year'] == recent_year].copy()
    year_data['week'] = year_data['date'].dt.isocalendar().week
    year_data['weekday'] = year_data['date'].dt.dayofweek

    # Create heatmap
    pivot_data = year_data.pivot_table(values='streams', index='weekday', columns='week', fill_value=0)

    plt.figure(figsize=(20, 6))
    sns.heatmap(pivot_data, cmap='YlGnBu', cbar_kws={'label': 'Streams'}, linewidths=0.5)
    plt.xlabel('Week of Year')
    plt.ylabel('Day of Week')
    plt.yticks(range(7), ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], rotation=0)
    plt.title(f'Listening Activity Calendar - {recent_year}', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / f'listening_calendar_{recent_year}.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/listening_calendar_{recent_year}.png")

def create_artist_network(df):
    """Analyze artist co-listening patterns"""
    print("\nAnalyzing artist co-listening...")

    # Get top 30 artists
    top_artists = df['master_metadata_album_artist_name'].value_counts().head(30).index

    # Find which artists are listened to on the same days
    df_top = df[df['master_metadata_album_artist_name'].isin(top_artists)].copy()

    # Get daily artist combinations
    daily_artists = df_top.groupby('date')['master_metadata_album_artist_name'].apply(set).reset_index()

    # Count co-occurrences
    from itertools import combinations

    co_listen = {}
    for artists_set in daily_artists['master_metadata_album_artist_name']:
        if len(artists_set) > 1:
            for pair in combinations(sorted(artists_set), 2):
                if pair in co_listen:
                    co_listen[pair] += 1
                else:
                    co_listen[pair] = 1

    # Create DataFrame
    if co_listen:
        co_listen_df = pd.DataFrame([
            {'Artist 1': pair[0], 'Artist 2': pair[1], 'Days Together': count}
            for pair, count in co_listen.items()
        ])
        co_listen_df = co_listen_df.sort_values('Days Together', ascending=False)

        co_listen_df.head(50).to_csv(DATA_OUTPUT_DIR / 'artist_co_listening.csv', index=False)
        print(f"  Saved: outputs/data/artist_co_listening.csv")
    else:
        print("  Not enough data for co-listening analysis")

def create_listening_momentum(df):
    """Create listening momentum chart (rolling averages)"""
    print("\nCreating listening momentum chart...")

    daily_stats = df.groupby('date').agg({
        'ms_played': 'count',
        'hours_played': 'sum'
    }).reset_index()
    daily_stats.columns = ['date', 'streams', 'hours']

    # Calculate rolling averages
    daily_stats['streams_7d_avg'] = daily_stats['streams'].rolling(window=7, min_periods=1).mean()
    daily_stats['streams_30d_avg'] = daily_stats['streams'].rolling(window=30, min_periods=1).mean()
    daily_stats['hours_7d_avg'] = daily_stats['hours'].rolling(window=7, min_periods=1).mean()

    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))

    # Streams
    axes[0].plot(daily_stats['date'], daily_stats['streams'], alpha=0.3, color='gray', label='Daily')
    axes[0].plot(daily_stats['date'], daily_stats['streams_7d_avg'], linewidth=2, color='blue', label='7-day avg')
    axes[0].plot(daily_stats['date'], daily_stats['streams_30d_avg'], linewidth=2, color='red', label='30-day avg')
    axes[0].set_ylabel('Streams')
    axes[0].set_title('Listening Momentum: Stream Count', fontsize=12, fontweight='bold')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Hours
    axes[1].plot(daily_stats['date'], daily_stats['hours'], alpha=0.3, color='gray', label='Daily')
    axes[1].plot(daily_stats['date'], daily_stats['hours_7d_avg'], linewidth=2, color='green', label='7-day avg')
    axes[1].set_xlabel('Date')
    axes[1].set_ylabel('Hours')
    axes[1].set_title('Listening Momentum: Hours Listened', fontsize=12, fontweight='bold')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'listening_momentum.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/listening_momentum.png")

def create_artist_timeline_bands(df):
    """Create timeline showing when different artists were popular"""
    print("\nCreating artist timeline bands...")

    # Get top 15 artists
    top_artists = df['master_metadata_album_artist_name'].value_counts().head(15).index

    # Get monthly streams for each artist
    df_top = df[df['master_metadata_album_artist_name'].isin(top_artists)].copy()
    df_top['year_month'] = df_top['ts'].dt.to_period('M')

    artist_monthly = df_top.groupby(['year_month', 'master_metadata_album_artist_name']).size().reset_index(name='streams')
    artist_pivot = artist_monthly.pivot(index='year_month', columns='master_metadata_album_artist_name', values='streams').fillna(0)

    # Create stacked area chart
    plt.figure(figsize=(16, 8))
    artist_pivot.plot.area(stacked=True, alpha=0.7, figsize=(16, 8), colormap='tab20')

    plt.xlabel('Month')
    plt.ylabel('Number of Streams')
    plt.title('Artist Listening Timeline (Top 15 Artists)', fontsize=14, fontweight='bold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'artist_timeline_bands.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/artist_timeline_bands.png")

def create_listening_intensity_scatter(df):
    """Create scatter plot of daily listening intensity"""
    print("\nCreating listening intensity scatter plot...")

    daily_stats = df.groupby('date').agg({
        'ms_played': 'count',
        'hours_played': 'sum',
        'master_metadata_track_name': 'nunique'
    }).reset_index()
    daily_stats.columns = ['date', 'streams', 'hours', 'unique_tracks']

    # Create scatter plot
    plt.figure(figsize=(14, 8))
    scatter = plt.scatter(
        daily_stats['streams'],
        daily_stats['hours'],
        c=daily_stats['unique_tracks'],
        s=50,
        alpha=0.6,
        cmap='viridis',
        edgecolors='black',
        linewidth=0.5
    )

    plt.colorbar(scatter, label='Unique Tracks')
    plt.xlabel('Number of Streams')
    plt.ylabel('Total Hours')
    plt.title('Daily Listening Intensity', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'listening_intensity_scatter.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/listening_intensity_scatter.png")

def create_monthly_comparison_radar(df):
    """Create radar chart comparing listening across months"""
    print("\nCreating monthly comparison chart...")

    # Get hourly distribution for each month
    df['month_name'] = df['ts'].dt.strftime('%B')
    hourly_monthly = df.groupby(['month_name', 'hour']).size().reset_index(name='streams')

    # Normalize by total streams per month
    monthly_totals = df.groupby('month_name').size()
    hourly_monthly['normalized_streams'] = hourly_monthly.apply(
        lambda x: x['streams'] / monthly_totals[x['month_name']] * 100, axis=1
    )

    # Get peak hours for each month
    peak_hours = hourly_monthly.groupby('month_name').apply(
        lambda x: x.nlargest(3, 'normalized_streams')['hour'].tolist()
    )

    # Create summary
    month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']

    month_summary = []
    for month in month_order:
        if month in peak_hours.index:
            month_data = df[df['month_name'] == month]
            month_summary.append({
                'Month': month,
                'Total Streams': len(month_data),
                'Avg Streams/Day': len(month_data) / month_data['date'].nunique(),
                'Peak Hours': ', '.join([f"{h}:00" for h in peak_hours[month]])
            })

    if month_summary:
        month_df = pd.DataFrame(month_summary)
        month_df.to_csv(DATA_OUTPUT_DIR / 'monthly_patterns_summary.csv', index=False)
        print(f"  Saved: outputs/data/monthly_patterns_summary.csv")

def main():
    print("="*60)
    print("ADVANCED VISUALIZATIONS")
    print("="*60)

    df = load_data()

    create_listening_calendar(df)
    create_artist_network(df)
    create_listening_momentum(df)
    create_artist_timeline_bands(df)
    create_listening_intensity_scatter(df)
    create_monthly_comparison_radar(df)

    print("\n" + "="*60)
    print("ADVANCED VISUALIZATIONS COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
