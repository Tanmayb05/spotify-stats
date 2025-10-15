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
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  Divider,
  Alert,
  Snackbar,
  IconButton,
} from '@mui/material';
import {
  CalendarMonth,
  ContentCopy,
  EmojiEvents,
  Explore,
  LocalFireDepartment,
  MusicNote,
} from '@mui/icons-material';
import { api } from '../api/client';
import type { Milestone, FlashbackData } from '../types/api';
import ErrorBanner from '../components/ErrorBanner';

export default function Milestones() {
  // State for milestones
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [milestonesLoading, setMilestonesLoading] = useState(true);

  // State for flashback
  const [flashbackDate, setFlashbackDate] = useState<string>('');
  const [flashbackData, setFlashbackData] = useState<FlashbackData | null>(null);
  const [flashbackLoading, setFlashbackLoading] = useState(false);

  // State for copy notification
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Fetch milestones on mount
  useEffect(() => {
    fetchMilestones();
  }, []);

  const fetchMilestones = async () => {
    try {
      setError(null);
      setMilestonesLoading(true);
      const data = await api.getMilestones();
      setMilestones(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load milestones');
    } finally {
      setMilestonesLoading(false);
    }
  };

  const fetchFlashback = async () => {
    if (!flashbackDate) {
      setError('Please select a date for flashback');
      return;
    }

    try {
      setError(null);
      setFlashbackLoading(true);
      const data = await api.getFlashback(flashbackDate);
      setFlashbackData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load flashback');
      setFlashbackData(null);
    } finally {
      setFlashbackLoading(false);
    }
  };

  const handleCopySummary = () => {
    if (!flashbackData) return;

    const summary = `
📅 Listening Flashback - ${flashbackData.date}
Day: ${flashbackData.day_of_week}

📊 Stats:
- Streams: ${flashbackData.streams}
- Hours: ${flashbackData.hours}
- Unique Artists: ${flashbackData.unique_artists}
- Unique Tracks: ${flashbackData.unique_tracks}
- Skip Rate: ${flashbackData.skip_rate}%

⏰ Activity:
- First Stream: ${flashbackData.first_stream || 'N/A'}
- Last Stream: ${flashbackData.last_stream || 'N/A'}
- Duration: ${flashbackData.listening_duration || 'N/A'}

🎵 Top Artists:
${flashbackData.top_artists.map((a, i) => `${i + 1}. ${a.artist} (${a.streams} streams)`).join('\n')}

🎶 Top Tracks:
${flashbackData.top_tracks.map((t, i) => `${i + 1}. ${t.track} - ${t.artist} (${t.plays} plays)`).join('\n')}

Generated with Spotify Stats
    `.trim();

    navigator.clipboard.writeText(summary);
    setSnackbarMessage('Summary copied to clipboard!');
    setSnackbarOpen(true);
  };

  // Group milestones by year
  const milestonesByYear = milestones.reduce((acc, milestone) => {
    const year = milestone.year;
    if (!acc[year]) {
      acc[year] = [];
    }
    acc[year].push(milestone);
    return acc;
  }, {} as Record<number, Milestone[]>);

  const years = Object.keys(milestonesByYear)
    .map(Number)
    .sort((a, b) => b - a); // Most recent first

  // Get icon for milestone type
  const getMilestoneIcon = (type: Milestone['type']) => {
    switch (type) {
      case 'streak':
        return <LocalFireDepartment sx={{ color: '#2dd881' }} />;
      case 'top_day':
        return <EmojiEvents sx={{ color: '#4ea699' }} />;
      case 'first_artist':
        return <MusicNote sx={{ color: '#6fedb7' }} />;
      case 'diversity':
        return <Explore sx={{ color: '#140d4f' }} />;
      default:
        return <CalendarMonth />;
    }
  };

  // Get label for milestone type
  const getMilestoneLabel = (type: Milestone['type']) => {
    switch (type) {
      case 'streak':
        return 'Streak';
      case 'top_day':
        return 'Peak Day';
      case 'first_artist':
        return 'Discovery';
      case 'diversity':
        return 'Diverse';
      default:
        return 'Milestone';
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        Milestones
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Your listening achievements, streaks, top days, and memorable moments.
      </Typography>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <Grid container spacing={3} sx={{ mt: 1 }}>
        {/* Flashback Widget */}
        <Grid size={12}>
          <Paper
            sx={{
              p: 4,
              transition: 'all 0.3s ease-in-out',
              '&:hover': {
                boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
              },
            }}
          >
            <Box sx={{ mb: 3 }}>
              <Typography variant="h5" fontWeight={700} gutterBottom>
                <CalendarMonth sx={{ verticalAlign: 'middle', mr: 1 }} />
                Flashback
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Travel back to any day and see what you were listening to
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', mb: 3 }}>
              <TextField
                label="Select Date"
                type="date"
                value={flashbackDate}
                onChange={(e) => setFlashbackDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
                sx={{ minWidth: 200 }}
                fullWidth
              />
              <Button
                variant="contained"
                onClick={fetchFlashback}
                disabled={flashbackLoading || !flashbackDate}
                sx={{ minWidth: 120, height: 56 }}
              >
                {flashbackLoading ? 'Loading...' : 'View'}
              </Button>
            </Box>

            {flashbackLoading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : flashbackData ? (
              flashbackData.error || flashbackData.streams === 0 ? (
                <Alert severity="info">
                  {flashbackData.message || flashbackData.error || 'No listening data found for this date'}
                </Alert>
              ) : (
                <Card
                  sx={{
                    background: 'linear-gradient(135deg, rgba(45, 216, 129, 0.05) 0%, rgba(78, 166, 153, 0.05) 100%)',
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <CardContent sx={{ p: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                      <Box>
                        <Typography variant="h6" fontWeight={600}>
                          {new Date(flashbackData.date).toLocaleDateString('en-US', {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                          })}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {flashbackData.day_of_week}
                        </Typography>
                      </Box>
                      <IconButton onClick={handleCopySummary} color="primary" aria-label="Copy summary">
                        <ContentCopy />
                      </IconButton>
                    </Box>

                    <Grid container spacing={2} sx={{ mb: 2 }}>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Streams
                        </Typography>
                        <Typography variant="h5" fontWeight={700} color="primary.main">
                          {flashbackData.streams}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Hours
                        </Typography>
                        <Typography variant="h5" fontWeight={700} color="primary.main">
                          {flashbackData.hours}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Unique Artists
                        </Typography>
                        <Typography variant="h5" fontWeight={700} color="primary.main">
                          {flashbackData.unique_artists}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Skip Rate
                        </Typography>
                        <Typography variant="h5" fontWeight={700} color="primary.main">
                          {flashbackData.skip_rate}%
                        </Typography>
                      </Grid>
                    </Grid>

                    {flashbackData.first_stream && flashbackData.last_stream && (
                      <Box sx={{ mb: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Listening Window
                        </Typography>
                        <Typography variant="body1">
                          {flashbackData.first_stream} → {flashbackData.last_stream}
                        </Typography>
                        {flashbackData.listening_duration && (
                          <Typography variant="caption" color="text.secondary">
                            Duration: {flashbackData.listening_duration}
                          </Typography>
                        )}
                      </Box>
                    )}

                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, md: 6 }}>
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                          Top Artists
                        </Typography>
                        <List dense>
                          {flashbackData.top_artists.map((artist, i) => (
                            <ListItem key={i} disablePadding>
                              <ListItemText
                                primary={`${i + 1}. ${artist.artist}`}
                                secondary={`${artist.streams} streams`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Grid>
                      <Grid size={{ xs: 12, md: 6 }}>
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                          Top Tracks
                        </Typography>
                        <List dense>
                          {flashbackData.top_tracks.map((track, i) => (
                            <ListItem key={i} disablePadding>
                              <ListItemText
                                primary={`${i + 1}. ${track.track}`}
                                secondary={`${track.artist} · ${track.plays} plays`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Grid>
                    </Grid>
                  </CardContent>
                </Card>
              )
            ) : null}
          </Paper>
        </Grid>

        {/* Milestones List */}
        <Grid size={12}>
          <Paper
            sx={{
              p: 4,
              transition: 'all 0.3s ease-in-out',
              '&:hover': {
                boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)',
              },
            }}
          >
            <Typography variant="h5" fontWeight={700} gutterBottom>
              Your Milestones
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              A timeline of your listening achievements and memorable moments
            </Typography>

            {milestonesLoading ? (
              <Box>
                {[...Array(5)].map((_, i) => (
                  <Box key={i} sx={{ mb: 2 }}>
                    <Skeleton variant="text" width={80} height={30} />
                    <Skeleton variant="rectangular" height={80} sx={{ my: 1 }} />
                  </Box>
                ))}
              </Box>
            ) : milestones.length === 0 ? (
              <Alert severity="info">No milestones found yet. Keep listening!</Alert>
            ) : (
              years.map((year) => (
                <Box key={year} sx={{ mb: 4 }}>
                  <Typography
                    variant="h6"
                    fontWeight={700}
                    sx={{
                      mb: 2,
                      pb: 1,
                      borderBottom: 2,
                      borderColor: 'primary.main',
                      display: 'inline-block',
                    }}
                  >
                    {year}
                  </Typography>

                  <List>
                    {milestonesByYear[year].map((milestone, index) => (
                      <Box key={`${milestone.date}-${index}`}>
                        <ListItem
                          sx={{
                            py: 2,
                            px: 0,
                            alignItems: 'flex-start',
                            '&:hover': {
                              bgcolor: 'action.hover',
                              borderRadius: 1,
                              px: 2,
                            },
                          }}
                        >
                          <Box sx={{ mr: 2, mt: 0.5 }}>{getMilestoneIcon(milestone.type)}</Box>
                          <ListItemText
                            primary={
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                <Typography variant="body1" fontWeight={600}>
                                  {milestone.title}
                                </Typography>
                                <Chip
                                  label={getMilestoneLabel(milestone.type)}
                                  size="small"
                                  sx={{
                                    bgcolor: milestone.badge_color,
                                    color: 'white',
                                    fontWeight: 600,
                                    fontSize: '0.7rem',
                                  }}
                                />
                              </Box>
                            }
                            secondary={
                              <Box>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                                  {milestone.description}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {new Date(milestone.date).toLocaleDateString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                  })}
                                </Typography>
                              </Box>
                            }
                          />
                        </ListItem>
                        {index < milestonesByYear[year].length - 1 && <Divider />}
                      </Box>
                    ))}
                  </List>
                </Box>
              ))
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Snackbar for copy notification */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={3000}
        onClose={() => setSnackbarOpen(false)}
        message={snackbarMessage}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </Box>
  );
}
