import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Chip,
  Tooltip,
  IconButton,
  Slider,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  SentimentVerySatisfied,
  Bolt,
  MusicNote,
  InfoOutlined,
} from '@mui/icons-material';

// Distinct colors for mood metrics
const MOOD_COLORS = {
  valence: '#10b981',    // Green (happiness)
  energy: '#f59e0b',     // Orange (energy)
  danceability: '#8b5cf6', // Purple (rhythm)
};
import { LineChart } from '@mui/x-charts/LineChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import type {
  MoodSummary,
  MoodContexts,
  MonthlyMood,
} from '../types/api';

export default function Moods() {
  const [loading, setLoading] = useState(true);
  const [window, setWindow] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [summary, setSummary] = useState<MoodSummary | null>(null);
  const [contexts, setContexts] = useState<MoodContexts | null>(null);
  const [monthly, setMonthly] = useState<MonthlyMood[]>([]);
  const [chartRange, setChartRange] = useState<'all' | '12m' | '6m' | '3m'>('all');
  const [sliderValue, setSliderValue] = useState<number>(0);
  const { setError } = useAppStore();

  useEffect(() => {
    loadData();
  }, [window]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [summaryData, contextsData, monthlyData] = await Promise.all([
        api.getMoodSummary(window),
        api.getMoodContexts(),
        api.getMoodMonthly(),
      ]);

      setSummary(summaryData);
      setContexts(contextsData);
      setMonthly(monthlyData);
    } catch (error) {
      console.error('Error loading mood data:', error);
      setError(
        error instanceof Error ? error.message : 'Failed to load mood data'
      );
    } finally {
      setLoading(false);
    }
  };

  const formatPercent = (value: number | null) => {
    if (value === null) return '—';
    return `${Math.round(value * 100)}%`;
  };

  // Filter monthly data based on chart range and slider position
  const getRangeMonths = () => {
    if (chartRange === 'all') return monthly.length;
    return parseInt(chartRange);
  };

  const getMaxSliderValue = () => {
    const rangeMonths = getRangeMonths();
    return Math.max(0, monthly.length - rangeMonths);
  };

  const filteredMonthly = chartRange === 'all'
    ? monthly
    : monthly.slice(sliderValue, sliderValue + getRangeMonths());

  // Reset slider when changing range or when data loads
  const handleRangeChange = (newRange: typeof chartRange) => {
    setChartRange(newRange);
    if (newRange === 'all') {
      setSliderValue(0);
    } else {
      // Start at the most recent data
      const rangeMonths = parseInt(newRange);
      setSliderValue(Math.max(0, monthly.length - rangeMonths));
    }
  };

  return (
    <Box sx={{ pb: 4 }}>
      <Typography variant="h3" gutterBottom fontWeight={700} sx={{ mb: 2 }}>
        Moods & Listening Patterns
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 6, fontSize: '1.1rem' }}>
        Analyze your listening moods derived from behavioral patterns: valence (happiness), energy, and danceability based on when and how you listen.
      </Typography>

      {/* Window Selector */}
      <Box sx={{ mb: 6 }}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Time Window</InputLabel>
          <Select
            value={window}
            label="Time Window"
            onChange={(e) => setWindow(e.target.value as typeof window)}
          >
            <MenuItem value="7d">Last 7 days</MenuItem>
            <MenuItem value="30d">Last 30 days</MenuItem>
            <MenuItem value="90d">Last 90 days</MenuItem>
            <MenuItem value="all">All time</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Summary Cards - Mood Ring */}
      <Grid container spacing={{ xs: 2, md: 3 }} sx={{ mb: 8 }}>
        <Grid xs={12} sm={4}>
          <Paper sx={{
            p: 4,
            textAlign: 'center',
            position: 'relative',
            aspectRatio: '1',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              transform: 'translateY(-8px)',
              boxShadow: '0 12px 24px rgba(0, 0, 0, 0.15)',
            },
          }}>
            <Box sx={{ position: 'absolute', top: 8, right: 8 }}>
              <Tooltip
                title="Valence measures positivity and happiness in your listening patterns. Higher scores indicate more upbeat listening times (weekends, daytime hours)."
                arrow
              >
                <IconButton size="small">
                  <InfoOutlined fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Box sx={{ position: 'relative', display: 'inline-flex', mb: 2, mx: 'auto' }}>
              <CircularProgress
                variant="determinate"
                value={(summary?.avg_valence ?? 0) * 100}
                size={120}
                thickness={4}
                sx={{ color: MOOD_COLORS.valence }}
              />
              <Box
                sx={{
                  top: 0,
                  left: 0,
                  bottom: 0,
                  right: 0,
                  position: 'absolute',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <SentimentVerySatisfied sx={{ fontSize: 48, color: MOOD_COLORS.valence }} />
              </Box>
            </Box>
            <Typography variant="h4" fontWeight={700}>
              {loading ? '—' : formatPercent(summary?.avg_valence ?? null)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Valence (Happiness)
            </Typography>
          </Paper>
        </Grid>

        <Grid xs={12} sm={4}>
          <Paper sx={{
            p: 4,
            textAlign: 'center',
            position: 'relative',
            aspectRatio: '1',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              transform: 'translateY(-8px)',
              boxShadow: '0 12px 24px rgba(0, 0, 0, 0.15)',
            },
          }}>
            <Box sx={{ position: 'absolute', top: 8, right: 8 }}>
              <Tooltip
                title="Energy reflects the intensity and activity level of your listening. Morning and afternoon listening typically shows higher energy."
                arrow
              >
                <IconButton size="small">
                  <InfoOutlined fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Box sx={{ position: 'relative', display: 'inline-flex', mb: 2, mx: 'auto' }}>
              <CircularProgress
                variant="determinate"
                value={(summary?.avg_energy ?? 0) * 100}
                size={120}
                thickness={4}
                sx={{ color: MOOD_COLORS.energy }}
              />
              <Box
                sx={{
                  top: 0,
                  left: 0,
                  bottom: 0,
                  right: 0,
                  position: 'absolute',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Bolt sx={{ fontSize: 48, color: MOOD_COLORS.energy }} />
              </Box>
            </Box>
            <Typography variant="h4" fontWeight={700}>
              {loading ? '—' : formatPercent(summary?.avg_energy ?? null)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Energy
            </Typography>
          </Paper>
        </Grid>

        <Grid xs={12} sm={4}>
          <Paper sx={{
            p: 4,
            textAlign: 'center',
            position: 'relative',
            aspectRatio: '1',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              transform: 'translateY(-8px)',
              boxShadow: '0 12px 24px rgba(0, 0, 0, 0.15)',
            },
          }}>
            <Box sx={{ position: 'absolute', top: 8, right: 8 }}>
              <Tooltip
                title="Danceability represents rhythmic engagement, derived from whether you listen to tracks fully or skip them. Complete listens indicate higher danceability."
                arrow
              >
                <IconButton size="small">
                  <InfoOutlined fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Box sx={{ position: 'relative', display: 'inline-flex', mb: 2, mx: 'auto' }}>
              <CircularProgress
                variant="determinate"
                value={(summary?.avg_danceability ?? 0) * 100}
                size={120}
                thickness={4}
                sx={{ color: MOOD_COLORS.danceability }}
              />
              <Box
                sx={{
                  top: 0,
                  left: 0,
                  bottom: 0,
                  right: 0,
                  position: 'absolute',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <MusicNote sx={{ fontSize: 48, color: MOOD_COLORS.danceability }} />
              </Box>
            </Box>
            <Typography variant="h4" fontWeight={700}>
              {loading ? '—' : formatPercent(summary?.avg_danceability ?? null)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Danceability
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {summary && summary.sample_size > 0 && (
        <Box sx={{ mb: 8, textAlign: 'center' }}>
          <Chip
            label={`Based on ${summary.sample_size.toLocaleString()} listening sessions`}
            size="small"
            sx={{ backgroundColor: 'rgba(46, 216, 129, 0.1)' }}
          />
        </Box>
      )}

      {/* Monthly Mood Trends */}
      <Paper sx={{
        p: 5,
        mb: 8,
        transition: 'all 0.3s ease-in-out',
        '&:hover': {
          boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
        },
      }}>
        <Box sx={{ mb: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: chartRange !== 'all' && getMaxSliderValue() > 0 ? 3 : 0 }}>
            <Typography variant="h5" fontWeight={700}>
              Mood Trends Over Time
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

          {/* Time Range Slider - moved to top */}
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
                      { value: 0, label: monthly[0]?.month || '' },
                      { value: getMaxSliderValue(), label: monthly[monthly.length - 1]?.month || '' },
                    ]}
                    valueLabelDisplay="auto"
                    valueLabelFormat={(value) => {
                      const startMonth = monthly[value]?.month || '';
                      const endMonth = monthly[Math.min(value + getRangeMonths() - 1, monthly.length - 1)]?.month || '';
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
          <Skeleton variant="rectangular" height={500} />
        ) : monthly.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="h6" color="text.secondary">
              No listening data available yet
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Add your Spotify streaming history to see mood trends
            </Typography>
          </Box>
        ) : (
          <>
            <LineChart
              xAxis={[
                {
                  data: filteredMonthly.map((_, idx) => idx),
                  scaleType: 'point',
                  valueFormatter: (value) => filteredMonthly[value]?.month || '',
                },
              ]}
              series={[
                {
                  data: filteredMonthly.map((d) => (d.avg_valence ?? 0) * 100),
                  label: 'Valence (Happiness)',
                  color: MOOD_COLORS.valence,
                  curve: 'catmullRom',
                },
                {
                  data: filteredMonthly.map((d) => (d.avg_energy ?? 0) * 100),
                  label: 'Energy',
                  color: MOOD_COLORS.energy,
                  curve: 'catmullRom',
                },
                {
                  data: filteredMonthly.map((d) => (d.avg_danceability ?? 0) * 100),
                  label: 'Danceability',
                  color: MOOD_COLORS.danceability,
                  curve: 'catmullRom',
                },
              ]}
              height={500}
              yAxis={[{ min: 0, max: 100 }]}
              slotProps={{
                legend: {
                  direction: 'row',
                  position: { vertical: 'bottom', horizontal: 'center' },
                  padding: 0,
                },
              }}
            />
          </>
        )}
      </Paper>

      {/* Context Comparisons */}
      {contexts && (
        <>
          {/* Weekday vs Weekend */}
          <Paper sx={{
            p: 5,
            mb: 8,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Typography variant="h5" gutterBottom fontWeight={700} sx={{ mb: 4 }}>
              Weekday vs Weekend
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <BarChart
                xAxis={[{ scaleType: 'band', data: ['Weekday', 'Weekend'] }]}
                series={[
                  {
                    data: [
                      (contexts.weekday_vs_weekend.weekday.avg_valence ?? 0) * 100,
                      (contexts.weekday_vs_weekend.weekend.avg_valence ?? 0) * 100,
                    ],
                    label: 'Valence',
                    color: MOOD_COLORS.valence,
                  },
                  {
                    data: [
                      (contexts.weekday_vs_weekend.weekday.avg_energy ?? 0) * 100,
                      (contexts.weekday_vs_weekend.weekend.avg_energy ?? 0) * 100,
                    ],
                    label: 'Energy',
                    color: MOOD_COLORS.energy,
                  },
                  {
                    data: [
                      (contexts.weekday_vs_weekend.weekday.avg_danceability ?? 0) * 100,
                      (contexts.weekday_vs_weekend.weekend.avg_danceability ?? 0) * 100,
                    ],
                    label: 'Danceability',
                    color: MOOD_COLORS.danceability,
                  },
                ]}
                height={400}
                yAxis={[{ min: 0, max: 100 }]}
              />
            )}
          </Paper>
        </>
      )}
    </Box>
  );
}
