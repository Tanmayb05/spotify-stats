import { Box, Typography, Paper } from '@mui/material';

export default function Discovery() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        Artist Discovery
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Explore your journey of discovering new artists and track your listening loyalty.
      </Typography>
      <Paper sx={{ p: 4, mt: 3, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          Phase 3 will implement artist discovery timeline and loyalty analysis
        </Typography>
      </Paper>
    </Box>
  );
}
