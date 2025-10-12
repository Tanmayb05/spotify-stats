import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Grid,
  Chip,
  Slider,
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
  const [chartRange, setChartRange] = useState<'all' | '12m' | '6m' | '3m'>('all');
  const [sliderValue, setSliderValue] = useState<number>(0);
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

  // Filter monthly data based on chart range and slider position
  const getRangeMonths = () => {
    if (chartRange === 'all') return monthlyData.length;
    return parseInt(chartRange);
  };

  const getMaxSliderValue = () => {
    const rangeMonths = getRangeMonths();
    return Math.max(0, monthlyData.length - rangeMonths);
  };

  const filteredMonthlyData = chartRange === 'all'
    ? monthlyData
    : monthlyData.slice(sliderValue, sliderValue + getRangeMonths());

  const handleRangeChange = (newRange: typeof chartRange) => {
    setChartRange(newRange);
    if (newRange === 'all') {
      setSliderValue(0);
    } else {
      const rangeMonths = parseInt(newRange);
      setSliderValue(Math.max(0, monthlyData.length - rangeMonths));
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
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: chartRange !== 'all' && getMaxSliderValue() > 0 ? 3 : 0 }}>
                <Typography variant="h5" fontWeight={700}>
                  Monthly Listening Trends
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip
                    label="All"
                    size="small"
                    onClick={() => handleRangeChange('all')}
                    color={chartRange === 'all' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                  <Chip
                    label="12M"
                    size="small"
                    onClick={() => handleRangeChange('12m')}
                    color={chartRange === '12m' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                  <Chip
                    label="6M"
                    size="small"
                    onClick={() => handleRangeChange('6m')}
                    color={chartRange === '6m' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                  <Chip
                    label="3M"
                    size="small"
                    onClick={() => handleRangeChange('3m')}
                    color={chartRange === '3m' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                </Box>
              </Box>

              {/* Time Range Slider */}
              {chartRange !== 'all' && getMaxSliderValue() > 0 && (
                <Box sx={{ mt: 2, px: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ minWidth: 'fit-content', flexShrink: 0 }}>
                      Time period:
                    </Typography>
                    <Box sx={{ flex: 1 }}>
                      <Slider
                        value={sliderValue}
                        onChange={(_, value) => setSliderValue(value as number)}
                        min={0}
                        max={getMaxSliderValue()}
                        step={1}
                        marks={[
                          { value: 0, label: monthlyData[0]?.month || '' },
                          { value: getMaxSliderValue(), label: monthlyData[monthlyData.length - 1]?.month || '' },
                        ]}
                        valueLabelDisplay="auto"
                        valueLabelFormat={(value) => {
                          const startMonth = monthlyData[value]?.month || '';
                          const endMonth = monthlyData[Math.min(value + getRangeMonths() - 1, monthlyData.length - 1)]?.month || '';
                          return `${startMonth} - ${endMonth}`;
                        }}
                        sx={{
                          '& .MuiSlider-markLabel': {
                            fontSize: '0.75rem',
                          },
                        }}
                      />
                    </Box>
                  </Box>
                </Box>
              )}
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={600} />
            ) : (
              <LineChart
                xAxis={[
                  {
                    data: filteredMonthlyData.map((_, idx) => idx),
                    scaleType: 'point',
                    valueFormatter: (value) => filteredMonthlyData[value]?.month || '',
                  },
                ]}
                series={[
                  {
                    data: filteredMonthlyData.map((d) => d.streams),
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
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: chartRange !== 'all' && getMaxSliderValue() > 0 ? 3 : 0 }}>
                <Typography variant="h5" fontWeight={700}>
                  Monthly Listening Hours
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip
                    label="All"
                    size="small"
                    onClick={() => handleRangeChange('all')}
                    color={chartRange === 'all' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                  <Chip
                    label="12M"
                    size="small"
                    onClick={() => handleRangeChange('12m')}
                    color={chartRange === '12m' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                  <Chip
                    label="6M"
                    size="small"
                    onClick={() => handleRangeChange('6m')}
                    color={chartRange === '6m' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                  <Chip
                    label="3M"
                    size="small"
                    onClick={() => handleRangeChange('3m')}
                    color={chartRange === '3m' ? 'primary' : 'default'}
                    sx={{ cursor: 'pointer' }}
                  />
                </Box>
              </Box>

              {/* Time Range Slider */}
              {chartRange !== 'all' && getMaxSliderValue() > 0 && (
                <Box sx={{ mt: 2, px: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ minWidth: 'fit-content', flexShrink: 0 }}>
                      Time period:
                    </Typography>
                    <Box sx={{ flex: 1 }}>
                      <Slider
                        value={sliderValue}
                        onChange={(_, value) => setSliderValue(value as number)}
                        min={0}
                        max={getMaxSliderValue()}
                        step={1}
                        marks={[
                          { value: 0, label: monthlyData[0]?.month || '' },
                          { value: getMaxSliderValue(), label: monthlyData[monthlyData.length - 1]?.month || '' },
                        ]}
                        valueLabelDisplay="auto"
                        valueLabelFormat={(value) => {
                          const startMonth = monthlyData[value]?.month || '';
                          const endMonth = monthlyData[Math.min(value + getRangeMonths() - 1, monthlyData.length - 1)]?.month || '';
                          return `${startMonth} - ${endMonth}`;
                        }}
                        sx={{
                          '& .MuiSlider-markLabel': {
                            fontSize: '0.75rem',
                          },
                        }}
                      />
                    </Box>
                  </Box>
                </Box>
              )}
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={600} />
            ) : (
              <LineChart
                xAxis={[
                  {
                    data: filteredMonthlyData.map((_, idx) => idx),
                    scaleType: 'point',
                    valueFormatter: (value) => filteredMonthlyData[value]?.month || '',
                  },
                ]}
                series={[
                  {
                    data: filteredMonthlyData.map((d) => d.hours),
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
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
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
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
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
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
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
