#!/usr/bin/env python3
"""
Load Spotify streaming JSON files into Supabase PostgreSQL

This script:
1. Reads all streaming_*.json files from data/ directory
2. Validates and transforms the data
3. Batch inserts into Supabase streaming_history table
4. Refreshes materialized views
5. Provides progress tracking and error handling
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys

CURRENT_PATH = Path(__file__).resolve()
PACKAGE_ROOT = CURRENT_PATH.parent.parent

# Add apps/api to path for imports
sys.path.append(str(PACKAGE_ROOT))


def _find_project_root() -> Path:
    """Locate repository root by searching for known directories."""
    for parent in CURRENT_PATH.parents:
        if (parent / 'data').exists():
            return parent
    return PACKAGE_ROOT

try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Please run: pip install supabase python-dotenv")
    sys.exit(1)


# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = _find_project_root()
DATA_DIR = PROJECT_ROOT / 'data'
BATCH_SIZE = 1000  # Insert in batches for performance
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')  # Use service key for admin operations


class StreamingDataLoader:
    """Load streaming data from JSON files into Supabase"""

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
            )

        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.total_records = 0
        self.successful_inserts = 0
        self.failed_inserts = 0
        self.errors: List[str] = []

    def load_json_files(self) -> List[Dict[str, Any]]:
        """Load all streaming JSON files from data directory"""
        print(f"📂 Loading JSON files from {DATA_DIR}")

        # Find all audio streaming files (exclude video)
        audio_files = sorted(DATA_DIR.glob('streaming_[0-9]*.json'))

        if not audio_files:
            print(f"❌ No streaming_*.json files found in {DATA_DIR}")
            return []

        all_records = []
        for file_path in audio_files:
            print(f"   Loading {file_path.name}...")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_records.extend(data)
                    print(f"   ✓ Loaded {len(data):,} records")
            except Exception as e:
                error_msg = f"Failed to load {file_path.name}: {str(e)}"
                print(f"   ❌ {error_msg}")
                self.errors.append(error_msg)

        print(f"\n✅ Total records loaded: {len(all_records):,}")
        self.total_records = len(all_records)
        return all_records

    def transform_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform JSON record to database format"""
        try:
            # Validate required fields
            if not record.get('ts'):
                return None

            # Transform to database schema
            transformed = {
                'ts': record['ts'],
                'platform': record.get('platform'),
                'ms_played': record.get('ms_played', 0),
                'conn_country': record.get('conn_country'),
                'ip_addr': record.get('ip_addr'),
                'master_metadata_track_name': record.get('master_metadata_track_name'),
                'master_metadata_album_artist_name': record.get('master_metadata_album_artist_name'),
                'master_metadata_album_album_name': record.get('master_metadata_album_album_name'),
                'spotify_track_uri': record.get('spotify_track_uri'),
                'episode_name': record.get('episode_name'),
                'episode_show_name': record.get('episode_show_name'),
                'spotify_episode_uri': record.get('spotify_episode_uri'),
                'audiobook_title': record.get('audiobook_title'),
                'audiobook_uri': record.get('audiobook_uri'),
                'audiobook_chapter_uri': record.get('audiobook_chapter_uri'),
                'audiobook_chapter_title': record.get('audiobook_chapter_title'),
                'reason_start': record.get('reason_start'),
                'reason_end': record.get('reason_end'),
                'shuffle': record.get('shuffle', False),
                'skipped': record.get('skipped', False),
                'offline': record.get('offline', False),
                'offline_timestamp': record.get('offline_timestamp'),
                'incognito_mode': record.get('incognito_mode', False),
            }

            return transformed

        except Exception as e:
            self.errors.append(f"Transform error: {str(e)}")
            return None

    def check_existing_data(self) -> int:
        """Check if table already has data"""
        try:
            response = self.supabase.table('streaming_history').select('id', count='exact').limit(1).execute()
            count = response.count if hasattr(response, 'count') else 0
            return count or 0
        except Exception as e:
            print(f"⚠️  Could not check existing data: {str(e)}")
            return 0

    def clear_table(self):
        """Clear all data from streaming_history table"""
        print("\n🗑️  Clearing existing data...")
        try:
            # Supabase doesn't have a direct truncate, so we delete all
            # For large datasets, it's better to use SQL directly
            response = self.supabase.rpc('truncate_streaming_history').execute()
            print("✅ Table cleared")
        except Exception as e:
            print(f"⚠️  Note: Could not clear table via RPC: {str(e)}")
            print("   You may need to manually clear the table or use the SQL console")

    def insert_batch(self, batch: List[Dict[str, Any]]) -> int:
        """Insert a batch of records"""
        if not batch:
            return 0

        try:
            response = self.supabase.table('streaming_history').insert(batch).execute()
            return len(batch)
        except Exception as e:
            error_msg = f"Batch insert failed: {str(e)}"
            self.errors.append(error_msg)
            print(f"   ❌ {error_msg}")
            return 0

    def load_to_database(self, records: List[Dict[str, Any]], skip_duplicates: bool = True):
        """Load records into Supabase in batches"""
        print(f"\n📤 Inserting {len(records):,} records into Supabase...")
        print(f"   Batch size: {BATCH_SIZE}")

        # Transform records
        print("   Transforming records...")
        transformed_records = []
        for record in records:
            transformed = self.transform_record(record)
            if transformed:
                transformed_records.append(transformed)

        print(f"   ✓ {len(transformed_records):,} records ready for insert")

        # Insert in batches
        batches = [
            transformed_records[i:i + BATCH_SIZE]
            for i in range(0, len(transformed_records), BATCH_SIZE)
        ]

        print(f"   Processing {len(batches)} batches...")

        for i, batch in enumerate(batches, 1):
            success_count = self.insert_batch(batch)
            self.successful_inserts += success_count

            # Progress indicator
            progress = (i / len(batches)) * 100
            print(f"   [{i}/{len(batches)}] {progress:.1f}% - Inserted {self.successful_inserts:,} records", end='\r')

        print(f"\n✅ Inserted {self.successful_inserts:,} records")

        if self.errors:
            print(f"\n⚠️  {len(self.errors)} errors occurred (see details below)")

    def refresh_materialized_views(self):
        """Refresh materialized views for performance"""
        print("\n🔄 Refreshing materialized views...")

        views = ['monthly_stats', 'top_artists', 'top_tracks']

        for view_name in views:
            try:
                # Execute refresh via RPC or raw SQL
                # Supabase client doesn't have direct REFRESH MATERIALIZED VIEW
                # We'll use a custom RPC function
                print(f"   Refreshing {view_name}...")
                self.supabase.rpc(f'refresh_{view_name}').execute()
                print(f"   ✓ {view_name} refreshed")
            except Exception as e:
                print(f"   ⚠️  Could not refresh {view_name}: {str(e)}")
                print(f"      Run manually: REFRESH MATERIALIZED VIEW {view_name};")

    def verify_data(self):
        """Verify data was loaded correctly"""
        print("\n🔍 Verifying data...")

        try:
            # Count total records
            response = self.supabase.table('streaming_history').select('*', count='exact').limit(1).execute()
            total_count = response.count if hasattr(response, 'count') else 0

            print(f"   Total records in database: {total_count:,}")

            # Get date range
            response = self.supabase.rpc('get_date_range').execute()
            if response.data:
                date_range = response.data[0] if isinstance(response.data, list) else response.data
                print(f"   Date range: {date_range}")

            # Sample query: top artist
            response = self.supabase.table('streaming_history') \
                .select('master_metadata_album_artist_name') \
                .not_.is_('master_metadata_album_artist_name', 'null') \
                .limit(1000) \
                .execute()

            if response.data:
                from collections import Counter
                artists = [r['master_metadata_album_artist_name'] for r in response.data]
                top_artist = Counter(artists).most_common(1)[0]
                print(f"   Sample top artist: {top_artist[0]} ({top_artist[1]} plays in sample)")

            print("✅ Verification complete")

        except Exception as e:
            print(f"⚠️  Verification failed: {str(e)}")

    def print_summary(self):
        """Print summary of the load operation"""
        print("\n" + "="*60)
        print("📊 LOAD SUMMARY")
        print("="*60)
        print(f"Total records processed: {self.total_records:,}")
        print(f"Successfully inserted:   {self.successful_inserts:,}")
        print(f"Failed inserts:          {self.failed_inserts:,}")

        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"   - {error}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more")
        else:
            print("\n✅ No errors!")

        print("="*60)


def main():
    """Main execution function"""
    print("="*60)
    print("🎵 Spotify Streaming Data → Supabase Migration")
    print("="*60)

    try:
        # Initialize loader
        loader = StreamingDataLoader()

        # Check for existing data
        existing_count = loader.check_existing_data()
        if existing_count > 0:
            print(f"\n⚠️  Table already contains {existing_count:,} records")
            response = input("Do you want to clear and reload? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                loader.clear_table()
            else:
                print("❌ Aborted by user")
                return

        # Load JSON files
        records = loader.load_json_files()

        if not records:
            print("❌ No records to load")
            return

        # Insert into database
        loader.load_to_database(records)

        # Refresh views
        loader.refresh_materialized_views()

        # Verify
        loader.verify_data()

        # Print summary
        loader.print_summary()

        print("\n✅ Migration complete!")
        print("\nNext steps:")
        print("1. Update .env.example with Supabase configuration")
        print("2. Update data_loader.py to use Supabase instead of JSON files")
        print("3. Test API endpoints with new data source")

    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
