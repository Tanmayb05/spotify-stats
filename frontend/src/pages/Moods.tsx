import { Box, Typography, Paper } from '@mui/material';

export default function Moods() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        Moods & Audio Features
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Analyze your listening moods based on audio features like valence, energy, and danceability.
      </Typography>
      <Paper sx={{ p: 4, mt: 3, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          Phase 2 will implement mood analysis and time-based discovery
        </Typography>
      </Paper>
    </Box>
  );
}
