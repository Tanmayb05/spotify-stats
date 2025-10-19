import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Grid,
  Tabs,
  Tab,
  Card,
  CardContent,
} from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import { LineChart } from '@mui/x-charts/LineChart';
import DataTable from '../components/DataTable';
import type { Column } from '../components/DataTable';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import { formatNumber } from '../utils/format';
import type {
  SessionDuration,
  BingeSession,
  SessionStatistics,
  WeekendWeekdayComparison,
  ListeningStreak,
  RepeatedTrack,
  MonthlyDiversity,
} from '../types/api';

export default function ListeningPatterns() {
  const [loading, setLoading] = useState(true);

  // Session Analysis state
  const [sessionDurations, setSessionDurations] = useState<SessionDuration[]>([]);
  const [bingeSessions, setBingeSessions] = useState<BingeSession[]>([]);
  const [sessionStats, setSessionStats] = useState<SessionStatistics | null>(null);
  const [sessionTab, setSessionTab] = useState<'duration' | 'binge' | 'stats'>('duration');

  // Temporal Patterns state
  const [weekendWeekday, setWeekendWeekday] = useState<WeekendWeekdayComparison | null>(null);
  const [temporalTab, setTemporalTab] = useState<'weekend' | 'diversity'>('weekend');

  // Listening Behavior state
  const [listeningStreaks, setListeningStreaks] = useState<ListeningStreak[]>([]);
  const [repeatedTracks, setRepeatedTracks] = useState<RepeatedTrack[]>([]);
  const [monthlyDiversity, setMonthlyDiversity] = useState<MonthlyDiversity[]>([]);
  const [behaviorTab, setBehaviorTab] = useState<'streaks' | 'repeated' | 'diversity'>('streaks');

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
        durationsData,
        bingeData,
        statsData,
        weekendWeekdayData,
        streaksData,
        repeatedData,
        diversityData,
      ] = await Promise.all([
        api.getSessionDurations(),
        api.getBingeSessions(20),
        api.getSessionStatistics(),
        api.getWeekendWeekdayComparison(),
        api.getListeningStreaks(10),
        api.getRepeatedTracks(20),
        api.getMonthlyDiversity(),
      ]);

      setSessionDurations(durationsData);
      setBingeSessions(bingeData);
      setSessionStats(statsData);
      setWeekendWeekday(weekendWeekdayData);
      setListeningStreaks(streaksData);
      setRepeatedTracks(repeatedData);
      setMonthlyDiversity(diversityData);
    } catch (error) {
      console.error('Error loading listening patterns data:', error);
      setError(
        error instanceof Error ? error.message : 'Failed to load listening patterns data'
      );
    } finally {
      setLoading(false);
    }
  };

  // Table columns
  const bingeColumns: Column<BingeSession>[] = [
    { key: 'session_date', label: 'Date & Time', align: 'left' },
    { key: 'duration_minutes', label: 'Duration (min)', align: 'right', format: (val) => formatNumber(val) },
    { key: 'track_count', label: 'Tracks', align: 'right', format: (val) => formatNumber(val) },
  ];

  const streakColumns: Column<ListeningStreak>[] = [
    { key: 'start_date', label: 'Start Date', align: 'left' },
    { key: 'end_date', label: 'End Date', align: 'left' },
    { key: 'length_days', label: 'Length (days)', align: 'right', format: (val) => formatNumber(val) },
    { key: 'total_streams', label: 'Total Streams', align: 'right', format: (val) => formatNumber(val) },
  ];

  const repeatedColumns: Column<RepeatedTrack>[] = [
    { key: 'track', label: 'Track', align: 'left' },
    { key: 'artist', label: 'Artist', align: 'left' },
    { key: 'play_count', label: 'Play Count', align: 'right', format: (val) => formatNumber(val) },
    { key: 'repeat_score', label: 'Repeat Score', align: 'right', format: (val) => val.toFixed(2) },
  ];

  return (
    <Box sx={{ pb: 4 }}>
      <Typography variant="h3" gutterBottom fontWeight={700} sx={{ mb: 2 }}>
        Listening Patterns
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 6, fontSize: '1.1rem' }}>
        Deep dive into your listening habits, sessions, and temporal patterns.
      </Typography>

      {/* Charts */}
      <Grid container spacing={{ xs: 3, lg: 5 }}>
        {/* Session Analysis - Tabbed */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
                Session Analysis
              </Typography>

              {/* Tabs */}
              <Tabs
                value={sessionTab}
                onChange={(_, newValue) => setSessionTab(newValue)}
                sx={{
                  mb: 3,
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Tab
                  label="Duration Distribution"
                  value="duration"
                  sx={{ textTransform: 'none', fontWeight: 600, fontSize: '1rem' }}
                />
                <Tab
                  label="Binge Sessions"
                  value="binge"
                  sx={{ textTransform: 'none', fontWeight: 600, fontSize: '1rem' }}
                />
                <Tab
                  label="Statistics"
                  value="stats"
                  sx={{ textTransform: 'none', fontWeight: 600, fontSize: '1rem' }}
                />
              </Tabs>
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <Box sx={{ width: '100%' }}>
                {sessionTab === 'duration' && (
                  <BarChart
                    xAxis={[
                      {
                        data: sessionDurations.map((d) => d.duration_range),
                        scaleType: 'band',
                        label: 'Session Duration (minutes)',
                      },
                    ]}
                    series={[
                      {
                        data: sessionDurations.map((d) => d.session_count),
                        label: 'Number of Sessions',
                        color: '#2dd881',
                      },
                    ]}
                    height={400}
                    margin={{ left: 60, right: 40, top: 40, bottom: 80 }}
                  />
                )}

                {sessionTab === 'binge' && (
                  <DataTable
                    columns={bingeColumns}
                    data={bingeSessions}
                    loading={loading}
                    emptyMessage="No binge sessions found"
                    aria-label="Top 20 binge sessions"
                  />
                )}

                {sessionTab === 'stats' && sessionStats && (
                  <Card>
                    <CardContent sx={{ p: 4 }}>
                      <Grid container spacing={4}>
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              Total Sessions
                            </Typography>
                            <Typography variant="h3" fontWeight={700}>
                              {formatNumber(sessionStats.total_sessions)}
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              Avg Duration
                            </Typography>
                            <Typography variant="h3" fontWeight={700}>
                              {formatNumber(sessionStats.avg_duration_minutes)} min
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              Median Duration
                            </Typography>
                            <Typography variant="h3" fontWeight={700}>
                              {formatNumber(sessionStats.median_duration_minutes)} min
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              Avg Tracks per Session
                            </Typography>
                            <Typography variant="h3" fontWeight={700}>
                              {formatNumber(sessionStats.avg_tracks_per_session)}
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              Longest Session
                            </Typography>
                            <Typography variant="h3" fontWeight={700}>
                              {formatNumber(sessionStats.longest_session_minutes)} min
                            </Typography>
                          </Box>
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                )}
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Listening Behavior - Tabbed */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
                Listening Behavior
              </Typography>

              {/* Tabs */}
              <Tabs
                value={behaviorTab}
                onChange={(_, newValue) => setBehaviorTab(newValue)}
                sx={{
                  mb: 3,
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Tab
                  label="Listening Streaks"
                  value="streaks"
                  sx={{ textTransform: 'none', fontWeight: 600, fontSize: '1rem' }}
                />
                <Tab
                  label="Repeated Tracks"
                  value="repeated"
                  sx={{ textTransform: 'none', fontWeight: 600, fontSize: '1rem' }}
                />
              </Tabs>
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <Box sx={{ width: '100%' }}>
                {behaviorTab === 'streaks' && (
                  <DataTable
                    columns={streakColumns}
                    data={listeningStreaks}
                    loading={loading}
                    emptyMessage="No listening streaks found"
                    aria-label="Listening streaks"
                  />
                )}

                {behaviorTab === 'repeated' && (
                  <DataTable
                    columns={repeatedColumns}
                    data={repeatedTracks}
                    loading={loading}
                    emptyMessage="No repeated tracks found"
                    aria-label="Most repeated tracks"
                  />
                )}
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Temporal Patterns - Tabbed */}
        <Grid size={12}>
          <Paper sx={{
            p: 5,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: 4 }}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
                Temporal Patterns
              </Typography>

              {/* Tabs */}
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
                  label="Weekend vs Weekday"
                  value="weekend"
                  sx={{ textTransform: 'none', fontWeight: 600, fontSize: '1rem' }}
                />
                <Tab
                  label="Monthly Diversity"
                  value="diversity"
                  sx={{ textTransform: 'none', fontWeight: 600, fontSize: '1rem' }}
                />
              </Tabs>
            </Box>

            {loading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <Box sx={{ width: '100%' }}>
                {temporalTab === 'weekend' && weekendWeekday && (
                  <Card>
                    <CardContent sx={{ p: 4 }}>
                      <Grid container spacing={6}>
                        <Grid size={{ xs: 12, md: 6 }}>
                          <Typography variant="h6" gutterBottom fontWeight={600}>
                            Weekday
                          </Typography>
                          <Box sx={{ mt: 3 }}>
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="body2" color="text.secondary">
                                Total Streams
                              </Typography>
                              <Typography variant="h4" fontWeight={700}>
                                {formatNumber(weekendWeekday.weekday.streams)}
                              </Typography>
                            </Box>
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="body2" color="text.secondary">
                                Total Hours
                              </Typography>
                              <Typography variant="h4" fontWeight={700}>
                                {formatNumber(weekendWeekday.weekday.hours)}h
                              </Typography>
                            </Box>
                            <Box>
                              <Typography variant="body2" color="text.secondary">
                                Avg per Day
                              </Typography>
                              <Typography variant="h4" fontWeight={700}>
                                {formatNumber(weekendWeekday.weekday.avg_per_day)}
                              </Typography>
                            </Box>
                          </Box>
                        </Grid>
                        <Grid size={{ xs: 12, md: 6 }}>
                          <Typography variant="h6" gutterBottom fontWeight={600}>
                            Weekend
                          </Typography>
                          <Box sx={{ mt: 3 }}>
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="body2" color="text.secondary">
                                Total Streams
                              </Typography>
                              <Typography variant="h4" fontWeight={700}>
                                {formatNumber(weekendWeekday.weekend.streams)}
                              </Typography>
                            </Box>
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="body2" color="text.secondary">
                                Total Hours
                              </Typography>
                              <Typography variant="h4" fontWeight={700}>
                                {formatNumber(weekendWeekday.weekend.hours)}h
                              </Typography>
                            </Box>
                            <Box>
                              <Typography variant="body2" color="text.secondary">
                                Avg per Day
                              </Typography>
                              <Typography variant="h4" fontWeight={700}>
                                {formatNumber(weekendWeekday.weekend.avg_per_day)}
                              </Typography>
                            </Box>
                          </Box>
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                )}

                {temporalTab === 'diversity' && (
                  <LineChart
                    xAxis={[
                      {
                        data: monthlyDiversity.map((_, idx) => idx),
                        scaleType: 'point',
                        valueFormatter: (value) => monthlyDiversity[value]?.month || '',
                      },
                    ]}
                    series={[
                      {
                        data: monthlyDiversity.map((d) => d.unique_artists),
                        label: 'Unique Artists',
                        color: '#4ea699',
                        curve: 'catmullRom',
                      },
                    ]}
                    height={600}
                    margin={{ left: 60, right: 40, top: 40, bottom: 60 }}
                  />
                )}
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
