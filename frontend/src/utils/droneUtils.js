// Utility functions for drone data processing and formatting

/**
 * Convert timestamp to human-readable format
 */
export const formatTimestamp = (timestamp) => {
  if (!timestamp) return 'N/A';
  
  const now = Date.now();
  const time = typeof timestamp === 'string' ? new Date(timestamp).getTime() : timestamp;
  const diff = now - time;
  
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (seconds < 30) return 'Now';
  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
};

/**
 * Get drone status based on telemetry data
 */
export const getDroneStatus = (drone) => {
  if (!drone) return 'unknown';
  
  // Emergency conditions
  if (drone.battery_percentage <= 10 && drone.is_online) {
    return 'emergency';
  }
  
  // Check if drone is offline (last seen > 30 minutes)
  if (!drone.is_online || (Date.now() - drone.timestamp) > 1800000) {
    return 'offline';
  }
  
  return 'online';
};

/**
 * Get status styling classes
 */
export const getStatusClasses = (status) => {
  switch (status) {
    case 'online':
      return {
        border: 'border-green-500',
        text: 'text-green-500',
        bg: 'bg-green-500/10',
        glow: 'shadow-green-500/20'
      };
    case 'offline':
      return {
        border: 'border-gray-600',
        text: 'text-gray-500',
        bg: 'bg-gray-500/10',
        glow: 'shadow-gray-500/20'
      };
    case 'emergency':
      return {
        border: 'border-red-500',
        text: 'text-red-500',
        bg: 'bg-red-500/10',
        glow: 'shadow-red-500/20'
      };
    default:
      return {
        border: 'border-gray-700',
        text: 'text-gray-400',
        bg: 'bg-gray-700/10',
        glow: 'shadow-gray-700/20'
      };
  }
};

/**
 * Format flight mode for display
 */
export const formatFlightMode = (mode) => {
  if (!mode) return 'Unknown';
  
  const modeMap = {
    'manual': 'MANUAL',
    'atti': 'ATTI',
    'rth': 'RTH',
    'Return to Launch': 'RTH',
    'Position Hold': 'POSITION',
  };
  
  return modeMap[mode] || mode.toUpperCase();
};

/**
 * Format coordinates for display
 */
export const formatCoordinates = (lat, lng) => {
  if (!lat || !lng) return 'N/A';
  return `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
};

/**
 * Calculate distance between two coordinates (Haversine formula)
 */
export const calculateDistance = (lat1, lng1, lat2, lng2) => {
  const R = 6371; // Earth's radius in kilometers
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
    Math.sin(dLng/2) * Math.sin(dLng/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c; // Distance in kilometers
};

/**
 * Get battery level styling
 */
export const getBatteryStyle = (level) => {
  if (level > 70) return { color: 'text-green-500', icon: 'full' };
  if (level > 40) return { color: 'text-yellow-500', icon: 'half' };
  if (level > 20) return { color: 'text-orange-500', icon: 'quarter' };
  return { color: 'text-red-500', icon: 'empty' };
};

/**
 * Convert altitude to different units
 */
export const formatAltitude = (altitudeM, unit = 'meters') => {
  if (altitudeM === null || altitudeM === undefined) return 'N/A';
  
  switch (unit) {
    case 'feet':
      return `${(altitudeM * 3.28084).toFixed(1)} ft`;
    case 'meters':
    default:
      return `${altitudeM.toFixed(1)} m`;
  }
};

/**
 * Generate mock telemetry data for charts
 */
export const generateMockTelemetryHistory = (droneId, hours = 1) => {
  const data = [];
  const now = Date.now();
  const interval = (hours * 60 * 60 * 1000) / 60; // 60 data points
  
  for (let i = 60; i >= 0; i--) {
    const timestamp = now - (i * interval);
    data.push({
      timestamp,
      battery: Math.max(10, 100 - (i * 1.5) + (Math.random() - 0.5) * 10),
      altitude: Math.max(0, 50 + Math.sin(i * 0.1) * 30 + (Math.random() - 0.5) * 10),
      speed: Math.max(0, 25 + Math.cos(i * 0.15) * 15 + (Math.random() - 0.5) * 5),
    });
  }
  
  return data;
};

/**
 * Validate drone telemetry data
 */
export const validateTelemetryData = (data) => {
  const errors = [];
  
  if (!data.drone_id) errors.push('Missing drone ID');
  if (typeof data.latitude !== 'number' || data.latitude < -90 || data.latitude > 90) {
    errors.push('Invalid latitude');
  }
  if (typeof data.longitude !== 'number' || data.longitude < -180 || data.longitude > 180) {
    errors.push('Invalid longitude');
  }
  if (data.battery_percentage !== null && (data.battery_percentage < 0 || data.battery_percentage > 100)) {
    errors.push('Invalid battery percentage');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Get alert level based on drone conditions
 */
export const getAlertLevel = (drone) => {
  const alerts = [];
  
  if (drone.battery_percentage <= 10) {
    alerts.push({ level: 'critical', message: 'Critical battery level' });
  } else if (drone.battery_percentage <= 20) {
    alerts.push({ level: 'warning', message: 'Low battery level' });
  }
  
  if (!drone.is_online) {
    alerts.push({ level: 'error', message: 'Drone offline' });
  }
  
  if (drone.flight_mode === 'rth') {
    alerts.push({ level: 'info', message: 'Returning to home' });
  }
  
  return alerts;
};