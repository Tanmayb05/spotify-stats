import { Box, Typography, Paper } from '@mui/material';

export default function Sessions() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        Listening Sessions
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Discover patterns in your listening sessions through clustering and analysis.
      </Typography>
      <Paper sx={{ p: 4, mt: 3, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          Phase 5 will implement session segmentation and clustering
        </Typography>
      </Paper>
    </Box>
  );
}
