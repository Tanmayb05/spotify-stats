import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Button,
  Autocomplete,
  TextField,
  Slider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Skeleton,
  LinearProgress,
  List,
  ListItem,
  Divider,
} from '@mui/material';
import { Download, PlayArrow } from '@mui/icons-material';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import { formatDate } from '../utils/format';
import type { SimulationResponse } from '../types/api';

type HourValue = number | 'any';

const HOURS: { value: HourValue; label: string }[] = [
  { value: 'any', label: 'Any hour' },
  ...Array.from({ length: 24 }, (_, h) => ({
    value: h as HourValue,
    label: `${String(h).padStart(2, '0')}:00`,
  })),
];

const DEFAULT_N = 20;

// Trigger a browser download of a same-origin CSV endpoint (matches Recommendations.tsx).
function handleExportCSV(url: string, filename: string) {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export default function Simulator() {
  const { setError } = useAppStore();
  const [loadingArtists, setLoadingArtists] = useState(true);
  const [running, setRunning] = useState(false);
  const [artists, setArtists] = useState<string[]>([]);
  const [seed, setSeed] = useState<string | null>(null);
  const [n, setN] = useState<number>(DEFAULT_N);
  const [hour, setHour] = useState<HourValue>('any');
  const [result, setResult] = useState<SimulationResponse | null>(null);
  // The seed text the user asked for, kept so an "unknown" result can name it.
  const [requestedSeed, setRequestedSeed] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoadingArtists(true);
      setError(null);
      try {
        const data = await api.getSimulationArtists();
        if (cancelled) return;
        setArtists(data);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load artists');
      } finally {
        if (!cancelled) setLoadingArtists(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [setError]);

  const runSimulation = async () => {
    setRunning(true);
    setError(null);
    setRequestedSeed(seed);
    try {
      const data = await api.getSimulation(
        n,
        seed ?? undefined,
        hour === 'any' ? undefined : hour
      );
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setRunning(false);
    }
  };

  const exportUrl = api.exportSimulation(
    50,
    seed ?? undefined,
    hour === 'any' ? undefined : hour
  );

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={1} mb={1}>
        <Typography variant="h4" fontWeight={700}>
          Predictive Simulator
        </Typography>
        <Chip label="⚗️ Experimental" size="small" color="secondary" />
      </Box>
      <Typography variant="body1" color="text.secondary" paragraph>
        A deterministic walk over an artist-level Markov chain built from your
        in-session play history. Pick a seed artist and an hour of day, then
        simulate the most likely next plays with their transition probabilities.
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
          role="group"
          aria-label="Simulation controls"
          display="flex"
          alignItems="center"
          flexWrap="wrap"
          gap={2}
          mb={3}
        >
          <Autocomplete
            options={artists}
            value={seed}
            onChange={(_, v) => setSeed(v)}
            loading={loadingArtists}
            sx={{ minWidth: 260 }}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Seed artist (optional)"
                size="small"
                helperText="Leave blank to auto-seed from your top artist"
              />
            )}
          />

          <Box sx={{ width: 220 }}>
            <Typography variant="caption" color="text.secondary">
              Plays to simulate: {n}
            </Typography>
            <Slider
              value={n}
              min={5}
              max={50}
              step={1}
              onChange={(_, v) => setN(v as number)}
              valueLabelDisplay="auto"
              aria-label="Number of plays to simulate"
            />
          </Box>

          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="sim-hour-label">Hour of day</InputLabel>
            <Select
              labelId="sim-hour-label"
              value={hour}
              label="Hour of day"
              onChange={(e) => setHour(e.target.value as HourValue)}
            >
              {HOURS.map((h) => (
                <MenuItem key={String(h.value)} value={h.value}>
                  {h.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Button
            variant="contained"
            startIcon={<PlayArrow />}
            onClick={runSimulation}
            disabled={running}
          >
            Simulate
          </Button>

          <Button
            variant="outlined"
            size="small"
            startIcon={<Download />}
            disabled={!result || result.count === 0}
            onClick={() => handleExportCSV(exportUrl, 'simulation.csv')}
          >
            Export CSV
          </Button>
        </Box>

        {/* Body */}
        {running ? (
          <Skeleton variant="rectangular" height={480} />
        ) : !result ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="h6" color="text.secondary">
              Choose options and press Simulate
            </Typography>
          </Box>
        ) : result.count === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="h6" color="text.secondary">
              No transitions available for this seed / hour
            </Typography>
          </Box>
        ) : (
          <Box>
            <Box display="flex" gap={1} flexWrap="wrap" mb={2}>
              {result.seed_status === 'unknown' && (
                <Chip
                  size="small"
                  color="warning"
                  label={
                    requestedSeed
                      ? `"${requestedSeed}" not found — using ${result.seed}`
                      : `Using ${result.seed}`
                  }
                />
              )}
              {result.seed_status === 'default' && (
                <Chip size="small" label={`Auto-seeded from ${result.seed}`} />
              )}
              {result.hour != null && (
                <Chip
                  size="small"
                  variant="outlined"
                  label={`Hour ${String(result.hour).padStart(2, '0')}:00`}
                />
              )}
              {result.truncated && (
                <Chip
                  size="small"
                  variant="outlined"
                  label="Chain ended early (no further transitions)"
                />
              )}
            </Box>

            <Typography role="status" sx={{ position: 'absolute', left: -9999 }}>
              Simulated {result.count} plays starting from {result.seed}
            </Typography>

            <List disablePadding>
              {result.sequence.map((s) => (
                <Box key={s.step}>
                  <ListItem sx={{ px: 0, display: 'block' }}>
                    <Box
                      display="flex"
                      justifyContent="space-between"
                      alignItems="baseline"
                      gap={1}
                    >
                      <Typography variant="body2" fontWeight={600}>
                        #{s.step}&nbsp;&nbsp;{s.from_artist}&nbsp;→&nbsp;
                        {s.to_artist}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {(s.probability * 100).toFixed(1)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(100, s.probability * 100)}
                      aria-label={`transition probability ${(
                        s.probability * 100
                      ).toFixed(0)} percent`}
                      sx={{ mt: 0.5, height: 6, borderRadius: 3 }}
                    />
                  </ListItem>
                  {s.step < result.sequence.length && <Divider />}
                </Box>
              ))}
            </List>
          </Box>
        )}

        {result && (
          <Typography
            variant="caption"
            color="text.secondary"
            display="block"
            sx={{ mt: 3 }}
          >
            Generated {formatDate(result.generated_at)} · deterministic
            most-probable walk, Laplace-smoothed, 30-min session gap
          </Typography>
        )}
      </Paper>
    </Box>
  );
}
