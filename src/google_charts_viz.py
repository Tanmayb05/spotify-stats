"""
Google Charts Visualizations
Generates interactive HTML visualizations using Google Charts
"""

import json
import pandas as pd
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

def create_html_header(title):
    """Create HTML header with Google Charts library"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1DB954;
            text-align: center;
            margin-bottom: 10px;
        }}
        h2 {{
            color: #333;
            border-bottom: 2px solid #1DB954;
            padding-bottom: 10px;
            margin-top: 40px;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 40px;
        }}
        .chart {{
            margin: 20px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .stat-card h3 {{
            margin: 0;
            font-size: 2em;
            font-weight: bold;
        }}
        .stat-card p {{
            margin: 10px 0 0 0;
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
"""

def create_html_footer():
    """Create HTML footer"""
    return f"""
        <div class="footer">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Spotify Streaming History Analysis</p>
        </div>
    </div>
</body>
</html>
"""

def create_top_artists_chart(df):
    """Create top artists bar chart"""
    print("\nCreating top artists chart...")

    top_artists = df['master_metadata_album_artist_name'].value_counts().head(20)

    data_rows = []
    for artist, count in top_artists.items():
        # Escape single quotes in artist names
        artist_escaped = artist.replace("'", "\\'") if artist else "Unknown"
        data_rows.append(f"['{artist_escaped}', {count}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Top 20 Artists</h2>
        <div id="chart_top_artists" class="chart" style="height: 600px;"></div>
        <script type="text/javascript">
            google.charts.load('current', {{'packages':['corechart']}});
            google.charts.setOnLoadCallback(drawTopArtists);

            function drawTopArtists() {{
                var data = google.visualization.arrayToDataTable([
                    ['Artist', 'Streams'],
                    {data_string}
                ]);

                var options = {{
                    title: 'Most Streamed Artists',
                    chartArea: {{width: '60%', height: '80%'}},
                    hAxis: {{title: 'Number of Streams'}},
                    vAxis: {{title: 'Artist'}},
                    colors: ['#1DB954'],
                    legend: {{position: 'none'}},
                    animation: {{
                        startup: true,
                        duration: 1000,
                        easing: 'out'
                    }}
                }};

                var chart = new google.visualization.BarChart(document.getElementById('chart_top_artists'));
                chart.draw(data, options);
            }}
        </script>
"""
    return html

def create_listening_over_time_chart(df):
    """Create listening over time line chart"""
    print("Creating listening over time chart...")

    df['year_month'] = df['ts'].dt.to_period('M')
    monthly_stats = df.groupby('year_month').agg({
        'ms_played': 'count',
        'hours_played': 'sum'
    }).reset_index()
    monthly_stats['year_month'] = monthly_stats['year_month'].astype(str)

    data_rows = []
    for _, row in monthly_stats.iterrows():
        data_rows.append(f"['{row['year_month']}', {row['ms_played']}, {row['hours_played']:.2f}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Listening Activity Over Time</h2>
        <div id="chart_over_time" class="chart" style="height: 500px;"></div>
        <script type="text/javascript">
            google.charts.setOnLoadCallback(drawOverTime);

            function drawOverTime() {{
                var data = google.visualization.arrayToDataTable([
                    ['Month', 'Streams', 'Hours'],
                    {data_string}
                ]);

                var options = {{
                    title: 'Monthly Listening Trends',
                    curveType: 'function',
                    legend: {{position: 'bottom'}},
                    chartArea: {{width: '80%', height: '70%'}},
                    series: {{
                        0: {{targetAxisIndex: 0, color: '#1DB954'}},
                        1: {{targetAxisIndex: 1, color: '#FF6B6B'}}
                    }},
                    vAxes: {{
                        0: {{title: 'Number of Streams'}},
                        1: {{title: 'Hours Listened'}}
                    }},
                    hAxis: {{
                        title: 'Month',
                        slantedText: true,
                        slantedTextAngle: 45
                    }}
                }};

                var chart = new google.visualization.LineChart(document.getElementById('chart_over_time'));
                chart.draw(data, options);
            }}
        </script>
"""
    return html

def create_hourly_pattern_chart(df):
    """Create hourly listening pattern chart"""
    print("Creating hourly pattern chart...")

    hourly_stats = df.groupby('hour').size().reset_index(name='streams')

    data_rows = []
    for _, row in hourly_stats.iterrows():
        data_rows.append(f"['{row['hour']}:00', {row['streams']}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Listening by Hour of Day</h2>
        <div id="chart_hourly" class="chart" style="height: 400px;"></div>
        <script type="text/javascript">
            google.charts.setOnLoadCallback(drawHourly);

            function drawHourly() {{
                var data = google.visualization.arrayToDataTable([
                    ['Hour', 'Streams'],
                    {data_string}
                ]);

                var options = {{
                    title: 'Listening Activity by Hour',
                    chartArea: {{width: '80%', height: '70%'}},
                    legend: {{position: 'none'}},
                    colors: ['#4ECDC4'],
                    hAxis: {{title: 'Hour of Day'}},
                    vAxis: {{title: 'Number of Streams'}}
                }};

                var chart = new google.visualization.ColumnChart(document.getElementById('chart_hourly'));
                chart.draw(data, options);
            }}
        </script>
"""
    return html

def create_day_of_week_chart(df):
    """Create day of week pattern chart"""
    print("Creating day of week chart...")

    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_stats = df.groupby('day_of_week').size().reindex(day_order).reset_index(name='streams')

    data_rows = []
    for _, row in day_stats.iterrows():
        data_rows.append(f"['{row['day_of_week'][:3]}', {row['streams']}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Listening by Day of Week</h2>
        <div id="chart_daily" class="chart" style="height: 400px;"></div>
        <script type="text/javascript">
            google.charts.setOnLoadCallback(drawDaily);

            function drawDaily() {{
                var data = google.visualization.arrayToDataTable([
                    ['Day', 'Streams'],
                    {data_string}
                ]);

                var options = {{
                    title: 'Listening Activity by Day of Week',
                    chartArea: {{width: '80%', height: '70%'}},
                    legend: {{position: 'none'}},
                    colors: ['#FFD93D'],
                    hAxis: {{title: 'Day of Week'}},
                    vAxis: {{title: 'Number of Streams'}}
                }};

                var chart = new google.visualization.ColumnChart(document.getElementById('chart_daily'));
                chart.draw(data, options);
            }}
        </script>
"""
    return html

def create_platform_pie_chart(df):
    """Create platform distribution pie chart"""
    print("Creating platform pie chart...")

    platform_stats = df['platform'].value_counts().head(10)

    data_rows = []
    for platform, count in platform_stats.items():
        platform_escaped = platform.replace("'", "\\'") if platform else "Unknown"
        data_rows.append(f"['{platform_escaped}', {count}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Platform Usage Distribution</h2>
        <div id="chart_platform" class="chart" style="height: 500px;"></div>
        <script type="text/javascript">
            google.charts.setOnLoadCallback(drawPlatform);

            function drawPlatform() {{
                var data = google.visualization.arrayToDataTable([
                    ['Platform', 'Streams'],
                    {data_string}
                ]);

                var options = {{
                    title: 'Top 10 Platforms Used',
                    is3D: true,
                    chartArea: {{width: '90%', height: '80%'}},
                    colors: ['#1DB954', '#1ed760', '#169c46', '#117a37', '#0d5829',
                            '#ff6b6b', '#ee5a6f', '#c44569', '#f79f1f', '#ffa502']
                }};

                var chart = new google.visualization.PieChart(document.getElementById('chart_platform'));
                chart.draw(data, options);
            }}
        </script>
"""
    return html

def create_yearly_comparison_chart(df):
    """Create yearly comparison chart"""
    print("Creating yearly comparison chart...")

    yearly_stats = df.groupby('year').agg({
        'ms_played': 'count',
        'hours_played': 'sum'
    }).reset_index()
    yearly_stats.columns = ['year', 'streams', 'hours']

    data_rows = []
    for _, row in yearly_stats.iterrows():
        data_rows.append(f"['{int(row['year'])}', {row['streams']}, {row['hours']:.2f}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Yearly Comparison</h2>
        <div id="chart_yearly" class="chart" style="height: 500px;"></div>
        <script type="text/javascript">
            google.charts.setOnLoadCallback(drawYearly);

            function drawYearly() {{
                var data = google.visualization.arrayToDataTable([
                    ['Year', 'Streams', 'Hours'],
                    {data_string}
                ]);

                var options = {{
                    title: 'Listening Activity by Year',
                    chartArea: {{width: '75%', height: '70%'}},
                    legend: {{position: 'bottom'}},
                    series: {{
                        0: {{targetAxisIndex: 0, color: '#1DB954', type: 'bars'}},
                        1: {{targetAxisIndex: 1, color: '#FF6B6B', type: 'line'}}
                    }},
                    vAxes: {{
                        0: {{title: 'Number of Streams'}},
                        1: {{title: 'Hours Listened'}}
                    }},
                    hAxis: {{title: 'Year'}}
                }};

                var chart = new google.visualization.ComboChart(document.getElementById('chart_yearly'));
                chart.draw(data, options);
            }}
        </script>
"""
    return html

def create_statistics_cards(df):
    """Create summary statistics cards"""
    print("Creating statistics cards...")

    total_streams = len(df)
    total_hours = df['hours_played'].sum()
    unique_tracks = df['master_metadata_track_name'].nunique()
    unique_artists = df['master_metadata_album_artist_name'].nunique()
    avg_per_day = total_streams / (df['ts'].max() - df['ts'].min()).days

    html = f"""
        <p class="subtitle">Complete Overview of Your Spotify Listening History</p>
        <div class="stats">
            <div class="stat-card">
                <h3>{total_streams:,}</h3>
                <p>Total Streams</p>
            </div>
            <div class="stat-card">
                <h3>{total_hours:,.0f}</h3>
                <p>Hours Listened</p>
            </div>
            <div class="stat-card">
                <h3>{unique_artists:,}</h3>
                <p>Unique Artists</p>
            </div>
            <div class="stat-card">
                <h3>{unique_tracks:,}</h3>
                <p>Unique Tracks</p>
            </div>
            <div class="stat-card">
                <h3>{avg_per_day:.0f}</h3>
                <p>Avg Streams/Day</p>
            </div>
            <div class="stat-card">
                <h3>{(total_hours/24):,.0f}</h3>
                <p>Days Listened</p>
            </div>
        </div>
"""
    return html

def main():
    print("="*60)
    print("GOOGLE CHARTS VISUALIZATIONS")
    print("="*60)

    df = load_data()

    # Create complete dashboard HTML
    html_content = create_html_header("Spotify Streaming History Dashboard")
    html_content += create_statistics_cards(df)
    html_content += create_top_artists_chart(df)
    html_content += create_listening_over_time_chart(df)
    html_content += create_hourly_pattern_chart(df)
    html_content += create_day_of_week_chart(df)
    html_content += create_platform_pie_chart(df)
    html_content += create_yearly_comparison_chart(df)
    html_content += create_html_footer()

    # Save main dashboard
    output_file = DASHBOARDS_DIR / 'spotify_dashboard.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✓ Saved: {output_file}")
    print(f"\nOpen {output_file} in your browser to view interactive dashboard!")

    print("\n" + "="*60)
    print("GOOGLE CHARTS VISUALIZATIONS COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
