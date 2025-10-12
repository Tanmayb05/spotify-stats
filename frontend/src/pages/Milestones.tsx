import { Box, Typography, Paper } from '@mui/material';

export default function Milestones() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        Milestones
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Your listening achievements, streaks, top days, and memorable moments.
      </Typography>
      <Paper sx={{ p: 4, mt: 3, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          Phase 4 will implement milestones and flashback features
        </Typography>
      </Paper>
    </Box>
  );
}
