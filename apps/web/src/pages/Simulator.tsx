import { Box, Typography, Paper, Chip } from '@mui/material';

export default function Simulator() {
  return (
    <Box>
      <Box display="flex" alignItems="center" gap={1} mb={2}>
        <Typography variant="h4" fontWeight={700}>
          Predictive Simulator
        </Typography>
        <Chip label="⚗️ Experimental" size="small" color="secondary" />
      </Box>
      <Typography variant="body1" color="text.secondary" paragraph>
        Simulate future listening patterns using Markov chains and probabilistic models.
      </Typography>
      <Paper sx={{ p: 4, mt: 3, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          Phase 7 will implement predictive simulation features
        </Typography>
      </Paper>
    </Box>
  );
}
