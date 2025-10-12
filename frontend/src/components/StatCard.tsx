import { Card, CardContent, Typography, Box, Skeleton } from '@mui/material';
import type { ReactNode } from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  subtitle?: string;
  loading?: boolean;
}

export default function StatCard({
  title,
  value,
  icon,
  subtitle,
  loading = false,
}: StatCardProps) {
  return (
    <Card sx={{
      height: '100%',
      transition: 'all 0.3s ease-in-out',
      '&:hover': {
        transform: 'translateY(-8px)',
        boxShadow: '0 12px 24px rgba(0, 0, 0, 0.15)',
      },
    }}>
      <CardContent sx={{ p: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={2}>
          <Box>
            <Typography color="text.secondary" variant="body2" gutterBottom sx={{ mb: 1.5 }}>
              {title}
            </Typography>
            {loading ? (
              <Skeleton width={140} height={48} />
            ) : (
              <Typography variant="h3" component="div" fontWeight={700} sx={{ mb: 0.5 }}>
                {value}
              </Typography>
            )}
            {subtitle && !loading && (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          {icon && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'primary.main',
                borderRadius: '50%',
                p: 2,
                opacity: 0.9,
                minWidth: 56,
                minHeight: 56,
              }}
            >
              {icon}
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
