import { Box, Typography, Paper, Chip } from '@mui/material';

export default function Recommendations() {
  return (
    <Box>
      <Box display="flex" alignItems="center" gap={1} mb={2}>
        <Typography variant="h4" fontWeight={700}>
          Recommendations
        </Typography>
        <Chip label="⚗️ Experimental" size="small" color="secondary" />
      </Box>
      <Typography variant="body1" color="text.secondary" paragraph>
        Get personalized music recommendations based on your listening history and preferences.
      </Typography>
      <Paper sx={{ p: 4, mt: 3, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          Phase 6 will implement ML-based content recommendations
        </Typography>
      </Paper>
    </Box>
  );
}
