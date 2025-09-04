import { useState, useEffect, useCallback, useRef } from 'react';
import apiService from '../services/api';

/**
 * Custom hook for managing real-time drone data
 */
export const useRealTimeData = (refreshInterval = 5000) => {
  const [drones, setDrones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const intervalRef = useRef(null);

  // Fetch drone data
  const fetchDrones = useCallback(async () => {
    try {
      setError(null);
      const data = await apiService.getAllDrones();
      setDrones(data);
      setIsConnected(true);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch drone data:', err);
      setError(err.message || 'Failed to fetch drone data');
      setIsConnected(false);
      setLoading(false);
    }
  }, []);

  // Start real-time updates
  const startRealTimeUpdates = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    
    intervalRef.current = setInterval(fetchDrones, refreshInterval);
  }, [fetchDrones, refreshInterval]);

  // Stop real-time updates
  const stopRealTimeUpdates = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Manual refresh
  const refresh = useCallback(() => {
    setLoading(true);
    fetchDrones();
  }, [fetchDrones]);

  // Initialize on mount
  useEffect(() => {
    fetchDrones();
    startRealTimeUpdates();

    return () => {
      stopRealTimeUpdates();
    };
  }, [fetchDrones, startRealTimeUpdates, stopRealTimeUpdates]);

  return {
    drones,
    loading,
    error,
    isConnected,
    refresh,
    startRealTimeUpdates,
    stopRealTimeUpdates,
  };
};

/**
 * Custom hook for getting telemetry history for a specific drone
 */
export const useDroneTelemetry = (droneId, limit = 50) => {
  const [telemetry, setTelemetry] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchTelemetry = useCallback(async () => {
    if (!droneId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await apiService.getDroneTelemetry(droneId, limit);
      setTelemetry(data);
    } catch (err) {
      console.error(`Failed to fetch telemetry for ${droneId}:`, err);
      setError(err.message || 'Failed to fetch telemetry data');
    } finally {
      setLoading(false);
    }
  }, [droneId, limit]);

  useEffect(() => {
    fetchTelemetry();
  }, [fetchTelemetry]);

  return {
    telemetry,
    loading,
    error,
    refresh: fetchTelemetry,
  };
};

/**
 * Custom hook for managing selected drone
 */
export const useSelectedDrone = () => {
  const [selectedDroneId, setSelectedDroneId] = useState(null);
  const [selectedDrone, setSelectedDrone] = useState(null);

  const selectDrone = useCallback((drone) => {
    if (drone) {
      setSelectedDroneId(drone.drone_id);
      setSelectedDrone(drone);
    }
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedDroneId(null);
    setSelectedDrone(null);
  }, []);

  return {
    selectedDroneId,
    selectedDrone,
    selectDrone,
    clearSelection,
  };
};

/**
 * Custom hook for system health monitoring
 */
export const useSystemHealth = () => {
  const [health, setHealth] = useState({
    api: 'unknown',
    database: 'unknown',
    mqtt: 'unknown',
  });
  const [loading, setLoading] = useState(true);

  const checkHealth = useCallback(async () => {
    try {
      await apiService.healthCheck();
      setHealth(prev => ({ ...prev, api: 'healthy' }));
    } catch (error) {
      setHealth(prev => ({ ...prev, api: 'unhealthy' }));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    
    // Check health every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    
    return () => clearInterval(interval);
  }, [checkHealth]);

  return {
    health,
    loading,
    checkHealth,
  };
};

/**
 * Custom hook for managing alerts and notifications
 */
export const useAlerts = (drones = []) => {
  const [alerts, setAlerts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const newAlerts = [];
    
    drones.forEach(drone => {
      const droneAlerts = [];
      
      // Battery alerts
      if (drone.battery_percentage <= 10) {
        droneAlerts.push({
          id: `${drone.drone_id}-battery-critical`,
          droneId: drone.drone_id,
          type: 'critical',
          message: `Critical battery level: ${drone.battery_percentage}%`,
          timestamp: Date.now(),
        });
      } else if (drone.battery_percentage <= 20) {
        droneAlerts.push({
          id: `${drone.drone_id}-battery-low`,
          droneId: drone.drone_id,
          type: 'warning',
          message: `Low battery level: ${drone.battery_percentage}%`,
          timestamp: Date.now(),
        });
      }
      
      // Connectivity alerts
      if (!drone.is_online) {
        droneAlerts.push({
          id: `${drone.drone_id}-offline`,
          droneId: drone.drone_id,
          type: 'error',
          message: 'Drone is offline',
          timestamp: Date.now(),
        });
      }
      
      // Flight mode alerts
      if (drone.flight_mode === 'rth') {
        droneAlerts.push({
          id: `${drone.drone_id}-rth`,
          droneId: drone.drone_id,
          type: 'info',
          message: 'Drone is returning to home',
          timestamp: Date.now(),
        });
      }
      
      newAlerts.push(...droneAlerts);
    });
    
    setAlerts(newAlerts);
    setUnreadCount(newAlerts.filter(alert => alert.type === 'critical' || alert.type === 'error').length);
  }, [drones]);

  const dismissAlert = useCallback((alertId) => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  }, []);

  const clearAllAlerts = useCallback(() => {
    setAlerts([]);
    setUnreadCount(0);
  }, []);

  return {
    alerts,
    unreadCount,
    dismissAlert,
    clearAllAlerts,
  };
};

export default useRealTimeData;