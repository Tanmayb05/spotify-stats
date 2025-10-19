import { Alert, Snackbar } from '@mui/material';
import { useAppStore } from '../store/app';

export default function ErrorBanner() {
  const { error, setError } = useAppStore();

  const handleClose = () => {
    setError(null);
  };

  return (
    <Snackbar
      open={!!error}
      autoHideDuration={6000}
      onClose={handleClose}
      anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
    >
      <Alert onClose={handleClose} severity="error" sx={{ width: '100%' }}>
        {error}
      </Alert>
    </Snackbar>
  );
}
