import { useEffect, useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  type SelectChangeEvent,
  Skeleton,
} from '@mui/material';
import { Person } from '@mui/icons-material';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import type { CompareUser } from '../types/api';

/**
 * Global user switcher shown in the AppBar. Drives which user's data every
 * analytics page fetches. Selecting the primary user stores `null` so calls
 * omit `user_id` and hit the backend's primary-user fallback.
 */
export default function UserSwitcher() {
  const { selectedUserId, setSelectedUserId } = useAppStore();
  const [users, setUsers] = useState<CompareUser[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const u = await api.getCompareUsers();
        if (!cancelled) setUsers(u);
      } catch {
        if (!cancelled) setUsers([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <Skeleton variant="rounded" width={160} height={36} sx={{ mr: 1 }} />;
  }
  if (users.length === 0) return null;

  const primary = users.find((u) => u.is_primary);
  const value = selectedUserId ?? primary?.user_id ?? '';

  const handleChange = (e: SelectChangeEvent) => {
    const id = e.target.value;
    // storing null for the primary user keeps `user_id` off primary requests
    setSelectedUserId(primary && id === primary.user_id ? null : id);
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', mr: 1 }}>
      <Person sx={{ mr: 1, opacity: 0.9 }} fontSize="small" />
      <FormControl size="small" variant="standard" sx={{ minWidth: 140 }}>
        <InputLabel
          id="user-switcher-label"
          sx={{ color: 'inherit', '&.Mui-focused': { color: 'inherit' } }}
        >
          User
        </InputLabel>
        <Select
          labelId="user-switcher-label"
          id="user-switcher"
          value={value}
          onChange={handleChange}
          label="User"
          aria-label="select user"
          sx={{
            color: 'inherit',
            '& .MuiSelect-icon': { color: 'inherit' },
            '&:before': { borderColor: 'rgba(255,255,255,0.4)' },
            '&:hover:not(.Mui-disabled):before': { borderColor: 'rgba(255,255,255,0.7)' },
          }}
        >
          {users.map((u) => (
            <MenuItem key={u.user_id} value={u.user_id}>
              {u.is_primary ? 'You' : u.display_name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
}
