import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import { ZONE_COORDS } from '../data/constants';

const API_URL = 'http://192.168.68.109:8000/api';
const QUEUE_KEY = 'offline_log_queue';
const now = () => new Date().toISOString();
let _id = 9000;
const lid = () => String(++_id);

// ─── OFFLINE QUEUE ───────────────────────────────────────────────────────────
async function queueOfflineLog(entry) {
  try {
    const raw = await AsyncStorage.getItem(QUEUE_KEY);
    const queue = raw ? JSON.parse(raw) : [];
    queue.push(entry);
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  } catch {}
}

async function syncOfflineQueue() {
  try {
    const raw = await AsyncStorage.getItem(QUEUE_KEY);
    if (!raw) return;
    const queue = JSON.parse(raw);
    if (!queue.length) return;
    for (const entry of queue) {
      await api('/activity-log/', { method: 'POST', body: entry }).catch(() => {});
    }
    await AsyncStorage.removeItem(QUEUE_KEY);
  } catch {}
}

// ─── HEARTBEAT ───────────────────────────────────────────────────────────────
let heartbeatInterval = null;

function startHeartbeat(userId) {
  if (heartbeatInterval) clearInterval(heartbeatInterval);
  heartbeatInterval = setInterval(() => {
    api('/auth/heartbeat/', { method: 'POST', body: { user_id: userId } }).catch(() => {});
  }, 30000);
}

function stopHeartbeat(userId) {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
  if (userId) {
    api('/auth/offline/', { method: 'POST', body: { user_id: userId } }).catch(() => {});
  }
}

const ni = r => ({ ...r, dateReported: r.date_reported, createdAt: r.created_at });
const ne = r => ({ ...r, facilitiesAvailable: r.facilities_available || [], contactPerson: r.contact_person });
const nr = r => ({ ...r, householdMembers: r.household_members, evacuationStatus: r.evacuation_status, vulnerabilityTags: r.vulnerability_tags || [] });
const na = r => ({ ...r, id: String(r.id), userName: r.user_name || 'System', userRole: r.user_role || '', userStatus: r.user_status || '', createdAt: r.created_at || now(), urgent: !!r.urgent });

function gps(zone) {
  const b = ZONE_COORDS[zone] || { lat: 8.492, lng: 124.650 };
  return { lat: b.lat + (Math.random() - 0.5) * 0.004, lng: b.lng + (Math.random() - 0.5) * 0.004 };
}

