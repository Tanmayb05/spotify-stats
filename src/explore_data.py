"""
Spotify Streaming History Data Exploration
This script analyzes your complete Spotify streaming history from 2018-2025
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

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10

# Define paths
DATA_DIR = Path(__file__).parent.parent / 'data'
OUTPUT_DIR = Path(__file__).parent.parent / 'outputs'
IMAGES_DIR = OUTPUT_DIR / 'images'
DATA_OUTPUT_DIR = OUTPUT_DIR / 'data'

# Create output directories
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_all_audio_data():
    """Load all audio streaming history JSON files"""
    print("Loading audio streaming data...")

    audio_files = sorted(DATA_DIR.glob('streaming_*.json'))
    all_data = []

    for file in audio_files:
        print(f"  Loading {file.name}...")
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_data.extend(data)

    df = pd.DataFrame(all_data)
    print(f"  Loaded {len(df):,} streaming records from {len(audio_files)} files")
    return df

def load_video_data():
    """Load video streaming history JSON file"""
    print("\nLoading video streaming data...")

    video_file = DATA_DIR / 'streaming_video_2018-2025.json'

    if video_file.exists():
        with open(video_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        print(f"  Loaded {len(df):,} video streaming records")
        return df
    else:
        print("  No video data found")
        return pd.DataFrame()

def preprocess_data(df):
    """Preprocess the dataframe"""
    print("\nPreprocessing data...")

    # Convert timestamp to datetime
    df['ts'] = pd.to_datetime(df['ts'])

    # Extract time components
    df['year'] = df['ts'].dt.year
    df['month'] = df['ts'].dt.month
    df['day_of_week'] = df['ts'].dt.day_name()
    df['hour'] = df['ts'].dt.hour
    df['date'] = df['ts'].dt.date

    # Convert ms_played to minutes
    df['minutes_played'] = df['ms_played'] / 60000

    # Convert ms_played to hours for summary stats
    df['hours_played'] = df['ms_played'] / 3600000

    print(f"  Date range: {df['ts'].min()} to {df['ts'].max()}")
    print(f"  Total streaming time: {df['hours_played'].sum():.2f} hours")

    return df

def basic_statistics(df):
    """Print basic statistics about the data"""
    print("\n" + "="*60)
    print("BASIC STATISTICS")
    print("="*60)

    print(f"\nTotal streams: {len(df):,}")
    print(f"Total listening time: {df['hours_played'].sum():.2f} hours ({df['hours_played'].sum()/24:.2f} days)")
    print(f"Average stream duration: {df['minutes_played'].mean():.2f} minutes")
    print(f"Median stream duration: {df['minutes_played'].median():.2f} minutes")

    print(f"\nUnique tracks: {df['master_metadata_track_name'].nunique():,}")
    print(f"Unique artists: {df['master_metadata_album_artist_name'].nunique():,}")
    print(f"Unique albums: {df['master_metadata_album_album_name'].nunique():,}")

    print(f"\nShuffle mode usage: {(df['shuffle'] == True).sum():,} streams ({(df['shuffle'] == True).sum()/len(df)*100:.1f}%)")
    print(f"Skipped tracks: {(df['skipped'] == True).sum():,} streams ({(df['skipped'] == True).sum()/len(df)*100:.1f}%)")
    print(f"Offline listening: {(df['offline'] == True).sum():,} streams ({(df['offline'] == True).sum()/len(df)*100:.1f}%)")
    print(f"Private sessions: {(df['incognito_mode'] == True).sum():,} streams ({(df['incognito_mode'] == True).sum()/len(df)*100:.1f}%)")

    print(f"\nUnique platforms: {df['platform'].nunique()}")
    print(f"Unique countries: {df['conn_country'].nunique()}")

def plot_top_artists(df, top_n=20):
    """Plot top artists by number of streams"""
    print("\nGenerating top artists chart...")

    top_artists = df['master_metadata_album_artist_name'].value_counts().head(top_n)

    plt.figure(figsize=(12, 8))
    sns.barplot(x=top_artists.values, y=top_artists.index, palette='viridis')
    plt.xlabel('Number of Streams')
    plt.ylabel('Artist')
    plt.title(f'Top {top_n} Most Streamed Artists', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'top_artists.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/top_artists.png")

def plot_top_tracks(df, top_n=20):
    """Plot top tracks by number of streams"""
    print("\nGenerating top tracks chart...")

    # Create track identifier with artist name
    df['track_artist'] = df['master_metadata_track_name'] + ' - ' + df['master_metadata_album_artist_name']
    top_tracks = df['track_artist'].value_counts().head(top_n)

    plt.figure(figsize=(12, 8))
    sns.barplot(x=top_tracks.values, y=top_tracks.index, palette='plasma')
    plt.xlabel('Number of Streams')
    plt.ylabel('Track - Artist')
    plt.title(f'Top {top_n} Most Streamed Tracks', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'top_tracks.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/top_tracks.png")

def plot_listening_over_time(df):
    """Plot listening activity over time"""
    print("\nGenerating listening over time chart...")

    # Group by month
    df['year_month'] = df['ts'].dt.to_period('M')
    monthly_stats = df.groupby('year_month').agg({
        'ms_played': 'count',
        'hours_played': 'sum'
    }).reset_index()
    monthly_stats['year_month'] = monthly_stats['year_month'].astype(str)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    # Number of streams
    ax1.plot(monthly_stats['year_month'], monthly_stats['ms_played'], marker='o', linewidth=2, markersize=4)
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Number of Streams')
    ax1.set_title('Number of Streams Over Time', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)

    # Hours listened
    ax2.plot(monthly_stats['year_month'], monthly_stats['hours_played'], marker='o', linewidth=2, markersize=4, color='green')
    ax2.set_xlabel('Month')
    ax2.set_ylabel('Hours Listened')
    ax2.set_title('Total Listening Time Over Time', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'listening_over_time.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/listening_over_time.png")

def plot_listening_by_hour(df):
    """Plot listening patterns by hour of day"""
    print("\nGenerating listening by hour chart...")

    hourly_stats = df.groupby('hour').size()

    plt.figure(figsize=(12, 6))
    plt.bar(hourly_stats.index, hourly_stats.values, color='coral', edgecolor='black', alpha=0.7)
    plt.xlabel('Hour of Day')
    plt.ylabel('Number of Streams')
    plt.title('Listening Activity by Hour of Day', fontsize=14, fontweight='bold')
    plt.xticks(range(0, 24))
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'listening_by_hour.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/listening_by_hour.png")

def plot_listening_by_day(df):
    """Plot listening patterns by day of week"""
    print("\nGenerating listening by day of week chart...")

    # Order days properly
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_stats = df.groupby('day_of_week').size().reindex(day_order)

    plt.figure(figsize=(10, 6))
    plt.bar(day_stats.index, day_stats.values, color='skyblue', edgecolor='black', alpha=0.7)
    plt.xlabel('Day of Week')
    plt.ylabel('Number of Streams')
    plt.title('Listening Activity by Day of Week', fontsize=14, fontweight='bold')
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'listening_by_day.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/listening_by_day.png")

def plot_platform_usage(df):
    """Plot platform usage"""
    print("\nGenerating platform usage chart...")

    platform_stats = df['platform'].value_counts().head(10)

    plt.figure(figsize=(10, 6))
    plt.pie(platform_stats.values, labels=platform_stats.index, autopct='%1.1f%%', startangle=90)
    plt.title('Platform Usage Distribution (Top 10)', fontsize=14, fontweight='bold')
    plt.axis('equal')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'platform_usage.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/platform_usage.png")

def plot_skip_behavior(df):
    """Analyze and plot skip behavior"""
    print("\nGenerating skip behavior analysis...")

    # Filter tracks that were skipped
    df_clean = df[df['skipped'].notna()].copy()
    skip_rate = df_clean.groupby('master_metadata_album_artist_name').agg({
        'skipped': ['sum', 'count']
    })
    skip_rate.columns = ['skips', 'total_streams']
    skip_rate['skip_rate'] = skip_rate['skips'] / skip_rate['total_streams'] * 100
    skip_rate = skip_rate[skip_rate['total_streams'] >= 20]  # Only artists with 20+ streams

    # Top artists by skip rate
    top_skipped = skip_rate.nlargest(15, 'skip_rate')

    # Top artists with lowest skip rate (most completion)
    least_skipped = skip_rate.nsmallest(15, 'skip_rate')

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Most skipped
    sns.barplot(x=top_skipped['skip_rate'], y=top_skipped.index, ax=ax1, palette='Reds_r')
    ax1.set_xlabel('Skip Rate (%)')
    ax1.set_ylabel('Artist')
    ax1.set_title('Artists with Highest Skip Rate (20+ streams)', fontsize=12, fontweight='bold')

    # Least skipped
    sns.barplot(x=least_skipped['skip_rate'], y=least_skipped.index, ax=ax2, palette='Greens_r')
    ax2.set_xlabel('Skip Rate (%)')
    ax2.set_ylabel('Artist')
    ax2.set_title('Artists with Lowest Skip Rate (20+ streams)', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'skip_behavior.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/skip_behavior.png")

def plot_yearly_comparison(df):
    """Compare listening across years"""
    print("\nGenerating yearly comparison chart...")

    yearly_stats = df.groupby('year').agg({
        'ms_played': 'count',
        'hours_played': 'sum'
    }).reset_index()
    yearly_stats.columns = ['year', 'streams', 'hours']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Streams per year
    ax1.bar(yearly_stats['year'], yearly_stats['streams'], color='steelblue', edgecolor='black', alpha=0.7)
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Number of Streams')
    ax1.set_title('Total Streams by Year', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')

    # Hours per year
    ax2.bar(yearly_stats['year'], yearly_stats['hours'], color='darkgreen', edgecolor='black', alpha=0.7)
    ax2.set_xlabel('Year')
    ax2.set_ylabel('Hours Listened')
    ax2.set_title('Total Listening Time by Year', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'yearly_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/yearly_comparison.png")

def export_summary_statistics(df):
    """Export summary statistics to CSV"""
    print("\nExporting summary statistics...")

    # Top artists
    top_artists = df['master_metadata_album_artist_name'].value_counts().head(50)
    top_artists.to_csv(DATA_OUTPUT_DIR / 'top_50_artists.csv', header=['streams'])
    print(f"  Saved: outputs/data/top_50_artists.csv")

    # Top tracks
    df['track_artist'] = df['master_metadata_track_name'] + ' - ' + df['master_metadata_album_artist_name']
    top_tracks = df['track_artist'].value_counts().head(50)
    top_tracks.to_csv(DATA_OUTPUT_DIR / 'top_50_tracks.csv', header=['streams'])
    print(f"  Saved: outputs/data/top_50_tracks.csv")

    # Monthly summary
    df['year_month'] = df['ts'].dt.to_period('M')
    monthly_summary = df.groupby('year_month').agg({
        'ms_played': 'count',
        'hours_played': 'sum',
        'master_metadata_track_name': 'nunique',
        'master_metadata_album_artist_name': 'nunique'
    }).reset_index()
    monthly_summary.columns = ['month', 'total_streams', 'hours_listened', 'unique_tracks', 'unique_artists']
    monthly_summary.to_csv(DATA_OUTPUT_DIR / 'monthly_summary.csv', index=False)
    print(f"  Saved: outputs/data/monthly_summary.csv")

def main():
    """Main function to run all analyses"""
    print("="*60)
    print("SPOTIFY STREAMING HISTORY DATA EXPLORATION")
    print("="*60)

    # Load data
    audio_df = load_all_audio_data()
    video_df = load_video_data()

    # Focus on audio data for main analysis
    df = preprocess_data(audio_df)

    # Basic statistics
    basic_statistics(df)

    # Generate visualizations
    print("\n" + "="*60)
    print("GENERATING VISUALIZATIONS")
    print("="*60)

    plot_top_artists(df, top_n=20)
    plot_top_tracks(df, top_n=20)
    plot_listening_over_time(df)
    plot_listening_by_hour(df)
    plot_listening_by_day(df)
    plot_platform_usage(df)
    plot_skip_behavior(df)
    plot_yearly_comparison(df)

    # Export summary data
    print("\n" + "="*60)
    print("EXPORTING SUMMARY DATA")
    print("="*60)
    export_summary_statistics(df)

    print("\n" + "="*60)
    print("ANALYSIS COMPLETE!")
    print("="*60)
    print(f"\nAll outputs saved to: {OUTPUT_DIR.absolute()}")
    print("\nGenerated files:")
    print("  - 8 visualization images (PNG)")
    print("  - 3 summary CSV files")

if __name__ == "__main__":
    main()
