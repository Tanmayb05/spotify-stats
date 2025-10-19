import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Chip,
  Skeleton,
  Slider,
} from '@mui/material';
import { LineChart } from '@mui/x-charts/LineChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { api } from '../api/client';
import type {
  DiscoveryTimeline,
  ArtistLoyalty,
  ArtistObsession,
  ReflectiveInsights,
} from '../types/api';
import DataTable from '../components/DataTable';
import type { Column } from '../components/DataTable';
import ErrorBanner from '../components/ErrorBanner';

export default function Discovery() {
  // State for timeline data
  const [timeline, setTimeline] = useState<DiscoveryTimeline[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(true);

  // State for loyalty data
  const [loyalty, setLoyalty] = useState<ArtistLoyalty[]>([]);
  const [loyaltyLoading, setLoyaltyLoading] = useState(true);

  // State for obsessions data
  const [obsessions, setObsessions] = useState<ArtistObsession[]>([]);
  const [obsessionsLoading, setObsessionsLoading] = useState(true);

  // State for reflective insights
  const [insights, setInsights] = useState<ReflectiveInsights | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(true);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Chart range and slider state
  const [chartRange, setChartRange] = useState<'all' | '12m' | '6m' | '3m'>('all');
  const [sliderValue, setSliderValue] = useState<number>(0);

  // Fetch all data on mount
  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      setError(null);

      // Fetch all data in parallel
      const [timelineData, loyaltyData, obsessionsData, insightsData] = await Promise.all([
        api.getDiscoveryTimeline(),
        api.getArtistLoyalty(20),
        api.getArtistObsessions(15),
        api.getReflectiveInsights(),
      ]);

      setTimeline(timelineData);
      setLoyalty(loyaltyData);
      setObsessions(obsessionsData);
      setInsights(insightsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load discovery data');
    } finally {
      setTimelineLoading(false);
      setLoyaltyLoading(false);
      setObsessionsLoading(false);
      setInsightsLoading(false);
    }
  };

  // Filter timeline data based on chart range and slider position
  const getRangeMonths = () => {
    if (chartRange === 'all') return timeline.length;
    return parseInt(chartRange);
  };

  const getMaxSliderValue = () => {
    const rangeMonths = getRangeMonths();
    return Math.max(0, timeline.length - rangeMonths);
  };

  const filteredTimeline = chartRange === 'all'
    ? timeline
    : timeline.slice(sliderValue, sliderValue + getRangeMonths());

  const handleRangeChange = (newRange: typeof chartRange) => {
    setChartRange(newRange);
    if (newRange === 'all') {
      setSliderValue(0);
    } else {
      const rangeMonths = parseInt(newRange);
      setSliderValue(Math.max(0, timeline.length - rangeMonths));
    }
  };

  // Table columns for loyalty
  const loyaltyColumns: Column<ArtistLoyalty>[] = [
    { key: 'artist', label: 'Artist', align: 'left', width: '40%' },
    {
      key: 'return_prob',
      label: 'Return Probability (%)',
      align: 'right',
      format: (val) => `${val.toFixed(1)}%`,
    },
    {
      key: 'half_life_days',
      label: 'Half-Life (days)',
      align: 'right',
      format: (val) => val.toFixed(1),
    },
    {
      key: 'total_streams',
      label: 'Total Streams',
      align: 'right',
      format: (val) => val.toLocaleString(),
    },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        Artist Discovery
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Explore your journey of discovering new artists and track your listening loyalty.
      </Typography>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <Grid container spacing={3} sx={{ mt: 1 }}>
        {/* Discovery Timeline */}
        <Grid size={12}>
          <Paper sx={{
            p: 3,
            transition: 'all 0.3s ease-in-out',
            '&:hover': {
              boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
            },
          }}>
            <Box sx={{ mb: chartRange !== 'all' && getMaxSliderValue() > 0 ? 3 : 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: chartRange !== 'all' && getMaxSliderValue() > 0 ? 3 : 0 }}>
                <Box>
                  <Typography variant="h6" gutterBottom fontWeight={600}>
                    Discovery Timeline
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Track when you discovered new artists over time
                  </Typography>
                </Box>
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
                          { value: 0, label: timeline[0]?.month || '' },
                          { value: getMaxSliderValue(), label: timeline[timeline.length - 1]?.month || '' },
                        ]}
                        valueLabelDisplay="auto"
                        valueLabelFormat={(value) => {
                          const startMonth = timeline[value]?.month || '';
                          const endMonth = timeline[Math.min(value + getRangeMonths() - 1, timeline.length - 1)]?.month || '';
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

            {timelineLoading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : filteredTimeline.length > 0 ? (
              <LineChart
                xAxis={[
                  {
                    data: filteredTimeline.map((_, idx) => idx),
                    scaleType: 'point',
                    valueFormatter: (value) => filteredTimeline[value]?.month || '',
                  },
                ]}
                series={[
                  {
                    data: filteredTimeline.map((d) => d.new_artists_count),
                    label: 'New Artists Discovered',
                    color: '#2dd881',
                    curve: 'monotoneX',
                  },
                ]}
                height={400}
                margin={{ left: 60, right: 20, top: 20, bottom: 60 }}
                slotProps={{
                  legend: { hidden: false, position: { vertical: 'top', horizontal: 'right' } },
                }}
              />
            ) : (
              <Box sx={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="text.secondary">No discovery data available</Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Loyalty Table */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom fontWeight={600}>
              Artist Loyalty
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Artists you consistently return to listen
            </Typography>
            <DataTable
              columns={loyaltyColumns}
              data={loyalty}
              loading={loyaltyLoading}
              emptyMessage="No loyalty data available"
              maxHeight="400px"
              aria-label="Artist loyalty table"
            />
          </Paper>
        </Grid>

        {/* Obsessions */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom fontWeight={600}>
              Obsession Periods
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Times when an artist dominated your listening (30%+ share in a week)
            </Typography>
            {obsessionsLoading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : obsessions.length > 0 ? (
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                <BarChart
                  yAxis={[
                    {
                      data: obsessions.slice(0, 10).map((o) => o.artist),
                      scaleType: 'band',
                    },
                  ]}
                  series={[
                    {
                      data: obsessions.slice(0, 10).map((o) => o.period_share),
                      label: 'Period Share (%)',
                      color: '#4ea699',
                    },
                  ]}
                  layout="horizontal"
                  height={400}
                  margin={{ left: 250, right: 40, top: 40, bottom: 60 }}
                  slotProps={{
                    legend: { hidden: false, position: { vertical: 'top', horizontal: 'right' } },
                  }}
                  sx={{
                    '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': {
                      fontSize: '0.875rem',
                    },
                  }}
                />
              </Box>
            ) : (
              <Box sx={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="text.secondary">No obsession periods found</Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Reflective Insights */}
        <Grid size={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom fontWeight={600}>
              Reflective Insights
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Key patterns and milestones from your listening journey
            </Typography>
            {insightsLoading ? (
              <Grid container spacing={2} sx={{ mt: 1 }}>
                {[...Array(4)].map((_, i) => (
                  <Grid size={{ xs: 12, sm: 6, md: 3 }} key={i}>
                    <Skeleton variant="rectangular" height={140} />
                  </Grid>
                ))}
              </Grid>
            ) : insights ? (
              <Grid container spacing={2} sx={{ mt: 1 }}>
                {/* Stat Cards */}
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card
                    sx={{
                      height: '100%',
                      transition: 'all 0.3s ease-in-out',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
                      },
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 1.5 }}>
                        Longest Streak
                      </Typography>
                      <Typography variant="h3" fontWeight={700} color="primary.main" sx={{ mb: 0.5 }}>
                        {insights.longest_streak_days}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        consecutive days
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card
                    sx={{
                      height: '100%',
                      transition: 'all 0.3s ease-in-out',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
                      },
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 1.5 }}>
                        Peak Hour
                      </Typography>
                      <Typography variant="h3" fontWeight={700} color="primary.main" sx={{ mb: 0.5 }}>
                        {insights.most_active_hour}:00
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        most active time
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card
                    sx={{
                      height: '100%',
                      transition: 'all 0.3s ease-in-out',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
                      },
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 1.5 }}>
                        Favorite Day
                      </Typography>
                      <Typography variant="h3" fontWeight={700} color="primary.main" sx={{ mb: 0.5 }}>
                        {insights.most_active_day}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        most active
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card
                    sx={{
                      height: '100%',
                      transition: 'all 0.3s ease-in-out',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
                      },
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 1.5 }}>
                        Daily Average
                      </Typography>
                      <Typography variant="h3" fontWeight={700} color="primary.main" sx={{ mb: 0.5 }}>
                        {insights.avg_streams_per_day.toFixed(0)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        streams per day
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            ) : null}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