async function api(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export function useDB() {
  const [incidents,   setI] = useState([]);
  const [alerts,      setA] = useState([]);
  const [evacCenters, setE] = useState([]);
  const [residents,   setR] = useState([]);
  const [resources,   setS] = useState([]);
  const [users,       setU] = useState([]);
  const [activityLog, setL] = useState([]);
  const [loading,  setLoad] = useState(true);
  const [currentUser, setCU] = useState(null);

  const reload = useCallback(async () => {
    setLoad(true);
    try {
      const [ri, ra, re, rr, rs, ru, rl] = await Promise.allSettled([
        api('/incidents/'),
        api('/alerts/'),
        api('/evacuation-centers/'),
        api('/residents/'),
        api('/resources/'),
        api('/users/'),
        api('/activity-log/'),
      ]);
      const g = x => x.status === 'fulfilled' ? (x.value || []) : [];
      setI(g(ri).map(ni));
      setA(g(ra));
      setE(g(re).map(ne));
      setR(g(rr).map(nr));
      setS(g(rs));
      setU(g(ru));
      setL(g(rl).map(na));
    } catch (err) {
      console.warn('DB error:', err);
      setU([{ id: 'local1', name: 'Admin', email: 'admin@kauswagan.gov.ph', role: 'Admin', status: 'Active', is_online: true }]);
    } finally {
      setLoad(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // Auto-refresh users every 30s for live status
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await api('/users/');
        if (data) setU(data);
      } catch {}
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // App state — background/foreground for Staff only
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (!currentUser || currentUser.role === 'Admin') return;
      if (state === 'background' || state === 'inactive') {
        stopHeartbeat(currentUser.id);
      } else if (state === 'active') {
        startHeartbeat(currentUser.id);
        syncOfflineQueue();
      }
    });
    return () => sub.remove();
  }, [currentUser]);

  // Network changes for Staff only
  useEffect(() => {
    const unsub = NetInfo.addEventListener(async (state) => {
      if (!currentUser || currentUser.role === 'Admin') return;
      if (!state.isConnected) {
        await queueOfflineLog({
          action: `${currentUser.name} went offline`,
          type: 'Auth',
          user_name: currentUser.name,
          user_role: currentUser.role,
          user_status: 'Inactive',
          urgent: false,
        });
        stopHeartbeat(currentUser.id);
      } else {
        await syncOfflineQueue();
        startHeartbeat(currentUser.id);
        reload();
      }
    });
    return () => unsub();
  }, [currentUser]);

  const log = useCallback(async (action, type, user, urgent, role = '', status = '') => {
    const entry = {
      action,
      type,
      user_name: user || 'System',
      user_role: role,
      user_status: status,
      urgent: !!urgent,
    };
    setL(p => [{ id: lid(), ...entry, userName: user || 'System', userRole: role, userStatus: status, createdAt: now() }, ...p].slice(0, 150));
    try {
      await api('/activity-log/', { method: 'POST', body: entry });
    } catch {
      await queueOfflineLog(entry);
    }
  }, []);

  // ─── AUTH ────────────────────────────────────────────────────────────────
  const loginUser = useCallback(async (email, password) => {
    try {
      const data = await api('/auth/login/', {
        method: 'POST',
        body: { email: email.trim(), password },
      });
      if (!data || !data.user) return { ok: false, msg: 'Wrong email or password.' };
      setCU(data.user);
      await syncOfflineQueue();
      if (data.user.role !== 'Admin') {
        startHeartbeat(data.user.id);
      }
      log(`Signed in: ${data.user.name} (${data.user.role})`, 'Auth', data.user.name, false, data.user.role, 'Active');
      return { ok: true, user: data.user };
    } catch (_) {
      const local = users.find(u => u.email?.toLowerCase() === email.trim().toLowerCase() && u.password === password && u.status === 'Active');
      if (local) {
        setCU(local);
        log(`Signed in: ${local.name} (${local.role})`, 'Auth', local.name, false, local.role, 'Active');
        return { ok: true, user: { id: local.id, name: local.name, email: local.email, role: local.role } };
      }
      return { ok: false, msg: 'Cannot connect. Make sure Django server is running.' };
    }
  }, [users, log]);

  const logoutUser = useCallback(async (userId, userName, role) => {
    if (role !== 'Admin') {
      stopHeartbeat(userId);
    }
    setCU(null);
    log(`Signed out: ${userName} (${role})`, 'Auth', userName, false, role, role === 'Admin' ? 'Active' : 'Inactive');
    await api('/auth/logout/', {
      method: 'POST',
      body: { user_id: role !== 'Admin' ? userId : null, user_name: userName, user_role: role },
    }).catch(() => {});
  }, [log]);

  const addIncident = useCallback(async (d, user) => {
    const p = gps(d.zone);
    const rec = await api('/incidents/', {
      method: 'POST',
      body: { type: d.type, zone: d.zone, location: d.location || '', severity: d.severity || 'Medium', status: 'Pending', description: d.description || '', reporter: d.reporter || '', lat: p.lat, lng: p.lng, source: 'mobile' },
    });
    setI(prev => [ni(rec), ...prev]);
    log('Incident: ' + d.type + ' in ' + d.zone, 'Incident', user, d.severity === 'High');
  }, [log]);

  const updateIncident = useCallback(async (id, d, user) => {
    const { id: _, created_at, date_reported, dateReported, createdAt, ...safe } = d;
    const rec = await api(`/incidents/${id}/`, { method: 'PATCH', body: safe });
    setI(prev => prev.map(r => r.id === id ? ni(rec) : r));
    log('Incident updated', 'Incident', user);
  }, [log]);

  const deleteIncident = useCallback(async (id, label, user) => {
    await api(`/incidents/${id}/`, { method: 'DELETE' });
    setI(prev => prev.filter(r => r.id !== id));
    log('Incident deleted: ' + (label || ''), 'Incident', user, true);
  }, [log]);

  const addAlert = useCallback(async (d, user) => {
    const count = d.recipients_count ?? d.smsCount ?? 0;
    const rec = await api('/alerts/', {
      method: 'POST',
      body: { title: d.level + ' — ' + d.zone, message: d.message, level: d.level, zone: d.zone, recipients_count: count, sent_by: user || 'System' },
    });
    setA(prev => [{ ...rec, recipients_count: count }, ...prev]);
    log(d.level + ' alert to ' + d.zone, 'Alert', user, d.level === 'Danger');
  }, [log]);

  const deleteAlert = useCallback(async (id, user) => {
    await api(`/alerts/${id}/`, { method: 'DELETE' });
    setA(prev => prev.filter(r => r.id !== id));
    log('Alert deleted', 'Alert', user);
  }, [log]);

  const addEvac = useCallback(async (d, user) => {
    const p = gps(d.zone);
    const rec = await api('/evacuation-centers/', {
      method: 'POST',
      body: { name: d.name, zone: d.zone, address: d.address || '', capacity: parseInt(d.capacity) || 100, occupancy: parseInt(d.occupancy) || 0, status: d.status || 'Open', facilities_available: d.facilitiesAvailable || [], contact_person: d.contactPerson || '', contact: d.contact || '', lat: p.lat, lng: p.lng },
    });
    setE(prev => [...prev, ne(rec)]);
    log('Evac center added: ' + d.name, 'Evacuation', user);
  }, [log]);

  const updateEvac = useCallback(async (id, d, user) => {
    const rec = await api(`/evacuation-centers/${id}/`, {
      method: 'PATCH',
      body: { name: d.name, zone: d.zone, address: d.address || '', capacity: parseInt(d.capacity) || 100, occupancy: parseInt(d.occupancy) || 0, status: d.status, facilities_available: d.facilitiesAvailable || [], contact_person: d.contactPerson || '', contact: d.contact || '' },
    });
    setE(prev => prev.map(r => r.id === id ? ne(rec) : r));
    log('Evac updated: ' + d.name, 'Evacuation', user);
  }, [log]);

  const deleteEvac = useCallback(async (id, name, user) => {
    await api(`/evacuation-centers/${id}/`, { method: 'DELETE' });
    setE(prev => prev.filter(r => r.id !== id));
    log('Evac deleted: ' + (name || ''), 'Evacuation', user, true);
  }, [log]);

  const addResident = useCallback(async (d, user) => {
    const p = gps(d.zone);
    const rec = await api('/residents/', {
      method: 'POST',
      body: { name: d.name, zone: d.zone, address: d.address || '', household_members: parseInt(d.householdMembers) || 1, contact: d.contact || '', evacuation_status: d.evacuationStatus || 'Safe', vulnerability_tags: d.vulnerabilityTags || [], notes: d.notes || '', added_by: user || 'Mobile', lat: p.lat, lng: p.lng, source: 'mobile' },
    });
    setR(prev => [nr(rec), ...prev]);
    log('Resident added: ' + d.name, 'Resident', user);
  }, [log]);

  const updateResident = useCallback(async (id, d, user) => {
    const rec = await api(`/residents/${id}/`, {
      method: 'PATCH',
      body: { name: d.name, zone: d.zone, address: d.address || '', household_members: parseInt(d.householdMembers) || 1, contact: d.contact || '', evacuation_status: d.evacuationStatus || 'Safe', vulnerability_tags: d.vulnerabilityTags || [], notes: d.notes || '' },
    });
    setR(prev => prev.map(r => r.id === id ? nr(rec) : r));
    log('Resident updated: ' + d.name, 'Resident', user);
  }, [log]);

  const deleteResident = useCallback(async (id, name, user) => {
    await api(`/residents/${id}/`, { method: 'DELETE' });
    setR(prev => prev.filter(r => r.id !== id));
    log('Resident deleted: ' + (name || ''), 'Resident', user, true);
  }, [log]);

  const addResource = useCallback(async (d, user) => {
    const rec = await api('/resources/', {
      method: 'POST',
      body: { name: d.name, category: d.category, quantity: parseInt(d.quantity) || 1, available: parseInt(d.available) || 1, unit: d.unit || 'pcs', location: d.location || '', status: d.status || 'Available', notes: d.notes || '' },
    });
    setS(prev => [...prev, rec]);
    log('Resource added: ' + d.name, 'Resource', user);
  }, [log]);

  const updateResource = useCallback(async (id, d, user) => {
    const rec = await api(`/resources/${id}/`, {
      method: 'PATCH',
      body: { name: d.name, category: d.category, quantity: parseInt(d.quantity) || 0, available: parseInt(d.available) || 0, unit: d.unit || 'pcs', location: d.location || '', status: d.status || 'Available', notes: d.notes || '' },
    });
    setS(prev => prev.map(r => r.id === id ? rec : r));
    log('Resource updated: ' + (d.name || ''), 'Resource', user);
  }, [log]);

  const deleteResource = useCallback(async (id, name, user) => {
    await api(`/resources/${id}/`, { method: 'DELETE' });
    setS(prev => prev.filter(r => r.id !== id));
    log('Resource deleted: ' + (name || ''), 'Resource', user, true);
  }, [log]);

  const addUser = useCallback(async (d) => {
    const rec = await api('/users/', {
      method: 'POST',
      body: { name: d.name, email: d.email, password: d.password, role: d.role || 'Staff', status: d.status || 'Active' },
    });
    setU(prev => [...prev, rec]);
  }, []);

  const updateUser = useCallback(async (id, d) => {
    const update = { name: d.name, email: d.email, role: d.role, status: d.status };
    if (d.password && d.password.trim()) update.password = d.password;
    const rec = await api(`/users/${id}/`, { method: 'PATCH', body: update });
    setU(prev => prev.map(r => r.id === id ? rec : r));
  }, []);

  const deleteUser = useCallback(async (id) => {
    await api(`/users/${id}/`, { method: 'DELETE' });
    setU(prev => prev.filter(r => r.id !== id));
  }, []);

  return {
    loading, reload, log,
    currentUser,
    incidents, alerts, evacCenters, residents, resources, users, activityLog,
    loginUser, logoutUser,
    addIncident, updateIncident, deleteIncident,
    addAlert, deleteAlert,
    addEvac, updateEvac, deleteEvac,
    addResident, updateResident, deleteResident,
    addResource, updateResource, deleteResource,
    addUser, updateUser, deleteUser,
  };
}