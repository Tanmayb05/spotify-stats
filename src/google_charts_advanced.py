"""
Advanced Google Charts Dashboard
Creates more advanced interactive visualizations
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
    df['year_month'] = df['ts'].dt.to_period('M')
    df['day_of_week'] = df['ts'].dt.day_name()
    df['minutes_played'] = df['ms_played'] / 60000
    df['hours_played'] = df['ms_played'] / 3600000

    print(f"Loaded {len(df):,} records")
    return df

def create_html_template():
    """Create HTML template"""
    return """
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
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #1DB954;
            text-align: center;
            margin-bottom: 10px;
            font-size: 3em;
        }}
        h2 {{
            color: #333;
            border-left: 5px solid #1DB954;
            padding-left: 15px;
            margin-top: 50px;
            margin-bottom: 20px;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 40px;
            font-size: 1.2em;
        }}
        .chart {{
            margin: 30px 0;
            border: 2px solid #f0f0f0;
            border-radius: 10px;
            padding: 20px;
            background-color: #fafafa;
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin: 30px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding-top: 30px;
            border-top: 2px solid #ddd;
            color: #999;
        }}
        @media (max-width: 768px) {{
            .chart-row {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <p class="subtitle">{subtitle}</p>
        {content}
        <div class="footer">
            <p>Generated on {timestamp}</p>
        </div>
    </div>
</body>
</html>
"""

def create_top_tracks_table(df):
    """Create top tracks interactive table"""
    print("\nCreating top tracks table...")

    df['track_artist'] = df['master_metadata_track_name'] + ' - ' + df['master_metadata_album_artist_name']
    top_tracks = df['track_artist'].value_counts().head(30)

    data_rows = []
    for i, (track, count) in enumerate(top_tracks.items(), 1):
        track_escaped = track.replace("'", "\\'").replace('"', '\\"') if track else "Unknown"
        data_rows.append(f"[{i}, '{track_escaped}', {count}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Top 30 Tracks - Interactive Table</h2>
        <div id="table_top_tracks" class="chart"></div>
        <script type="text/javascript">
            google.charts.load('current', {{'packages':['table']}});
            google.charts.setOnLoadCallback(drawTopTracksTable);

            function drawTopTracksTable() {{
                var data = google.visualization.arrayToDataTable([
                    ['Rank', 'Track - Artist', 'Streams'],
                    {data_string}
                ]);

                var table = new google.visualization.Table(document.getElementById('table_top_tracks'));

                table.draw(data, {{
                    showRowNumber: false,
                    width: '100%',
                    height: '100%',
                    cssClassNames: {{
                        headerRow: 'header-row',
                        tableRow: 'table-row',
                        oddTableRow: 'odd-row'
                    }}
                }});
            }}
        </script>
"""
    return html

def create_heatmap_chart(df):
    """Create day-hour heatmap"""
    print("Creating day-hour heatmap...")

    # Create hour-day heatmap data
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_data = df.groupby(['day_of_week', 'hour']).size().reset_index(name='streams')

    # Prepare data for Google Charts
    hours = sorted(df['hour'].unique())
    header_cols = ', '.join([f"'{day}'" for day in day_order])
    data_rows = [f"['Hour', {header_cols}]"]

    for hour in hours:
        row_data = [f"'{hour}:00'"]
        for day in day_order:
            streams = heatmap_data[
                (heatmap_data['day_of_week'] == day) &
                (heatmap_data['hour'] == hour)
            ]['streams'].values
            value = int(streams[0]) if len(streams) > 0 else 0
            row_data.append(str(value))
        data_rows.append(f"[{', '.join(row_data)}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Listening Heatmap - Day vs Hour</h2>
        <div id="chart_heatmap" class="chart" style="height: 700px;"></div>
        <script type="text/javascript">
            google.charts.load('current', {{'packages':['table']}});
            google.charts.setOnLoadCallback(drawHeatmap);

            function drawHeatmap() {{
                var data = google.visualization.arrayToDataTable([
                    {data_string}
                ]);

                var table = new google.visualization.Table(document.getElementById('chart_heatmap'));

                // Calculate max value for color scaling
                var maxVal = 0;
                for (var i = 1; i < data.getNumberOfRows(); i++) {{
                    for (var j = 1; j < data.getNumberOfColumns(); j++) {{
                        maxVal = Math.max(maxVal, data.getValue(i, j));
                    }}
                }}

                // Create formatters for color coding
                var formatters = [];
                for (var j = 1; j < data.getNumberOfColumns(); j++) {{
                    var formatter = new google.visualization.ColorFormat();
                    formatter.addGradientRange(0, maxVal, '#ffffff', '#e7f5fe', '#1976d2');
                    formatter.format(data, j);
                }}

                table.draw(data, {{
                    showRowNumber: false,
                    width: '100%',
                    allowHtml: true,
                    cssClassNames: {{
                        headerRow: 'header-row',
                        tableRow: 'table-row'
                    }}
                }});
            }}
        </script>
"""
    return html

def create_artist_evolution_chart(df):
    """Create stacked area chart for top artists over time"""
    print("Creating artist evolution chart...")

    top_artists = df['master_metadata_album_artist_name'].value_counts().head(10).index
    df_top = df[df['master_metadata_album_artist_name'].isin(top_artists)]

    artist_monthly = df_top.groupby(['year_month', 'master_metadata_album_artist_name']).size().reset_index(name='streams')
    artist_pivot = artist_monthly.pivot(index='year_month', columns='master_metadata_album_artist_name', values='streams').fillna(0)

    # Prepare data
    months = [str(m) for m in artist_pivot.index]
    artists = list(artist_pivot.columns)

    # Header row
    header = "['Month', " + ", ".join([f"'{artist.replace(chr(39), chr(92)+chr(39))}'" for artist in artists]) + "]"

    # Data rows
    data_rows = [header]
    for month_idx, month in enumerate(months):
        values = [f"'{month}'"]
        for artist in artists:
            values.append(str(int(artist_pivot.iloc[month_idx][artist])))
        data_rows.append(f"[{', '.join(values)}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Top 10 Artists Evolution Over Time</h2>
        <div id="chart_artist_evolution" class="chart" style="height: 600px;"></div>
        <script type="text/javascript">
            google.charts.load('current', {{'packages':['corechart']}});
            google.charts.setOnLoadCallback(drawArtistEvolution);

            function drawArtistEvolution() {{
                var data = google.visualization.arrayToDataTable([
                    {data_string}
                ]);

                var options = {{
                    title: 'How Your Top Artists Changed Over Time',
                    chartArea: {{width: '75%', height: '70%'}},
                    isStacked: true,
                    legend: {{position: 'right', maxLines: 3}},
                    hAxis: {{
                        title: 'Month',
                        slantedText: true,
                        slantedTextAngle: 45
                    }},
                    vAxis: {{title: 'Number of Streams'}},
                    colors: ['#1DB954', '#1ed760', '#169c46', '#ff6b6b', '#4ecdc4',
                            '#ffd93d', '#a29bfe', '#fd79a8', '#fdcb6e', '#6c5ce7']
                }};

                var chart = new google.visualization.AreaChart(document.getElementById('chart_artist_evolution'));
                chart.draw(data, options);
            }}
        </script>
"""
    return html

def create_treemap_chart(df):
    """Create treemap for artists"""
    print("Creating artist treemap...")

    top_artists = df['master_metadata_album_artist_name'].value_counts().head(20)

    data_rows = ["['Artist', 'Parent', 'Streams', 'Color']", "['All Artists', null, 0, 0]"]
    max_streams = top_artists.max()

    for artist, count in top_artists.items():
        artist_escaped = artist.replace("'", "\\'") if artist else "Unknown"
        color_value = int((count / max_streams) * 100)
        data_rows.append(f"['{artist_escaped}', 'All Artists', {count}, {color_value}]")

    data_string = ",\n            ".join(data_rows)

    html = f"""
        <h2>Top 20 Artists - Treemap View</h2>
        <div id="chart_treemap" class="chart" style="height: 600px;"></div>
        <script type="text/javascript">
            google.charts.load('current', {{'packages':['treemap']}});
            google.charts.setOnLoadCallback(drawTreemap);

            function drawTreemap() {{
                var data = google.visualization.arrayToDataTable([
                    {data_string}
                ]);

                var options = {{
                    minColor: '#e8f5e9',
                    midColor: '#4caf50',
                    maxColor: '#1b5e20',
                    headerHeight: 20,
                    fontColor: 'black',
                    showScale: true,
                    generateTooltip: showFullTooltip
                }};

                function showFullTooltip(row, size, value) {{
                    return '<div style="background:#fd9; padding:10px; border-style:solid">' +
                           '<b>' + data.getValue(row, 0) + '</b><br>' +
                           'Streams: ' + size.toLocaleString() + '</div>';
                }}

                var tree = new google.visualization.TreeMap(document.getElementById('chart_treemap'));
                tree.draw(data, options);
            }}
        </script>
"""
    return html

def create_advanced_dashboard(df):
    """Create advanced dashboard with multiple visualizations"""
    print("\nGenerating advanced dashboard...")

    template = create_html_template()

    content = create_top_tracks_table(df)
    content += create_heatmap_chart(df)
    content += create_artist_evolution_chart(df)
    content += create_treemap_chart(df)

    html = template.format(
        title="Spotify Advanced Analytics",
        subtitle="Detailed Interactive Visualizations",
        content=content,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

    output_file = DASHBOARDS_DIR / 'spotify_advanced_dashboard.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Saved: {output_file}")
    return output_file

def main():
    print("="*60)
    print("ADVANCED GOOGLE CHARTS DASHBOARD")
    print("="*60)

    df = load_data()
    create_advanced_dashboard(df)

    print("\n" + "="*60)
    print("ADVANCED DASHBOARD COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
