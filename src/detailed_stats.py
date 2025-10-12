"""
Detailed Statistics and Comprehensive Reports
Generates comprehensive statistical reports and data exports
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).parent.parent / 'data'
OUTPUT_DIR = Path(__file__).parent.parent / 'outputs'
IMAGES_DIR = OUTPUT_DIR / 'images'
DATA_OUTPUT_DIR = OUTPUT_DIR / 'data'
DASHBOARDS_DIR = OUTPUT_DIR / 'dashboards'

# Create output directories
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)

def load_all_data():
    """Load all streaming data"""
    print("Loading all streaming data...")

    # Audio data
    audio_files = sorted(DATA_DIR.glob('streaming_*.json'))
    all_audio = []
    for file in audio_files:
        with open(file, 'r', encoding='utf-8') as f:
            all_audio.extend(json.load(f))

    audio_df = pd.DataFrame(all_audio)
    audio_df['ts'] = pd.to_datetime(audio_df['ts'])
    audio_df['content_type'] = 'audio'

    # Video data
    video_file = DATA_DIR / 'streaming_video_2018-2025.json'
    if video_file.exists():
        with open(video_file, 'r', encoding='utf-8') as f:
            video_data = json.load(f)
        video_df = pd.DataFrame(video_data)
        video_df['ts'] = pd.to_datetime(video_df['ts'])
        video_df['content_type'] = 'video'
    else:
        video_df = pd.DataFrame()

    print(f"  Audio: {len(audio_df):,} records")
    if not video_df.empty:
        print(f"  Video: {len(video_df):,} records")

    return audio_df, video_df

def generate_overall_statistics(audio_df, video_df):
    """Generate comprehensive overall statistics"""
    print("\nGenerating overall statistics...")

    stats = []

    # Time statistics
    audio_df['hours'] = audio_df['ms_played'] / 3600000
    total_hours = audio_df['hours'].sum()
    total_days = total_hours / 24

    stats.append(('Total Audio Streams', f"{len(audio_df):,}"))
    if not video_df.empty:
        stats.append(('Total Video Streams', f"{len(video_df):,}"))
    stats.append(('Total Listening Time (hours)', f"{total_hours:,.1f}"))
    stats.append(('Total Listening Time (days)', f"{total_days:,.1f}"))
    stats.append(('Average Stream Duration (minutes)', f"{(audio_df['ms_played'].mean() / 60000):.2f}"))

    # Date range
    start_date = audio_df['ts'].min()
    end_date = audio_df['ts'].max()
    total_span = (end_date - start_date).days

    stats.append(('First Stream Date', start_date.strftime('%Y-%m-%d')))
    stats.append(('Last Stream Date', end_date.strftime('%Y-%m-%d')))
    stats.append(('Total Span (days)', f"{total_span:,}"))
    stats.append(('Average Streams per Day', f"{len(audio_df) / total_span:.1f}"))
    stats.append(('Average Hours per Day', f"{total_hours / total_span:.2f}"))

    # Content diversity
    stats.append(('Unique Tracks', f"{audio_df['master_metadata_track_name'].nunique():,}"))
    stats.append(('Unique Artists', f"{audio_df['master_metadata_album_artist_name'].nunique():,}"))
    stats.append(('Unique Albums', f"{audio_df['master_metadata_album_album_name'].nunique():,}"))

    # Behavior stats
    total_with_shuffle = (audio_df['shuffle'] == True).sum()
    total_skipped = (audio_df['skipped'] == True).sum()
    total_offline = (audio_df['offline'] == True).sum()
    total_incognito = (audio_df['incognito_mode'] == True).sum()

    stats.append(('Shuffle Mode Usage', f"{total_with_shuffle:,} ({total_with_shuffle/len(audio_df)*100:.1f}%)"))
    stats.append(('Skipped Tracks', f"{total_skipped:,} ({total_skipped/len(audio_df)*100:.1f}%)"))
    stats.append(('Offline Listening', f"{total_offline:,} ({total_offline/len(audio_df)*100:.1f}%)"))
    stats.append(('Private Sessions', f"{total_incognito:,} ({total_incognito/len(audio_df)*100:.1f}%)"))

    # Platform and location
    stats.append(('Unique Platforms', f"{audio_df['platform'].nunique():,}"))
    stats.append(('Unique Countries', f"{audio_df['conn_country'].nunique():,}"))

    # Days with activity
    unique_days = audio_df['ts'].dt.date.nunique()
    stats.append(('Days with Listening Activity', f"{unique_days:,}"))
    stats.append(('Activity Coverage', f"{unique_days/total_span*100:.1f}%"))

    # Export
    stats_df = pd.DataFrame(stats, columns=['Metric', 'Value'])
    stats_df.to_csv(DATA_OUTPUT_DIR / 'comprehensive_statistics.csv', index=False)
    print(f"  Saved: outputs/data/comprehensive_statistics.csv")

    return stats_df

def generate_platform_report(df):
    """Generate detailed platform usage report"""
    print("\nGenerating platform usage report...")

    platform_stats = df.groupby('platform').agg({
        'ms_played': ['count', 'sum'],
        'master_metadata_track_name': 'nunique',
        'ts': ['min', 'max']
    })

    platform_stats.columns = ['Total Streams', 'Total ms', 'Unique Tracks', 'First Use', 'Last Use']
    platform_stats['Total Hours'] = platform_stats['Total ms'] / 3600000
    platform_stats['Avg Stream Duration (min)'] = (platform_stats['Total ms'] / platform_stats['Total Streams']) / 60000
    platform_stats = platform_stats.sort_values('Total Streams', ascending=False)

    platform_stats = platform_stats[['Total Streams', 'Total Hours', 'Unique Tracks', 'Avg Stream Duration (min)', 'First Use', 'Last Use']]
    platform_stats.to_csv(DATA_OUTPUT_DIR / 'platform_detailed_stats.csv')
    print(f"  Saved: outputs/data/platform_detailed_stats.csv")

def generate_country_report(df):
    """Generate detailed country/location report"""
    print("\nGenerating country usage report...")

    country_stats = df.groupby('conn_country').agg({
        'ms_played': ['count', 'sum'],
        'master_metadata_track_name': 'nunique',
        'ts': ['min', 'max']
    })

    country_stats.columns = ['Total Streams', 'Total ms', 'Unique Tracks', 'First Listen', 'Last Listen']
    country_stats['Total Hours'] = country_stats['Total ms'] / 3600000
    country_stats = country_stats.sort_values('Total Streams', ascending=False)

    country_stats = country_stats[['Total Streams', 'Total Hours', 'Unique Tracks', 'First Listen', 'Last Listen']]
    country_stats.to_csv(DATA_OUTPUT_DIR / 'country_listening_stats.csv')
    print(f"  Saved: outputs/data/country_listening_stats.csv")

def generate_albums_report(df):
    """Generate detailed albums report"""
    print("\nGenerating albums report...")

    album_stats = df.groupby(['master_metadata_album_album_name', 'master_metadata_album_artist_name']).agg({
        'ms_played': ['count', 'sum'],
        'master_metadata_track_name': 'nunique',
        'ts': ['min', 'max']
    }).reset_index()

    album_stats.columns = ['Album', 'Artist', 'Total Streams', 'Total ms', 'Unique Tracks', 'First Listen', 'Last Listen']
    album_stats['Total Hours'] = album_stats['Total ms'] / 3600000
    album_stats = album_stats.sort_values('Total Streams', ascending=False)

    album_stats_export = album_stats[['Album', 'Artist', 'Total Streams', 'Total Hours', 'Unique Tracks', 'First Listen', 'Last Listen']]
    album_stats_export.head(100).to_csv(DATA_OUTPUT_DIR / 'top_100_albums.csv', index=False)
    print(f"  Saved: outputs/data/top_100_albums.csv")

def generate_reason_analysis(df):
    """Analyze reason_start and reason_end fields"""
    print("\nAnalyzing playback reasons...")

    # Reason start
    reason_start = df['reason_start'].value_counts().reset_index()
    reason_start.columns = ['Reason Start', 'Count']
    reason_start['Percentage'] = (reason_start['Count'] / len(df) * 100).round(2)

    reason_start.to_csv(DATA_OUTPUT_DIR / 'reason_start_analysis.csv', index=False)
    print(f"  Saved: outputs/data/reason_start_analysis.csv")

    # Reason end
    reason_end = df['reason_end'].value_counts().reset_index()
    reason_end.columns = ['Reason End', 'Count']
    reason_end['Percentage'] = (reason_end['Count'] / len(df) * 100).round(2)

    reason_end.to_csv(DATA_OUTPUT_DIR / 'reason_end_analysis.csv', index=False)
    print(f"  Saved: outputs/data/reason_end_analysis.csv")

def generate_daily_stats(df):
    """Generate daily statistics"""
    print("\nGenerating daily statistics...")

    df['date'] = df['ts'].dt.date
    df['hours'] = df['ms_played'] / 3600000

    daily_stats = df.groupby('date').agg({
        'ms_played': 'count',
        'hours': 'sum',
        'master_metadata_track_name': 'nunique',
        'master_metadata_album_artist_name': 'nunique'
    }).reset_index()

    daily_stats.columns = ['Date', 'Total Streams', 'Total Hours', 'Unique Tracks', 'Unique Artists']

    # Add day of week
    daily_stats['Date'] = pd.to_datetime(daily_stats['Date'])
    daily_stats['Day of Week'] = daily_stats['Date'].dt.day_name()
    daily_stats['Date'] = daily_stats['Date'].dt.strftime('%Y-%m-%d')

    daily_stats.to_csv(DATA_OUTPUT_DIR / 'daily_statistics.csv', index=False)
    print(f"  Saved: outputs/data/daily_statistics.csv")

    # Find peak days
    peak_streams = daily_stats.nlargest(10, 'Total Streams')[['Date', 'Day of Week', 'Total Streams', 'Total Hours', 'Unique Tracks']]
    peak_streams.to_csv(DATA_OUTPUT_DIR / 'top_10_streaming_days.csv', index=False)
    print(f"  Saved: outputs/data/top_10_streaming_days.csv")

def generate_track_completion_analysis(df):
    """Analyze track completion rates"""
    print("\nAnalyzing track completion rates...")

    # Group by track and calculate stats
    track_stats = df.groupby(['master_metadata_track_name', 'master_metadata_album_artist_name']).agg({
        'ms_played': ['count', 'mean', 'median', 'std'],
        'skipped': lambda x: (x == True).sum()
    }).reset_index()

    track_stats.columns = ['Track', 'Artist', 'Total Plays', 'Avg Duration (ms)', 'Median Duration (ms)', 'Std Duration (ms)', 'Times Skipped']

    # Calculate skip rate
    track_stats['Skip Rate (%)'] = (track_stats['Times Skipped'] / track_stats['Total Plays'] * 100).round(2)

    # Filter tracks with at least 5 plays
    track_stats_filtered = track_stats[track_stats['Total Plays'] >= 5].copy()

    # Convert durations to minutes
    track_stats_filtered['Avg Duration (min)'] = (track_stats_filtered['Avg Duration (ms)'] / 60000).round(2)
    track_stats_filtered = track_stats_filtered.sort_values('Total Plays', ascending=False)

    # Export most completed tracks (low skip rate)
    most_completed = track_stats_filtered.nsmallest(50, 'Skip Rate (%)')[
        ['Track', 'Artist', 'Total Plays', 'Avg Duration (min)', 'Skip Rate (%)']
    ]
    most_completed.to_csv(DATA_OUTPUT_DIR / 'most_completed_tracks.csv', index=False)
    print(f"  Saved: outputs/data/most_completed_tracks.csv")

    # Export most skipped tracks (high skip rate)
    most_skipped = track_stats_filtered.nlargest(50, 'Skip Rate (%)')[
        ['Track', 'Artist', 'Total Plays', 'Avg Duration (min)', 'Skip Rate (%)']
    ]
    most_skipped.to_csv(DATA_OUTPUT_DIR / 'most_skipped_tracks.csv', index=False)
    print(f"  Saved: outputs/data/most_skipped_tracks.csv")

def generate_listening_milestones(df):
    """Identify listening milestones"""
    print("\nIdentifying listening milestones...")

    df_sorted = df.sort_values('ts').reset_index(drop=True)
    df_sorted['cumulative_hours'] = (df_sorted['ms_played'].cumsum() / 3600000)

    milestones = []
    milestone_hours = [100, 500, 1000, 2000, 5000, 10000, 20000]

    for milestone in milestone_hours:
        idx = df_sorted[df_sorted['cumulative_hours'] >= milestone].index
        if len(idx) > 0:
            first_idx = idx[0]
            row = df_sorted.iloc[first_idx]
            milestones.append({
                'Milestone (Hours)': milestone,
                'Date Reached': row['ts'].strftime('%Y-%m-%d %H:%M:%S'),
                'Track Playing': row['master_metadata_track_name'],
                'Artist': row['master_metadata_album_artist_name'],
                'Stream Number': first_idx + 1
            })

    if milestones:
        milestones_df = pd.DataFrame(milestones)
        milestones_df.to_csv(DATA_OUTPUT_DIR / 'listening_milestones.csv', index=False)
        print(f"  Saved: outputs/data/listening_milestones.csv")
        print(f"  Reached {len(milestones)} milestones")
    else:
        print("  No major milestones reached yet")

def main():
    print("="*60)
    print("DETAILED STATISTICS AND REPORTS")
    print("="*60)

    audio_df, video_df = load_all_data()

    generate_overall_statistics(audio_df, video_df)
    generate_platform_report(audio_df)
    generate_country_report(audio_df)
    generate_albums_report(audio_df)
    generate_reason_analysis(audio_df)
    generate_daily_stats(audio_df)
    generate_track_completion_analysis(audio_df)
    generate_listening_milestones(audio_df)

    print("\n" + "="*60)
    print("DETAILED STATISTICS GENERATION COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
