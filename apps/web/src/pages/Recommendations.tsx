import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Button,
  Card,
  CardContent,
  Divider,
  Skeleton,
  Grid,
} from '@mui/material';
import { Download } from '@mui/icons-material';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import { formatDate } from '../utils/format';
import type { Recommendation, TargetMood } from '../types/api';

type MoodFilter = 'all' | TargetMood;

const MOOD_FILTERS: { value: MoodFilter; label: string; color: string }[] = [
  { value: 'all', label: 'All', color: '#4ea699' },
  { value: 'happy', label: 'Happy', color: '#10b981' },
  { value: 'energetic', label: 'Energetic', color: '#f59e0b' },
  { value: 'chill', label: 'Chill', color: '#8b5cf6' },
];

const TOP_K = 24;

// Trigger a browser download of a same-origin CSV endpoint (matches Overview.tsx).
function handleExportCSV(url: string, filename: string) {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export default function Recommendations() {
  const { setError, selectedUserId } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [generatedAt, setGeneratedAt] = useState<string>('');
  const [mood, setMood] = useState<MoodFilter>('all');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getRecommendations(
          TOP_K,
          mood === 'all' ? undefined : mood
        );
        if (cancelled) return;
        setRecs(data.recommendations);
        setGeneratedAt(data.generated_at);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load recommendations');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [mood, selectedUserId, setError]);

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={1} mb={1}>
        <Typography variant="h4" fontWeight={700}>
          Recommendations
        </Typography>
        <Chip label="⚗️ Experimental" size="small" color="secondary" />
      </Box>
      <Typography variant="body1" color="text.secondary" paragraph>
        Content-based picks scored against a recency-weighted profile of your
        listening, then diversified so the list is not all one sound.
      </Typography>

      <Paper
        sx={{
          p: 3,
          transition: 'all 0.3s ease-in-out',
          '&:hover': { boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)' },
        }}
      >
        {/* Controls */}
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={2}
          mb={3}
        >
          <Box role="group" aria-label="Filter by mood" display="flex" gap={1} flexWrap="wrap">
            {MOOD_FILTERS.map((m) => (
              <Chip
                key={m.value}
                label={m.label}
                size="small"
                onClick={() => setMood(m.value)}
                color={mood === m.value ? 'primary' : 'default'}
                aria-pressed={mood === m.value}
                icon={
                  <Box
                    component="span"
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      bgcolor: m.color,
                      ml: 1,
                    }}
                  />
                }
                sx={{ cursor: 'pointer' }}
              />
            ))}
          </Box>

          <Button
            variant="outlined"
            size="small"
            startIcon={<Download />}
            onClick={() =>
              handleExportCSV(
                api.exportRecommendations(50, mood === 'all' ? undefined : mood),
                'recommendations.csv'
              )
            }
          >
            Export CSV
          </Button>
        </Box>

        {/* Body */}
        {loading ? (
          <Grid container spacing={2}>
            {[...Array(12)].map((_, i) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={i}>
                <Skeleton variant="rectangular" height={160} />
              </Grid>
            ))}
          </Grid>
        ) : recs.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="h6" color="text.secondary">
              No recommendations available
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={2}>
            {recs.map((r) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={r.track_uri || `${r.track}-${r.artist}`}>
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
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1}>
                      <Typography variant="subtitle1" fontWeight={700} noWrap title={r.track}>
                        {r.track}
                      </Typography>
                      <Chip
                        size="small"
                        color="primary"
                        label={r.score.toFixed(2)}
                        aria-label={`match score ${r.score.toFixed(2)}`}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary" noWrap title={r.artist}>
                      {r.artist}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" noWrap display="block">
                      {r.album}
                    </Typography>

                    <Divider sx={{ my: 1.5 }} />

                    <Typography variant="caption" color="text.secondary">
                      {r.why.summary}
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap" mt={1}>
                      {r.why.top_features.map((f) => (
                        <Chip
                          key={f.feature}
                          size="small"
                          variant="outlined"
                          label={f.feature.replace(/_/g, ' ')}
                        />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}

        {!loading && generatedAt && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 3 }}>
            Generated {formatDate(generatedAt)} · heuristic feature model (no Spotify
            audio features available)
          </Typography>
        )}
      </Paper>
    </Box>
  );
}
