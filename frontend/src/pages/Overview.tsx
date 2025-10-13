import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Grid,
  Chip,
  Slider,
  Button,
  Tabs,
  Tab,
} from '@mui/material';
import {
  MusicNote,
  Person,
  Album,
  AccessTime,
  HeadsetOff,
  Download,
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
  HourlyDistribution,
  DailyDistribution,
  SkipBehavior,
  YearlyComparison,
} from '../types/api';

export default function Overview() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [topArtists, setTopArtists] = useState<TopArtist[]>([]);
  const [topTracks, setTopTracks] = useState<TopTrack[]>([]);
  const [monthlyData, setMonthlyData] = useState<MonthlyData[]>([]);
  const [platformStats, setPlatformStats] = useState<PlatformStat[]>([]);
  const [hourlyData, setHourlyData] = useState<HourlyDistribution[]>([]);
  const [dailyData, setDailyData] = useState<DailyDistribution[]>([]);
  const [skipBehavior, setSkipBehavior] = useState<SkipBehavior[]>([]);
  const [yearlyData, setYearlyData] = useState<YearlyComparison[]>([]);
  const [chartRange, setChartRange] = useState<'all' | '12m' | '6m' | '3m'>('all');
  const [sliderValue, setSliderValue] = useState<number>(0);
  const [monthlyTab, setMonthlyTab] = useState<'streams' | 'hours'>('streams');
  const [rankingTab, setRankingTab] = useState<'artists' | 'tracks' | 'skip'>('artists');
  const [temporalTab, setTemporalTab] = useState<'hourly' | 'daily'>('hourly');
  const [yearlyTab, setYearlyTab] = useState<'streams' | 'hours'>('streams');
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
        hourlyDataRes,
        dailyDataRes,
        skipBehaviorRes,
        yearlyDataRes,
      ] = await Promise.all([
        api.getOverviewStats(),
        api.getTopArtists(10),
        api.getTopTracks(10),
        api.getMonthlyData(),
        api.getPlatformStats(),
        api.getHourlyDistribution(),
        api.getDailyDistribution(),
        api.getSkipBehavior(20),
        api.getYearlyComparison(),
      ]);

      setStats(overviewData);
      setTopArtists(artistsData);
      setTopTracks(tracksData);
      setMonthlyData(monthlyDataRes);
      setPlatformStats(platformsData);
      setHourlyData(hourlyDataRes);
      setDailyData(dailyDataRes);
      setSkipBehavior(skipBehaviorRes);
      setYearlyData(yearlyDataRes);
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

  const handleExportCSV = (url: string, filename: string) => {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
          <StatCard
            title="Total Streams"
            value={stats ? formatNumber(stats.total_streams) : '—'}
            icon={<MusicNote sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
          <StatCard
            title="Listening Time"
            value={stats ? formatCompact(stats.total_hours) + 'h' : '—'}
            subtitle={stats ? `${formatNumber(stats.total_hours)} hours` : undefined}
            icon={<AccessTime sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
          <StatCard
            title="Unique Artists"
            value={stats ? formatNumber(stats.unique_artists) : '—'}
            icon={<Person sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
          <StatCard
            title="Unique Tracks"
            value={stats ? formatNumber(stats.unique_tracks) : '—'}
            icon={<HeadsetOff sx={{ color: 'white', fontSize: 28 }} />}
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
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
        {/* Monthly Listening Trends - Tabbed */}
        <Grid size={12}>
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              {/* Header with Title and Controls */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" fontWeight={700}>
                  Monthly Listening Trends
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<Download />}
                    onClick={() => handleExportCSV(api.exportMonthlySummary(), 'monthly_summary.csv')}
                    sx={{ mr: 1 }}
                  >
                    Export CSV
                  </Button>
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

              {/* Tabs for Streams/Hours */}
              <Tabs
                value={monthlyTab}
                onChange={(_, newValue) => setMonthlyTab(newValue)}
                sx={{
                  mb: 3,
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Tab
                  label="Streams"
                  value="streams"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
                <Tab
                  label="Hours"
                  value="hours"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
              </Tabs>

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
                    data: monthlyTab === 'streams'
                      ? filteredMonthlyData.map((d) => d.streams)
                      : filteredMonthlyData.map((d) => d.hours),
                    label: monthlyTab === 'streams' ? 'Streams' : 'Hours',
                    color: monthlyTab === 'streams' ? '#2dd881' : '#4ea699',
                    curve: 'catmullRom',
                  },
                ]}
                height={600}
              />
            )}
          </Paper>
        </Grid>

        {/* Top Rankings - Tabbed */}
        <Grid size={12}>
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              {/* Header with Title and Controls */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" fontWeight={700}>
                  Top Rankings
                </Typography>
                {rankingTab !== 'skip' && (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<Download />}
                    onClick={() => handleExportCSV(
                      rankingTab === 'artists'
                        ? api.exportTopArtists(50)
                        : api.exportTopTracks(50),
                      rankingTab === 'artists'
                        ? 'top_50_artists.csv'
                        : 'top_50_tracks.csv'
                    )}
                  >
                    Export Top 50 CSV
                  </Button>
                )}
              </Box>

              {/* Tabs for Artists/Tracks/Skip Behavior */}
              <Tabs
                value={rankingTab}
                onChange={(_, newValue) => setRankingTab(newValue)}
                sx={{
                  mb: 3,
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Tab
                  label="Top Artists"
                  value="artists"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
                <Tab
                  label="Top Tracks"
                  value="tracks"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
                <Tab
                  label="Skip Behavior"
                  value="skip"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
              </Tabs>
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={rankingTab === 'skip' ? 600 : 550} />
            ) : (
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                {rankingTab === 'artists' && (
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
                    margin={{ left: 250, right: 40, top: 40, bottom: 60 }}
                    sx={{
                      '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': {
                        fontSize: '0.875rem',
                      },
                    }}
                  />
                )}
                {rankingTab === 'tracks' && (
                  <BarChart
                    yAxis={[
                      {
                        data: topTracks.map((t) => `${t.track} - ${t.artist}`),
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
                    margin={{ left: 300, right: 40, top: 40, bottom: 60 }}
                    sx={{
                      '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': {
                        fontSize: '0.875rem',
                      },
                    }}
                  />
                )}
                {rankingTab === 'skip' && (
                  <BarChart
                    yAxis={[
                      {
                        data: skipBehavior.map((s) => s.artist),
                        scaleType: 'band',
                      },
                    ]}
                    series={[
                      {
                        data: skipBehavior.map((s) => s.skip_rate),
                        label: 'Skip Rate (%)',
                        color: '#4ea699',
                        valueFormatter: (value) => `${value?.toFixed(1)}%`,
                      },
                    ]}
                    layout="horizontal"
                    height={600}
                    margin={{ left: 250, right: 40, top: 40, bottom: 60 }}
                    sx={{
                      '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': {
                        fontSize: '0.875rem',
                      },
                    }}
                  />
                )}
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Platform Distribution */}
        <Grid size={12}>
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

        {/* Listening Patterns - Tabbed */}
        <Grid size={12}>
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              {/* Header with Title */}
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
                Listening Patterns
              </Typography>

              {/* Tabs for Hourly/Daily */}
              <Tabs
                value={temporalTab}
                onChange={(_, newValue) => setTemporalTab(newValue)}
                sx={{
                  mb: 3,
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Tab
                  label="By Hour of Day"
                  value="hourly"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
                <Tab
                  label="By Day of Week"
                  value="daily"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
              </Tabs>
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <>
                {temporalTab === 'hourly' && (
                  <BarChart
                    xAxis={[
                      {
                        data: hourlyData.map((h) => h.hour),
                        scaleType: 'band',
                        valueFormatter: (value) => `${value}:00`,
                      },
                    ]}
                    series={[
                      {
                        data: hourlyData.map((h) => h.streams),
                        label: 'Streams',
                        color: '#2dd881',
                      },
                    ]}
                    height={400}
                    margin={{ left: 60, right: 40, top: 40, bottom: 60 }}
                  />
                )}
                {temporalTab === 'daily' && (
                  <BarChart
                    xAxis={[
                      {
                        data: dailyData.map((d) => d.day),
                        scaleType: 'band',
                      },
                    ]}
                    series={[
                      {
                        data: dailyData.map((d) => d.streams),
                        label: 'Streams',
                        color: '#4ea699',
                      },
                    ]}
                    height={400}
                    margin={{ left: 60, right: 40, top: 40, bottom: 60 }}
                  />
                )}
              </>
            )}
          </Paper>
        </Grid>

        {/* Yearly Comparison - Tabbed */}
        <Grid size={12}>
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              {/* Header with Title */}
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
                Year-over-Year Comparison
              </Typography>

              {/* Tabs for Streams/Hours */}
              <Tabs
                value={yearlyTab}
                onChange={(_, newValue) => setYearlyTab(newValue)}
                sx={{
                  mb: 3,
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Tab
                  label="Streams"
                  value="streams"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
                <Tab
                  label="Hours"
                  value="hours"
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '1rem',
                  }}
                />
              </Tabs>
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={500} />
            ) : (
              <LineChart
                xAxis={[
                  {
                    data: yearlyData.map((_, idx) => idx),
                    scaleType: 'point',
                    valueFormatter: (value) => yearlyData[value]?.year.toString() || '',
                  },
                ]}
                series={[
                  {
                    data: yearlyTab === 'streams'
                      ? yearlyData.map((y) => y.streams)
                      : yearlyData.map((y) => y.hours),
                    label: yearlyTab === 'streams' ? 'Streams' : 'Hours',
                    color: yearlyTab === 'streams' ? '#2dd881' : '#4ea699',
                    curve: 'catmullRom',
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
