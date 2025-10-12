"""
Advanced Listening Patterns Analysis
Analyzes detailed listening behavior patterns and habits
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

sns.set_style("whitegrid")
DATA_DIR = Path(__file__).parent.parent / 'data'
OUTPUT_DIR = Path(__file__).parent.parent / 'outputs'
IMAGES_DIR = OUTPUT_DIR / 'images'
DATA_OUTPUT_DIR = OUTPUT_DIR / 'data'

# Create output directories
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    df['hour'] = df['ts'].dt.hour
    df['day_of_week'] = df['ts'].dt.day_name()
    df['minutes_played'] = df['ms_played'] / 60000
    df['hours_played'] = df['ms_played'] / 3600000

    print(f"Loaded {len(df):,} records")
    return df

def analyze_binge_sessions(df):
    """Identify and analyze binge listening sessions"""
    print("\nAnalyzing binge listening sessions...")

    # Sort by timestamp
    df = df.sort_values('ts').copy()

    # Calculate time difference between consecutive streams
    df['time_diff'] = df['ts'].diff().dt.total_seconds() / 60  # in minutes

    # Define a session break as > 30 minutes between streams
    df['session_break'] = df['time_diff'] > 30
    df['session_id'] = df['session_break'].cumsum()

    # Analyze sessions
    sessions = df.groupby('session_id').agg({
        'ts': ['first', 'last', 'count'],
        'minutes_played': 'sum',
        'master_metadata_track_name': 'nunique'
    })

    sessions.columns = ['start_time', 'end_time', 'stream_count', 'total_minutes', 'unique_tracks']
    sessions['duration_minutes'] = (sessions['end_time'] - sessions['start_time']).dt.total_seconds() / 60

    # Filter meaningful sessions (at least 3 tracks)
    sessions = sessions[sessions['stream_count'] >= 3]

    # Find longest sessions
    top_sessions = sessions.nlargest(20, 'duration_minutes')

    # Export to CSV
    top_sessions.to_csv(DATA_OUTPUT_DIR / 'top_20_binge_sessions.csv')
    print(f"  Saved: outputs/data/top_20_binge_sessions.csv")

    # Session statistics
    session_stats = pd.DataFrame({
        'metric': [
            'Total Sessions',
            'Avg Session Duration (min)',
            'Avg Tracks Per Session',
            'Longest Session (hours)',
            'Most Tracks in Session'
        ],
        'value': [
            len(sessions),
            f"{sessions['duration_minutes'].mean():.1f}",
            f"{sessions['stream_count'].mean():.1f}",
            f"{sessions['duration_minutes'].max() / 60:.1f}",
            int(sessions['stream_count'].max())
        ]
    })
    session_stats.to_csv(DATA_OUTPUT_DIR / 'session_statistics.csv', index=False)
    print(f"  Saved: outputs/data/session_statistics.csv")

    # Visualize session distribution
    plt.figure(figsize=(12, 6))
    plt.hist(sessions['duration_minutes'], bins=50, edgecolor='black', alpha=0.7, color='teal')
    plt.xlabel('Session Duration (minutes)')
    plt.ylabel('Frequency')
    plt.title('Distribution of Listening Session Durations', fontsize=14, fontweight='bold')
    plt.axvline(sessions['duration_minutes'].median(), color='red', linestyle='--', label=f'Median: {sessions["duration_minutes"].median():.1f} min')
    plt.legend()
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'session_duration_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/session_duration_distribution.png")

def analyze_weekend_vs_weekday(df):
    """Compare weekend vs weekday listening patterns"""
    print("\nAnalyzing weekend vs weekday patterns...")

    df['is_weekend'] = df['day_of_week'].isin(['Saturday', 'Sunday'])

    comparison = df.groupby('is_weekend').agg({
        'ms_played': 'count',
        'hours_played': 'sum',
        'master_metadata_track_name': 'nunique',
        'master_metadata_album_artist_name': 'nunique'
    })

    comparison.index = ['Weekday', 'Weekend']
    comparison.columns = ['Total Streams', 'Total Hours', 'Unique Tracks', 'Unique Artists']

    # Calculate per-day averages
    weekday_count = df[~df['is_weekend']]['date'].nunique()
    weekend_count = df[df['is_weekend']]['date'].nunique()

    comparison['Avg Streams/Day'] = [
        comparison.loc['Weekday', 'Total Streams'] / weekday_count,
        comparison.loc['Weekend', 'Total Streams'] / weekend_count
    ]
    comparison['Avg Hours/Day'] = [
        comparison.loc['Weekday', 'Total Hours'] / weekday_count,
        comparison.loc['Weekend', 'Total Hours'] / weekend_count
    ]

    comparison.to_csv(DATA_OUTPUT_DIR / 'weekend_vs_weekday.csv')
    print(f"  Saved: outputs/data/weekend_vs_weekday.csv")

    # Visualize
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    comparison[['Avg Streams/Day', 'Avg Hours/Day']].plot(kind='bar', ax=axes[0], color=['skyblue', 'coral'], rot=0)
    axes[0].set_xlabel('Day Type')
    axes[0].set_ylabel('Count')
    axes[0].set_title('Average Daily Activity: Weekday vs Weekend', fontsize=12, fontweight='bold')
    axes[0].legend(['Avg Streams/Day', 'Avg Hours/Day'])
    axes[0].grid(True, alpha=0.3, axis='y')

    # Hourly pattern comparison
    hourly_weekend = df[df['is_weekend']].groupby('hour').size()
    hourly_weekday = df[~df['is_weekend']].groupby('hour').size()

    axes[1].plot(hourly_weekend.index, hourly_weekend.values, marker='o', label='Weekend', linewidth=2)
    axes[1].plot(hourly_weekday.index, hourly_weekday.values, marker='s', label='Weekday', linewidth=2)
    axes[1].set_xlabel('Hour of Day')
    axes[1].set_ylabel('Total Streams')
    axes[1].set_title('Hourly Listening Pattern: Weekday vs Weekend', fontsize=12, fontweight='bold')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'weekend_vs_weekday_patterns.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/weekend_vs_weekday_patterns.png")

def analyze_peak_listening_times(df):
    """Identify peak listening times and patterns"""
    print("\nAnalyzing peak listening times...")

    # Create hour-day heatmap data
    heatmap_data = df.groupby(['day_of_week', 'hour']).size().reset_index(name='streams')
    heatmap_pivot = heatmap_data.pivot(index='day_of_week', columns='hour', values='streams')

    # Reorder days
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_pivot = heatmap_pivot.reindex(day_order)

    plt.figure(figsize=(16, 8))
    sns.heatmap(heatmap_pivot, cmap='YlOrRd', annot=False, fmt='g', cbar_kws={'label': 'Number of Streams'})
    plt.xlabel('Hour of Day')
    plt.ylabel('Day of Week')
    plt.title('Listening Activity Heatmap: Day of Week vs Hour of Day', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'listening_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/listening_heatmap.png")

    # Find peak hours
    hourly = df.groupby('hour').size().sort_values(ascending=False)
    peak_hours = pd.DataFrame({
        'Hour': [f"{h}:00" for h in hourly.head(10).index],
        'Streams': hourly.head(10).values
    })
    peak_hours.to_csv(DATA_OUTPUT_DIR / 'peak_listening_hours.csv', index=False)
    print(f"  Saved: outputs/data/peak_listening_hours.csv")

def analyze_listening_streaks(df):
    """Analyze consecutive listening days and streaks"""
    print("\nAnalyzing listening streaks...")

    # Get unique listening dates
    dates = sorted(df['date'].unique())

    # Find streaks
    streaks = []
    current_streak = [dates[0]]

    for i in range(1, len(dates)):
        if (dates[i] - dates[i-1]).days == 1:
            current_streak.append(dates[i])
        else:
            if len(current_streak) >= 3:  # Only count streaks of 3+ days
                streaks.append({
                    'start_date': current_streak[0],
                    'end_date': current_streak[-1],
                    'days': len(current_streak)
                })
            current_streak = [dates[i]]

    # Check last streak
    if len(current_streak) >= 3:
        streaks.append({
            'start_date': current_streak[0],
            'end_date': current_streak[-1],
            'days': len(current_streak)
        })

    # Convert to DataFrame
    streaks_df = pd.DataFrame(streaks)
    if not streaks_df.empty:
        streaks_df = streaks_df.sort_values('days', ascending=False)
        streaks_df.to_csv(DATA_OUTPUT_DIR / 'listening_streaks.csv', index=False)
        print(f"  Saved: outputs/data/listening_streaks.csv")
        print(f"  Longest streak: {streaks_df.iloc[0]['days']} days")
    else:
        print("  No significant streaks found")

def analyze_repeat_behavior(df):
    """Analyze track repeat behavior"""
    print("\nAnalyzing repeat listening behavior...")

    # Find tracks played multiple times in a row
    df_sorted = df.sort_values('ts').copy()
    df_sorted['prev_track'] = df_sorted['master_metadata_track_name'].shift(1)
    df_sorted['is_repeat'] = df_sorted['master_metadata_track_name'] == df_sorted['prev_track']

    # Count consecutive repeats
    df_sorted['repeat_group'] = (df_sorted['is_repeat'] != df_sorted['is_repeat'].shift()).cumsum()
    repeat_groups = df_sorted[df_sorted['is_repeat']].groupby('repeat_group').agg({
        'master_metadata_track_name': ['first', 'count'],
        'master_metadata_album_artist_name': 'first'
    })

    if not repeat_groups.empty:
        repeat_groups.columns = ['track', 'repeat_count', 'artist']
        repeat_groups['repeat_count'] += 1  # Include the first play
        repeat_groups = repeat_groups.sort_values('repeat_count', ascending=False)

        # Top repeated tracks
        top_repeats = repeat_groups.head(30)
        top_repeats.to_csv(DATA_OUTPUT_DIR / 'most_repeated_tracks.csv')
        print(f"  Saved: outputs/data/most_repeated_tracks.csv")
        print(f"  Max consecutive repeats: {repeat_groups['repeat_count'].max()} times")

def analyze_monthly_diversity(df):
    """Analyze listening diversity by month"""
    print("\nAnalyzing monthly listening diversity...")

    df['year_month'] = df['ts'].dt.to_period('M')

    monthly_diversity = df.groupby('year_month').agg({
        'master_metadata_track_name': 'nunique',
        'master_metadata_album_artist_name': 'nunique',
        'master_metadata_album_album_name': 'nunique',
        'ms_played': 'count'
    })

    monthly_diversity.columns = ['Unique Tracks', 'Unique Artists', 'Unique Albums', 'Total Streams']
    monthly_diversity['Diversity Score'] = (
        monthly_diversity['Unique Artists'] / monthly_diversity['Total Streams'] * 100
    )

    monthly_diversity.index = monthly_diversity.index.astype(str)
    monthly_diversity.to_csv(DATA_OUTPUT_DIR / 'monthly_diversity.csv')
    print(f"  Saved: outputs/data/monthly_diversity.csv")

    # Visualize
    fig, ax = plt.subplots(figsize=(14, 6))
    ax2 = ax.twinx()

    ax.bar(monthly_diversity.index, monthly_diversity['Unique Artists'], alpha=0.7, color='steelblue', label='Unique Artists')
    ax2.plot(monthly_diversity.index, monthly_diversity['Diversity Score'], color='red', marker='o', linewidth=2, label='Diversity Score')

    ax.set_xlabel('Month')
    ax.set_ylabel('Unique Artists', color='steelblue')
    ax2.set_ylabel('Diversity Score (%)', color='red')
    ax.tick_params(axis='x', rotation=45)

    plt.title('Monthly Listening Diversity', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left')
    ax2.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(IMAGES_DIR / 'monthly_diversity_chart.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: outputs/images/monthly_diversity_chart.png")

def main():
    print("="*60)
    print("ADVANCED LISTENING PATTERNS ANALYSIS")
    print("="*60)

    df = load_and_preprocess()

    analyze_binge_sessions(df)
    analyze_weekend_vs_weekday(df)
    analyze_peak_listening_times(df)
    analyze_listening_streaks(df)
    analyze_repeat_behavior(df)
    analyze_monthly_diversity(df)

    print("\n" + "="*60)
    print("PATTERNS ANALYSIS COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
