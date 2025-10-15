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
  Alert,
} from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import { Groups, Science, TrendingUp } from '@mui/icons-material';
import { api } from '../api/client';
import type {
  SessionClustersResponse,
  SessionCentroid,
  SessionAssignment,
} from '../types/api';
import DataTable from '../components/DataTable';
import type { Column } from '../components/DataTable';
import ErrorBanner from '../components/ErrorBanner';

// Cluster colors matching brand palette
const CLUSTER_COLORS = [
  '#2dd881', // Emerald
  '#4ea699', // Keppel
  '#6fedb7', // Aquamarine
  '#140d4f', // Federal blue
  '#1c0b19', // Dark purple
  '#2dd881', // Repeat colors if more clusters
  '#4ea699',
  '#6fedb7',
];

const CLUSTER_NAMES = [
  'Quick Listens',
  'Deep Dives',
  'Discovery Sessions',
  'Background Music',
  'Focused Listening',
  'Exploratory',
  'Casual Play',
  'Intense Sessions',
];

export default function Sessions() {
  // State for cluster data
  const [clustersData, setClustersData] = useState<SessionClustersResponse | null>(null);
  const [clustersLoading, setClustersLoading] = useState(true);

  // State for centroids
  const [centroids, setCentroids] = useState<SessionCentroid[]>([]);
  const [centroidsLoading, setCentroidsLoading] = useState(true);

  // State for session assignments
  const [assignments, setAssignments] = useState<SessionAssignment[]>([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState(true);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Fetch all data on mount
  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      setError(null);

      // Fetch all data in parallel
      const [clustersRes, centroidsRes, assignmentsRes] = await Promise.all([
        api.getSessionClusters(),
        api.getSessionCentroids(),
        api.getSessionAssignments(50),
      ]);

      setClustersData(clustersRes);
      setCentroids(centroidsRes);
      setAssignments(assignmentsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session data');
    } finally {
      setClustersLoading(false);
      setCentroidsLoading(false);
      setAssignmentsLoading(false);
    }
  };

  // Get cluster name
  const getClusterName = (clusterId: number): string => {
    return CLUSTER_NAMES[clusterId % CLUSTER_NAMES.length];
  };

  // Get cluster color
  const getClusterColor = (clusterId: number): string => {
    return CLUSTER_COLORS[clusterId % CLUSTER_COLORS.length];
  };

  // Format feature names for display
  const formatFeatureName = (name: string): string => {
    return name
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Table columns for session assignments
  const assignmentColumns: Column<SessionAssignment>[] = [
    {
      key: 'cluster_label',
      label: 'Cluster',
      align: 'center',
      width: '120px',
      format: (val) => (
        <Chip
          label={getClusterName(val as number)}
          size="small"
          sx={{
            bgcolor: getClusterColor(val as number),
            color: 'white',
            fontWeight: 600,
          }}
        />
      ),
    },
    {
      key: 'start_time',
      label: 'Start Time',
      align: 'left',
      format: (val) =>
        new Date(val as string).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }),
    },
    {
      key: 'duration_minutes',
      label: 'Duration (min)',
      align: 'right',
      format: (val) => `${val.toFixed(1)}`,
    },
    {
      key: 'track_count',
      label: 'Tracks',
      align: 'right',
    },
    {
      key: 'skip_ratio',
      label: 'Skip Rate (%)',
      align: 'right',
      format: (val) => `${val.toFixed(1)}%`,
    },
    {
      key: 'diversity_score',
      label: 'Diversity',
      align: 'right',
      format: (val) => val.toFixed(2),
    },
    {
      key: 'platform',
      label: 'Platform',
      align: 'left',
      format: (val) => {
        const platform = val as string;
        return platform.length > 20 ? `${platform.substring(0, 17)}...` : platform;
      },
    },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        Listening Sessions
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Discover patterns in your listening sessions through clustering and analysis.
      </Typography>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <Grid container spacing={3} sx={{ mt: 1 }}>
        {/* Clustering Overview */}
        {clustersLoading ? (
          <Grid size={12}>
            <Skeleton variant="rectangular" height={120} />
          </Grid>
        ) : clustersData?.error ? (
          <Grid size={12}>
            <Alert severity="info">{clustersData.error}</Alert>
          </Grid>
        ) : clustersData ? (
          <Grid size={12}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Science color="primary" sx={{ fontSize: 32 }} />
                <Box>
                  <Typography variant="h6" fontWeight={600}>
                    Session Clustering Analysis
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    K-means clustering identified {clustersData.n_clusters} distinct listening patterns from{' '}
                    {clustersData.total_sessions} sessions (silhouette score: {clustersData.silhouette_score})
                  </Typography>
                </Box>
              </Box>

              <Grid container spacing={2} sx={{ mt: 1 }}>
                {[...Array(3)].map((_, i) => {
                  const stat = [
                    {
                      label: 'Total Sessions',
                      value: clustersData.total_sessions.toLocaleString(),
                      icon: <Groups />,
                    },
                    {
                      label: 'Clusters Found',
                      value: clustersData.n_clusters.toString(),
                      icon: <TrendingUp />,
                    },
                    {
                      label: 'Quality Score',
                      value: (clustersData.silhouette_score * 100).toFixed(0) + '%',
                      icon: <Science />,
                    },
                  ][i];

                  return (
                    <Grid size={{ xs: 12, sm: 4 }} key={i}>
                      <Card variant="outlined">
                        <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Box sx={{ color: 'primary.main' }}>{stat.icon}</Box>
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {stat.label}
                            </Typography>
                            <Typography variant="h6" fontWeight={700}>
                              {stat.value}
                            </Typography>
                          </Box>
                        </CardContent>
                      </Card>
                    </Grid>
                  );
                })}
              </Grid>
            </Paper>
          </Grid>
        ) : null}

        {/* Cluster Profiles */}
        {centroidsLoading ? (
          <>
            {[...Array(3)].map((_, i) => (
              <Grid size={{ xs: 12, lg: 6 }} key={i}>
                <Skeleton variant="rectangular" height={400} />
              </Grid>
            ))}
          </>
        ) : centroids.length > 0 && clustersData?.clusters ? (
          centroids.map((centroid) => {
            const clusterProfile = clustersData.clusters.find((c) => c.cluster_id === centroid.cluster_id);

            if (!clusterProfile) return null;

            // Prepare data for bar chart
            const featureNames = Object.keys(centroid.features);
            const featureValues = Object.values(centroid.features);

            // Normalize values for better visualization (scale to 0-100 range)
            const normalizedValues = featureValues.map((val, idx) => {
              const name = featureNames[idx];
              if (name === 'hour_of_day') return (val / 24) * 100;
              if (name === 'is_weekend') return val * 100;
              if (name === 'skip_ratio' || name === 'diversity_score') return val * 100;
              if (name === 'duration_minutes') return Math.min((val / 120) * 100, 100);
              if (name === 'track_count') return Math.min((val / 50) * 100, 100);
              if (name === 'unique_artists_count') return Math.min((val / 20) * 100, 100);
              if (name === 'avg_track_duration') return Math.min((val / 5) * 100, 100);
              return val;
            });

            return (
              <Grid size={{ xs: 12, lg: 6 }} key={centroid.cluster_id}>
                <Paper
                  sx={{
                    p: 3,
                    transition: 'all 0.3s ease-in-out',
                    border: 2,
                    borderColor: getClusterColor(centroid.cluster_id),
                    '&:hover': {
                      boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box>
                      <Typography variant="h6" fontWeight={700}>
                        {getClusterName(centroid.cluster_id)}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Cluster {centroid.cluster_id} · {clusterProfile.session_count} sessions
                      </Typography>
                    </Box>
                    <Chip
                      label={`#${centroid.cluster_id}`}
                      sx={{
                        bgcolor: getClusterColor(centroid.cluster_id),
                        color: 'white',
                        fontWeight: 700,
                      }}
                    />
                  </Box>

                  {/* Key Statistics */}
                  <Grid container spacing={1} sx={{ mb: 2 }}>
                    <Grid size={6}>
                      <Typography variant="caption" color="text.secondary">
                        Avg Duration
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {clusterProfile.avg_duration.toFixed(1)} min
                      </Typography>
                    </Grid>
                    <Grid size={6}>
                      <Typography variant="caption" color="text.secondary">
                        Avg Tracks
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {clusterProfile.avg_tracks.toFixed(0)} tracks
                      </Typography>
                    </Grid>
                    <Grid size={6}>
                      <Typography variant="caption" color="text.secondary">
                        Skip Rate
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {clusterProfile.avg_skip_ratio.toFixed(1)}%
                      </Typography>
                    </Grid>
                    <Grid size={6}>
                      <Typography variant="caption" color="text.secondary">
                        Peak Hour
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {clusterProfile.common_hour}:00
                      </Typography>
                    </Grid>
                  </Grid>

                  {/* Feature Chart */}
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom sx={{ mt: 2 }}>
                    Cluster Profile Features
                  </Typography>
                  <Box sx={{ width: '100%', overflowX: 'auto' }}>
                    <BarChart
                      yAxis={[
                        {
                          data: featureNames.map(formatFeatureName),
                          scaleType: 'band',
                        },
                      ]}
                      series={[
                        {
                          data: normalizedValues,
                          color: getClusterColor(centroid.cluster_id),
                        },
                      ]}
                      layout="horizontal"
                      height={300}
                      margin={{ left: 200, right: 40, top: 20, bottom: 40 }}
                      slotProps={{ legend: { hidden: true } }}
                      sx={{
                        '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': {
                          fontSize: '0.75rem',
                        },
                      }}
                    />
                  </Box>
                </Paper>
              </Grid>
            );
          })
        ) : null}

        {/* Recent Session Assignments */}
        <Grid size={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom fontWeight={600}>
              Recent Sessions
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Your latest listening sessions with their assigned cluster labels
            </Typography>
            <DataTable
              columns={assignmentColumns}
              data={assignments}
              loading={assignmentsLoading}
              emptyMessage="No session data available"
              maxHeight="500px"
              aria-label="Recent session assignments table"
            />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
