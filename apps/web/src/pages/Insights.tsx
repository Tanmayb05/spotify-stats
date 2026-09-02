import { useCallback, useEffect, useState } from 'react';
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
  Card,
  CardContent,
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
import DataTable from '../components/DataTable';
import type { Column } from '../components/DataTable';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import { formatNumber, formatCompact } from '../utils/format';
import { useTimeRange } from '../hooks/useTimeRange';
import type { UseTimeRange } from '../hooks/useTimeRange';
import { CHART } from '../theme/chartColors';
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
  SessionDuration,
  BingeSession,
  SessionStatistics,
  WeekendWeekdayComparison,
  ListeningStreak,
  RepeatedTrack,
  MonthlyDiversity,
  DiscoveryTimeline,
  ArtistLoyalty,
  ArtistObsession,
  ReflectiveInsights,
} from '../types/api';

const paperSx = {
  p: 5,
  transition: 'all 0.3s ease-in-out',
  '&:hover': { boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)' },
} as const;

const tabSx = { textTransform: 'none', fontWeight: 600, fontSize: '1rem' } as const;

function csvDownload(url: string, filename: string) {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function pick<T>(r: PromiseSettledResult<T>, fallback: T): T {
  return r.status === 'fulfilled' ? r.value : fallback;
}

export default function Insights() {
  const { setError, selectedUserId } = useAppStore();

  // ---- wave 1 (above the fold) -----------------------------------------
  const [loading1, setLoading1] = useState(true);
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [topArtists, setTopArtists] = useState<TopArtist[]>([]);
  const [topTracks, setTopTracks] = useState<TopTrack[]>([]);
  const [monthlyData, setMonthlyData] = useState<MonthlyData[]>([]);
  const [skipBehavior, setSkipBehavior] = useState<SkipBehavior[]>([]);

  // ---- wave 2 (mid page) ---------------------------------------------------
  const [loading2, setLoading2] = useState(true);
  const [platformStats, setPlatformStats] = useState<PlatformStat[]>([]);
  const [hourlyData, setHourlyData] = useState<HourlyDistribution[]>([]);
  const [dailyData, setDailyData] = useState<DailyDistribution[]>([]);
  const [yearlyData, setYearlyData] = useState<YearlyComparison[]>([]);
  const [timeline, setTimeline] = useState<DiscoveryTimeline[]>([]);

  // ---- wave 3 (below the fold) ------------------------------------------
  const [loading3, setLoading3] = useState(true);
  const [sessionDurations, setSessionDurations] = useState<SessionDuration[]>([]);
  const [bingeSessions, setBingeSessions] = useState<BingeSession[]>([]);
  const [sessionStats, setSessionStats] = useState<SessionStatistics | null>(null);
  const [weekendWeekday, setWeekendWeekday] = useState<WeekendWeekdayComparison | null>(null);
  const [listeningStreaks, setListeningStreaks] = useState<ListeningStreak[]>([]);
  const [repeatedTracks, setRepeatedTracks] = useState<RepeatedTrack[]>([]);
  const [monthlyDiversity, setMonthlyDiversity] = useState<MonthlyDiversity[]>([]);
  const [loyalty, setLoyalty] = useState<ArtistLoyalty[]>([]);
  const [obsessions, setObsessions] = useState<ArtistObsession[]>([]);
  const [insights, setInsights] = useState<ReflectiveInsights | null>(null);

  // ---- tab state --------------------------------------------------------
  const [monthlyTab, setMonthlyTab] = useState<'streams' | 'hours'>('streams');
  const [rankingTab, setRankingTab] = useState<'artists' | 'tracks' | 'skip'>('artists');
  const [whenTab, setWhenTab] = useState<'hourly' | 'daily'>('hourly');
  const [yearlyTab, setYearlyTab] = useState<'streams' | 'hours'>('streams');
  const [sessionTab, setSessionTab] = useState<'duration' | 'binge' | 'stats'>('duration');
  const [behaviorTab, setBehaviorTab] = useState<'streaks' | 'repeated' | 'diversity'>('streaks');
  const [weekTab, setWeekTab] = useState<'weekend' | 'diversity'>('weekend');

  const monthly = useTimeRange<MonthlyData>(monthlyData);
  const discovery = useTimeRange<DiscoveryTimeline>(timeline);

  const load = useCallback(async () => {
    setLoading1(true);
    setLoading2(true);
    setLoading3(true);
    setError(null);
    const failures: string[] = [];

    const w1 = await Promise.allSettled([
      api.getOverviewStats(),
      api.getTopArtists(10),
      api.getTopTracks(10),
      api.getMonthlyData(),
      api.getSkipBehavior(20),
    ]);
    setStats(pick(w1[0], null));
    setTopArtists(pick(w1[1], []));
    setTopTracks(pick(w1[2], []));
    setMonthlyData(pick(w1[3], []));
    setSkipBehavior(pick(w1[4], []));
    w1.forEach((r) => r.status === 'rejected' && failures.push(String(r.reason)));
    setLoading1(false);

    const w2 = await Promise.allSettled([
      api.getPlatformStats(),
      api.getHourlyDistribution(),
      api.getDailyDistribution(),
      api.getYearlyComparison(),
      api.getDiscoveryTimeline(),
    ]);
    setPlatformStats(pick(w2[0], []));
    setHourlyData(pick(w2[1], []));
    setDailyData(pick(w2[2], []));
    setYearlyData(pick(w2[3], []));
    setTimeline(pick(w2[4], []));
    w2.forEach((r) => r.status === 'rejected' && failures.push(String(r.reason)));
    setLoading2(false);

    const w3 = await Promise.allSettled([
      api.getSessionDurations(),
      api.getBingeSessions(20),
      api.getSessionStatistics(),
      api.getWeekendWeekdayComparison(),
      api.getListeningStreaks(10),
      api.getRepeatedTracks(20),
      api.getMonthlyDiversity(),
      api.getArtistLoyalty(20),
      api.getArtistObsessions(15),
      api.getReflectiveInsights(),
    ]);
    setSessionDurations(pick(w3[0], []));
    setBingeSessions(pick(w3[1], []));
    setSessionStats(pick(w3[2], null));
    setWeekendWeekday(pick(w3[3], null));
    setListeningStreaks(pick(w3[4], []));
    setRepeatedTracks(pick(w3[5], []));
    setMonthlyDiversity(pick(w3[6], []));
    setLoyalty(pick(w3[7], []));
    setObsessions(pick(w3[8], []));
    setInsights(pick(w3[9], null));
    w3.forEach((r) => r.status === 'rejected' && failures.push(String(r.reason)));
    setLoading3(false);

    if (failures.length) {
      setError(
        `${failures.length} section${failures.length > 1 ? 's' : ''} failed to load. ` +
          'Some charts may be empty.'
      );
    }
  }, [setError]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUserId]);

  const loyaltyColumns: Column<ArtistLoyalty>[] = [
    { key: 'artist', label: 'Artist', align: 'left', width: '40%' },
    { key: 'return_prob', label: 'Return Probability (%)', align: 'right', format: (v) => `${v.toFixed(1)}%` },
    { key: 'half_life_days', label: 'Half-Life (days)', align: 'right', format: (v) => v.toFixed(1) },
    { key: 'total_streams', label: 'Total Streams', align: 'right', format: (v) => v.toLocaleString() },
  ];
  const bingeColumns: Column<BingeSession>[] = [
    { key: 'session_date', label: 'Date & Time', align: 'left' },
    { key: 'duration_minutes', label: 'Duration (min)', align: 'right', format: (v) => formatNumber(v) },
    { key: 'track_count', label: 'Tracks', align: 'right', format: (v) => formatNumber(v) },
  ];
  const streakColumns: Column<ListeningStreak>[] = [
    { key: 'start_date', label: 'Start Date', align: 'left' },
    { key: 'end_date', label: 'End Date', align: 'left' },
    { key: 'length_days', label: 'Length (days)', align: 'right', format: (v) => formatNumber(v) },
    { key: 'total_streams', label: 'Total Streams', align: 'right', format: (v) => formatNumber(v) },
  ];
  const repeatedColumns: Column<RepeatedTrack>[] = [
    { key: 'track', label: 'Track', align: 'left' },
    { key: 'artist', label: 'Artist', align: 'left' },
    { key: 'play_count', label: 'Play Count', align: 'right', format: (v) => formatNumber(v) },
    { key: 'repeat_score', label: 'Repeat Score', align: 'right', format: (v) => v.toFixed(2) },
  ];

  const rangeChips = (tr: UseTimeRange<{ month: string }>) => (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
      {(['all', '12m', '6m', '3m'] as const).map((r) => (
        <Chip
          key={r}
          label={r === 'all' ? 'All' : r.toUpperCase()}
          size="small"
          onClick={() => tr.handleRangeChange(r)}
          color={tr.chartRange === r ? 'primary' : 'default'}
          sx={{ cursor: 'pointer' }}
        />
      ))}
    </Box>
  );

  const rangeSlider = (tr: UseTimeRange<{ month: string }>, data: { month: string }[]) =>
    tr.chartRange !== 'all' && tr.maxSliderValue > 0 ? (
      <Box sx={{ mt: 2, px: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="caption" color="text.secondary" sx={{ minWidth: 'fit-content', flexShrink: 0 }}>
            Time period:
          </Typography>
          <Box sx={{ flex: 1 }}>
            <Slider
              value={tr.sliderValue}
              onChange={(_, value) => tr.setSliderValue(value as number)}
              min={0}
              max={tr.maxSliderValue}
              step={1}
              marks={[
                { value: 0, label: data[0]?.month || '' },
                { value: tr.maxSliderValue, label: data[data.length - 1]?.month || '' },
              ]}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => {
                const s = data[value]?.month || '';
                const e = data[Math.min(value + tr.rangeMonths - 1, data.length - 1)]?.month || '';
                return `${s} - ${e}`;
              }}
              sx={{ '& .MuiSlider-markLabel': { fontSize: '0.75rem' } }}
            />
          </Box>
        </Box>
      </Box>
    ) : null;

  return (
    <Box sx={{ pb: 4 }}>
      <Typography variant="h3" gutterBottom fontWeight={700} sx={{ mb: 2 }}>
        Insights
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 6, fontSize: '1.1rem' }}>
        Your complete Spotify streaming history — overview, patterns, and discovery.
      </Typography>

      {/* Stat cards */}
      <Grid container spacing={{ xs: 2, md: 3 }} sx={{ mb: 8 }}>
        {[
          { title: 'Total Streams', value: stats ? formatNumber(stats.total_streams) : '—', icon: <MusicNote sx={{ color: 'white', fontSize: 28 }} /> },
          { title: 'Listening Time', value: stats ? formatCompact(stats.total_hours) + 'h' : '—', subtitle: stats ? `${formatNumber(stats.total_hours)} hours` : undefined, icon: <AccessTime sx={{ color: 'white', fontSize: 28 }} /> },
          { title: 'Unique Artists', value: stats ? formatNumber(stats.unique_artists) : '—', icon: <Person sx={{ color: 'white', fontSize: 28 }} /> },
          { title: 'Unique Tracks', value: stats ? formatNumber(stats.unique_tracks) : '—', icon: <HeadsetOff sx={{ color: 'white', fontSize: 28 }} /> },
          { title: 'Unique Albums', value: stats ? formatNumber(stats.unique_albums) : '—', icon: <Album sx={{ color: 'white', fontSize: 28 }} /> },
        ].map((c) => (
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }} key={c.title}>
            <StatCard title={c.title} value={c.value} subtitle={c.subtitle} icon={c.icon} loading={loading1} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={{ xs: 3, lg: 5 }} direction="column">
        {/* Monthly Listening Trends */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" fontWeight={700}>Monthly Listening Trends</Typography>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Button variant="outlined" size="small" startIcon={<Download />} onClick={() => csvDownload(api.exportMonthlySummary(), 'monthly_summary.csv')} sx={{ mr: 1 }}>
                    Export CSV
                  </Button>
                  {rangeChips(monthly as unknown as UseTimeRange<{ month: string }>)}
                </Box>
              </Box>
              <Tabs value={monthlyTab} onChange={(_, v) => setMonthlyTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                <Tab label="Streams" value="streams" sx={tabSx} />
                <Tab label="Hours" value="hours" sx={tabSx} />
              </Tabs>
              {rangeSlider(monthly as unknown as UseTimeRange<{ month: string }>, monthlyData)}
            </Box>
            {loading1 ? (
              <Skeleton variant="rectangular" height={600} />
            ) : (
              <LineChart
                xAxis={[{ data: monthly.filtered.map((_, i) => i), scaleType: 'point', valueFormatter: (v) => monthly.filtered[v]?.month || '' }]}
                series={[{
                  data: monthlyTab === 'streams' ? monthly.filtered.map((d) => d.streams) : monthly.filtered.map((d) => d.hours),
                  label: monthlyTab === 'streams' ? 'Streams' : 'Hours',
                  color: monthlyTab === 'streams' ? CHART.emerald : CHART.keppel,
                  curve: 'catmullRom',
                }]}
                height={600}
              />
            )}
          </Paper>
        </Grid>

        {/* Top Rankings */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" fontWeight={700}>Top Rankings</Typography>
                {rankingTab !== 'skip' && (
                  <Button variant="outlined" size="small" startIcon={<Download />}
                    onClick={() => csvDownload(
                      rankingTab === 'artists' ? api.exportTopArtists(50) : api.exportTopTracks(50),
                      rankingTab === 'artists' ? 'top_50_artists.csv' : 'top_50_tracks.csv'
                    )}>
                    Export Top 50 CSV
                  </Button>
                )}
              </Box>
              <Tabs value={rankingTab} onChange={(_, v) => setRankingTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                <Tab label="Top Artists" value="artists" sx={tabSx} />
                <Tab label="Top Tracks" value="tracks" sx={tabSx} />
                <Tab label="Skip Behavior" value="skip" sx={tabSx} />
              </Tabs>
            </Box>
            {loading1 ? (
              <Skeleton variant="rectangular" height={rankingTab === 'skip' ? 600 : 550} />
            ) : (
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                {rankingTab === 'artists' && (
                  <BarChart
                    yAxis={[{ data: topArtists.map((a) => a.artist), scaleType: 'band' }]}
                    series={[{ data: topArtists.map((a) => a.streams), label: 'Streams', color: CHART.emerald }]}
                    layout="horizontal" height={550} margin={{ left: 320, right: 40, top: 40, bottom: 60 }}
                    sx={{ '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': { fontSize: '0.875rem' } }}
                  />
                )}
                {rankingTab === 'tracks' && (
                  <BarChart
                    yAxis={[{ data: topTracks.map((t) => `${t.track} - ${t.artist}`), scaleType: 'band' }]}
                    series={[{ data: topTracks.map((t) => t.streams), label: 'Streams', color: CHART.aquamarine }]}
                    layout="horizontal" height={550} margin={{ left: 420, right: 40, top: 40, bottom: 60 }}
                    sx={{ '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': { fontSize: '0.875rem' } }}
                  />
                )}
                {rankingTab === 'skip' && (
                  <BarChart
                    yAxis={[{ data: skipBehavior.map((s) => s.artist), scaleType: 'band' }]}
                    series={[{ data: skipBehavior.map((s) => s.skip_rate), label: 'Skip Rate (%)', color: CHART.keppel, valueFormatter: (v) => `${v?.toFixed(1)}%` }]}
                    layout="horizontal" height={600} margin={{ left: 250, right: 40, top: 40, bottom: 60 }}
                    sx={{ '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': { fontSize: '0.875rem' } }}
                  />
                )}
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Platform Distribution */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 4 }}>Platform Distribution</Typography>
            {loading2 ? (
              <Skeleton variant="rectangular" height={500} />
            ) : (
              <PieChart
                series={[{
                  data: platformStats.map((p, i) => ({ id: i, value: p.streams, label: p.platform })),
                  highlightScope: { fade: 'global', highlight: 'item' },
                }]}
                height={500}
              />
            )}
          </Paper>
        </Grid>

        {/* When You Listen (was Overview's "Listening Patterns") */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Box sx={{ mb: 4 }}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>When You Listen</Typography>
              <Tabs value={whenTab} onChange={(_, v) => setWhenTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                <Tab label="By Hour of Day" value="hourly" sx={tabSx} />
                <Tab label="By Day of Week" value="daily" sx={tabSx} />
              </Tabs>
            </Box>
            {loading2 ? (
              <Skeleton variant="rectangular" height={400} />
            ) : whenTab === 'hourly' ? (
              <BarChart
                xAxis={[{ data: hourlyData.map((h) => h.hour), scaleType: 'band', valueFormatter: (v) => `${v}:00` }]}
                series={[{ data: hourlyData.map((h) => h.streams), label: 'Streams', color: CHART.emerald }]}
                height={400} margin={{ left: 60, right: 40, top: 40, bottom: 60 }}
              />
            ) : (
              <BarChart
                xAxis={[{ data: dailyData.map((d) => d.day), scaleType: 'band' }]}
                series={[{ data: dailyData.map((d) => d.streams), label: 'Streams', color: CHART.keppel }]}
                height={400} margin={{ left: 60, right: 40, top: 40, bottom: 60 }}
              />
            )}
          </Paper>
        </Grid>

        {/* Year-over-Year */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Box sx={{ mb: 4 }}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Year-over-Year Comparison</Typography>
              <Tabs value={yearlyTab} onChange={(_, v) => setYearlyTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                <Tab label="Streams" value="streams" sx={tabSx} />
                <Tab label="Hours" value="hours" sx={tabSx} />
              </Tabs>
            </Box>
            {loading2 ? (
              <Skeleton variant="rectangular" height={500} />
            ) : (
              <LineChart
                xAxis={[{ data: yearlyData.map((_, i) => i), scaleType: 'point', valueFormatter: (v) => yearlyData[v]?.year.toString() || '' }]}
                series={[{
                  data: yearlyTab === 'streams' ? yearlyData.map((y) => y.streams) : yearlyData.map((y) => y.hours),
                  label: yearlyTab === 'streams' ? 'Streams' : 'Hours',
                  color: yearlyTab === 'streams' ? CHART.emerald : CHART.keppel,
                  curve: 'catmullRom',
                }]}
                height={500}
              />
            )}
          </Paper>
        </Grid>

        {/* Discovery Timeline */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" fontWeight={700}>Discovery Timeline</Typography>
                {rangeChips(discovery as unknown as UseTimeRange<{ month: string }>)}
              </Box>
              {rangeSlider(discovery as unknown as UseTimeRange<{ month: string }>, timeline as unknown as { month: string }[])}
            </Box>
            {loading2 ? (
              <Skeleton variant="rectangular" height={400} />
            ) : discovery.filtered.length > 0 ? (
              <LineChart
                xAxis={[{ data: discovery.filtered.map((_, i) => i), scaleType: 'point', valueFormatter: (v) => discovery.filtered[v]?.month || '' }]}
                series={[{ data: discovery.filtered.map((d) => d.new_artists_count), label: 'New Artists Discovered', color: CHART.emerald, curve: 'monotoneX' }]}
                height={400} margin={{ left: 60, right: 20, top: 20, bottom: 60 }}
              />
            ) : (
              <Box sx={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="text.secondary">No discovery data available</Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Session Analysis + Listening Behavior side by side */}
        <Grid size={12}>
          <Grid container spacing={{ xs: 3, lg: 5 }}>
            <Grid size={{ xs: 12, lg: 6 }}>
              <Paper sx={paperSx}>
                <Box sx={{ mb: 4 }}>
                  <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Session Analysis</Typography>
                  <Tabs value={sessionTab} onChange={(_, v) => setSessionTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                    <Tab label="Duration Distribution" value="duration" sx={tabSx} />
                    <Tab label="Binge Sessions" value="binge" sx={tabSx} />
                    <Tab label="Statistics" value="stats" sx={tabSx} />
                  </Tabs>
                </Box>
                {loading3 ? (
                  <Skeleton variant="rectangular" height={400} />
                ) : sessionTab === 'duration' ? (
                  <BarChart
                    xAxis={[{ data: sessionDurations.map((d) => d.duration_range), scaleType: 'band', label: 'Session Duration (minutes)' }]}
                    series={[{ data: sessionDurations.map((d) => d.session_count), label: 'Number of Sessions', color: CHART.emerald }]}
                    height={400} margin={{ left: 60, right: 40, top: 40, bottom: 80 }}
                  />
                ) : sessionTab === 'binge' ? (
                  <DataTable columns={bingeColumns} data={bingeSessions} emptyMessage="No binge sessions found" aria-label="Top 20 binge sessions" />
                ) : sessionStats ? (
                  <Card><CardContent sx={{ p: 4 }}>
                    <Grid container spacing={4}>
                      {[
                        ['Total Sessions', formatNumber(sessionStats.total_sessions)],
                        ['Avg Duration', `${formatNumber(sessionStats.avg_duration_minutes)} min`],
                        ['Median Duration', `${formatNumber(sessionStats.median_duration_minutes)} min`],
                        ['Avg Tracks / Session', formatNumber(sessionStats.avg_tracks_per_session)],
                        ['Longest Session', `${formatNumber(sessionStats.longest_session_minutes)} min`],
                      ].map(([label, val]) => (
                        <Grid size={{ xs: 12, sm: 6, md: 4 }} key={label}>
                          <Typography variant="body2" color="text.secondary" gutterBottom>{label}</Typography>
                          <Typography variant="h4" fontWeight={700}>{val}</Typography>
                        </Grid>
                      ))}
                    </Grid>
                  </CardContent></Card>
                ) : null}
              </Paper>
            </Grid>

            <Grid size={{ xs: 12, lg: 6 }}>
              <Paper sx={paperSx}>
                <Box sx={{ mb: 4 }}>
                  <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Listening Behavior</Typography>
                  <Tabs value={behaviorTab} onChange={(_, v) => setBehaviorTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                    <Tab label="Listening Streaks" value="streaks" sx={tabSx} />
                    <Tab label="Repeated Tracks" value="repeated" sx={tabSx} />
                  </Tabs>
                </Box>
                {loading3 ? (
                  <Skeleton variant="rectangular" height={400} />
                ) : behaviorTab === 'streaks' ? (
                  <DataTable columns={streakColumns} data={listeningStreaks} emptyMessage="No listening streaks found" aria-label="Listening streaks" />
                ) : (
                  <DataTable columns={repeatedColumns} data={repeatedTracks} emptyMessage="No repeated tracks found" aria-label="Most repeated tracks" />
                )}
              </Paper>
            </Grid>
          </Grid>
        </Grid>

        {/* Weekend vs Weekday + Monthly Diversity */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Box sx={{ mb: 4 }}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Weekend vs Weekday</Typography>
              <Tabs value={weekTab} onChange={(_, v) => setWeekTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                <Tab label="Weekend vs Weekday" value="weekend" sx={tabSx} />
                <Tab label="Monthly Diversity" value="diversity" sx={tabSx} />
              </Tabs>
            </Box>
            {loading3 ? (
              <Skeleton variant="rectangular" height={400} />
            ) : weekTab === 'weekend' && weekendWeekday ? (
              <Card><CardContent sx={{ p: 4 }}>
                <Grid container spacing={6}>
                  {(['weekday', 'weekend'] as const).map((k) => (
                    <Grid size={{ xs: 12, md: 6 }} key={k}>
                      <Typography variant="h6" gutterBottom fontWeight={600} sx={{ textTransform: 'capitalize' }}>{k}</Typography>
                      <Box sx={{ mt: 3 }}>
                        <Box sx={{ mb: 2 }}>
                          <Typography variant="body2" color="text.secondary">Total Streams</Typography>
                          <Typography variant="h4" fontWeight={700}>{formatNumber(weekendWeekday[k].streams)}</Typography>
                        </Box>
                        <Box sx={{ mb: 2 }}>
                          <Typography variant="body2" color="text.secondary">Total Hours</Typography>
                          <Typography variant="h4" fontWeight={700}>{formatNumber(weekendWeekday[k].hours)}h</Typography>
                        </Box>
                        <Box>
                          <Typography variant="body2" color="text.secondary">Avg per Day</Typography>
                          <Typography variant="h4" fontWeight={700}>{formatNumber(weekendWeekday[k].avg_per_day)}</Typography>
                        </Box>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </CardContent></Card>
            ) : weekTab === 'diversity' ? (
              <LineChart
                xAxis={[{ data: monthlyDiversity.map((_, i) => i), scaleType: 'point', valueFormatter: (v) => monthlyDiversity[v]?.month || '' }]}
                series={[{ data: monthlyDiversity.map((d) => d.unique_artists), label: 'Unique Artists', color: CHART.keppel, curve: 'catmullRom' }]}
                height={600} margin={{ left: 60, right: 40, top: 40, bottom: 60 }}
              />
            ) : null}
          </Paper>
        </Grid>

        {/* Artist Loyalty + Obsessions */}
        <Grid size={12}>
          <Grid container spacing={{ xs: 3, lg: 5 }}>
            <Grid size={{ xs: 12, lg: 6 }}>
              <Paper sx={paperSx}>
                <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 3 }}>Artist Loyalty</Typography>
                <DataTable columns={loyaltyColumns} data={loyalty} loading={loading3} emptyMessage="No loyalty data available" maxHeight="400px" aria-label="Artist loyalty table" />
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, lg: 6 }}>
              <Paper sx={paperSx}>
                <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 3 }}>Obsession Periods</Typography>
                {loading3 ? (
                  <Skeleton variant="rectangular" height={400} />
                ) : obsessions.length > 0 ? (
                  <Box sx={{ width: '100%', overflowX: 'auto' }}>
                    <BarChart
                      yAxis={[{ data: obsessions.slice(0, 10).map((o) => o.artist), scaleType: 'band' }]}
                      series={[{ data: obsessions.slice(0, 10).map((o) => o.period_share), label: 'Period Share (%)', color: CHART.keppel }]}
                      layout="horizontal" height={400} margin={{ left: 250, right: 40, top: 40, bottom: 60 }}
                      sx={{ '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': { fontSize: '0.875rem' } }}
                    />
                  </Box>
                ) : (
                  <Box sx={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Typography color="text.secondary">No obsession periods found</Typography>
                  </Box>
                )}
              </Paper>
            </Grid>
          </Grid>
        </Grid>

        {/* Reflective Insights */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 3 }}>Reflective Insights</Typography>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              {insights
                ? [
                    { title: 'Longest Streak', value: insights.longest_streak_days, subtitle: 'consecutive days' },
                    { title: 'Peak Hour', value: `${insights.most_active_hour}:00`, subtitle: 'most active time' },
                    { title: 'Favorite Day', value: insights.most_active_day, subtitle: 'most active' },
                    { title: 'Daily Average', value: insights.avg_streams_per_day.toFixed(0), subtitle: 'streams per day' },
                  ].map((c) => (
                    <Grid size={{ xs: 12, sm: 6, md: 3 }} key={c.title}>
                      <StatCard title={c.title} value={c.value} subtitle={c.subtitle} loading={loading3} />
                    </Grid>
                  ))
                : [...Array(4)].map((_, i) => (
                    <Grid size={{ xs: 12, sm: 6, md: 3 }} key={i}>
                      <Skeleton variant="rectangular" height={140} />
                    </Grid>
                  ))}
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
