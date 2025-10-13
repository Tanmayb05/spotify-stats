import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Skeleton,
  Typography,
  Box,
} from '@mui/material';

export interface Column<T> {
  key: keyof T;
  label: string;
  align?: 'left' | 'right' | 'center';
  width?: string;
  format?: (value: any) => string | number;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyMessage?: string;
  maxHeight?: string;
  'aria-label'?: string;
}

export default function DataTable<T extends Record<string, any>>({
  columns,
  data,
  loading = false,
  emptyMessage = 'No data available',
  maxHeight = '500px',
  'aria-label': ariaLabel,
}: DataTableProps<T>) {
  // Loading skeleton
  if (loading) {
    return (
      <TableContainer component={Paper} sx={{ maxHeight }}>
        <Table stickyHeader aria-label={ariaLabel}>
          <TableHead>
            <TableRow>
              {columns.map((col) => (
                <TableCell
                  key={String(col.key)}
                  align={col.align || 'left'}
                  sx={{ fontWeight: 700, width: col.width }}
                >
                  {col.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {[...Array(5)].map((_, idx) => (
              <TableRow key={idx}>
                {columns.map((col) => (
                  <TableCell key={String(col.key)} align={col.align || 'left'}>
                    <Skeleton variant="text" width="80%" />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  }

  // Empty state
  if (data.length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Paper>
    );
  }

  // Data table
  return (
    <TableContainer component={Paper} sx={{ maxHeight }}>
      <Table stickyHeader aria-label={ariaLabel}>
        <TableHead>
          <TableRow>
            {columns.map((col) => (
              <TableCell
                key={String(col.key)}
                align={col.align || 'left'}
                sx={{ fontWeight: 700, width: col.width }}
              >
                {col.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row, rowIndex) => (
            <TableRow
              key={rowIndex}
              hover
              tabIndex={0}
              sx={{
                '&:focus': {
                  outline: '2px solid',
                  outlineColor: 'primary.main',
                  outlineOffset: '-2px',
                },
              }}
            >
              {columns.map((col) => {
                const value = row[col.key];
                const displayValue = col.format ? col.format(value) : value;

                return (
                  <TableCell key={String(col.key)} align={col.align || 'left'}>
                    {displayValue}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
