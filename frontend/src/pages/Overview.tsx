import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Grid,
} from '@mui/material';
import {
  MusicNote,
  Person,
  Album,
  AccessTime,
  HeadsetOff,
} from '@mui/icons-material';
import { LineChart } from '@mui/x-charts/LineChart';
import { PieChart } from '@mui/x-charts/PieChart';
import { BarChart } from '@mui/x-charts/BarChart';
import StatCard from '../components/StatCard';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import { formatNumber, formatCompact } from '../utils/format';
import type {
  OverviewStats,
  TopArtist,
  TopTrack,
  MonthlyData,
  PlatformStat,
} from '../types/api';

export default function Overview() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [topArtists, setTopArtists] = useState<TopArtist[]>([]);
  const [topTracks, setTopTracks] = useState<TopTrack[]>([]);
  const [monthlyData, setMonthlyData] = useState<MonthlyData[]>([]);
  const [platformStats, setPlatformStats] = useState<PlatformStat[]>([]);
  const { setError } = useAppStore();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all data in parallel
      const [
        overviewData,
        artistsData,
        tracksData,
        monthlyDataRes,
        platformsData,
      ] = await Promise.all([
        api.getOverviewStats(),
        api.getTopArtists(10),
        api.getTopTracks(10),
        api.getMonthlyData(),
        api.getPlatformStats(),
      ]);

      setStats(overviewData);
      setTopArtists(artistsData);
      setTopTracks(tracksData);
      setMonthlyData(monthlyDataRes);
      setPlatformStats(platformsData);
    } catch (error) {
      console.error('Error loading overview data:', error);
      setError(
        error instanceof Error ? error.message : 'Failed to load overview data'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ pb: 4 }}>
      <Typography variant="h3" gutterBottom fontWeight={700} sx={{ mb: 2 }}>
        Overview
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 6, fontSize: '1.1rem' }}>
        Your complete Spotify streaming history at a glance.
      </Typography>

      {/* Stat Cards */}
      <Grid container spacing={{ xs: 2, md: 3 }} sx={{ mb: 8 }}>
        <Grid xs={12} sm={6} md={4} lg={3} sx={{ display: 'flex' }}>
          <StatCard
            title="Total Streams"
            value={stats ? formatNumber(stats.total_streams) : '—'}
            icon={<MusicNote sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid xs={12} sm={6} md={4} lg={3} sx={{ display: 'flex' }}>
          <StatCard
            title="Listening Time"
            value={stats ? formatCompact(stats.total_hours) + 'h' : '—'}
            subtitle={stats ? `${formatNumber(stats.total_hours)} hours` : undefined}
            icon={<AccessTime sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid xs={12} sm={6} md={4} lg={3} sx={{ display: 'flex' }}>
          <StatCard
            title="Unique Artists"
            value={stats ? formatNumber(stats.unique_artists) : '—'}
            icon={<Person sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid xs={12} sm={6} md={4} lg={3} sx={{ display: 'flex' }}>
          <StatCard
            title="Unique Tracks"
            value={stats ? formatNumber(stats.unique_tracks) : '—'}
            icon={<HeadsetOff sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid xs={12} sm={6} md={4} lg={3} sx={{ display: 'flex' }}>
          <StatCard
            title="Unique Albums"
            value={stats ? formatNumber(stats.unique_albums) : '—'}
            icon={<Album sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={{ xs: 3, lg: 5 }} direction="column">
        {/* Monthly Trends */}
        <Grid xs={12}>
          <Paper sx={{ p: 5 }}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 4 }}>
              Monthly Listening Trends
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={600} />
            ) : (
              <LineChart
                xAxis={[
                  {
                    data: monthlyData.map((_, idx) => idx),
                    scaleType: 'point',
                    valueFormatter: (value) => monthlyData[value]?.month || '',
                  },
                ]}
                series={[
                  {
                    data: monthlyData.map((d) => d.streams),
                    label: 'Streams',
                    color: '#2dd881',
                  },
                ]}
                height={600}
              />
            )}
          </Paper>
        </Grid>

        {/* Monthly Hours */}
        <Grid xs={12}>
          <Paper sx={{ p: 5 }}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 4 }}>
              Monthly Listening Hours
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={600} />
            ) : (
              <LineChart
                xAxis={[
                  {
                    data: monthlyData.map((_, idx) => idx),
                    scaleType: 'point',
                    valueFormatter: (value) => monthlyData[value]?.month || '',
                  },
                ]}
                series={[
                  {
                    data: monthlyData.map((d) => d.hours),
                    label: 'Hours',
                    color: '#4ea699',
                    curve: 'catmullRom',
                  },
                ]}
                height={600}
              />
            )}
          </Paper>
        </Grid>

        {/* Top Artists */}
        <Grid item xs={12}>
          <Paper sx={{ p: 5 }}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 4 }}>
              Top 10 Artists
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={550} />
            ) : (
              <BarChart
                yAxis={[
                  {
                    data: topArtists.map((a) => a.artist),
                    scaleType: 'band',
                  },
                ]}
                series={[
                  {
                    data: topArtists.map((a) => a.streams),
                    label: 'Streams',
                    color: '#2dd881',
                  },
                ]}
                layout="horizontal"
                height={550}
              />
            )}
          </Paper>
        </Grid>

        {/* Top Tracks */}
        <Grid item xs={12}>
          <Paper sx={{ p: 5 }}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 4 }}>
              Top 10 Tracks
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={550} />
            ) : (
              <BarChart
                yAxis={[
                  {
                    data: topTracks.map((t) => `${t.track.substring(0, 35)}...`),
                    scaleType: 'band',
                  },
                ]}
                series={[
                  {
                    data: topTracks.map((t) => t.streams),
                    label: 'Streams',
                    color: '#6fedb7',
                  },
                ]}
                layout="horizontal"
                height={550}
              />
            )}
          </Paper>
        </Grid>

        {/* Platform Distribution */}
        <Grid item xs={12}>
          <Paper sx={{ p: 5 }}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 4 }}>
              Platform Distribution
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={500} />
            ) : (
              <PieChart
                series={[
                  {
                    data: platformStats.map((p, idx) => ({
                      id: idx,
                      value: p.streams,
                      label: p.platform,
                    })),
                    highlightScope: { fade: 'global', highlight: 'item' },
                  },
                ]}
                height={500}
              />
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
