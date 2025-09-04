import axios from 'axios';

// Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API service functions
export const apiService = {
  // Health check
  async healthCheck() {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  },

  // Get telemetry data for a specific drone
  async getDroneTelemetry(droneId, limit = 10) {
    try {
      const response = await api.get(`/telemetry/${droneId}?limit=${limit}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get telemetry for drone ${droneId}:`, error);
      throw error;
    }
  },

  // Get latest telemetry for all drones (mock implementation for now)
  async getAllDrones() {
    try {
      // For now, we'll simulate the drone list based on recent telemetry
      // In a real implementation, you'd have an endpoint like /drones
      const mockDroneIds = ['DRONE-001', 'DRONE-002', 'DRONE-003', 'DRONE-004'];
      
      const dronePromises = mockDroneIds.map(async (droneId) => {
        try {
          const telemetry = await this.getDroneTelemetry(droneId, 1);
          return telemetry.length > 0 ? telemetry[0] : null;
        } catch (error) {
          // If no telemetry found, return mock data
          return {
            drone_id: droneId,
            latitude: 40.7128 + (Math.random() - 0.5) * 0.1,
            longitude: -74.0060 + (Math.random() - 0.5) * 0.1,
            absolute_altitude_m: Math.random() * 100,
            battery_percentage: Math.floor(Math.random() * 100),
            flight_mode: ['manual', 'atti', 'rth'][Math.floor(Math.random() * 3)],
            is_online: Math.random() > 0.3,
            timestamp: Date.now(),
          };
        }
      });

      const drones = await Promise.all(dronePromises);
      return drones.filter(drone => drone !== null);
    } catch (error) {
      console.error('Failed to get all drones:', error);
      // Return mock data on error
      return [
        {
          drone_id: 'DRONE-001',
          latitude: 40.7128,
          longitude: -74.0060,
          absolute_altitude_m: 50.5,
          battery_percentage: 85,
          flight_mode: 'manual',
          is_online: true,
          timestamp: Date.now(),
        },
        {
          drone_id: 'DRONE-002',
          latitude: 40.7589,
          longitude: -73.9851,
          absolute_altitude_m: 0,
          battery_percentage: 15,
          flight_mode: 'rth',
          is_online: false,
          timestamp: Date.now() - 480000, // 8 minutes ago
        },
        {
          drone_id: 'DRONE-003',
          latitude: 40.6892,
          longitude: -74.0445,
          absolute_altitude_m: 75.2,
          battery_percentage: 92,
          flight_mode: 'atti',
          is_online: true,
          timestamp: Date.now() - 720000, // 12 minutes ago
        },
        {
          drone_id: 'DRONE-004',
          latitude: 40.7831,
          longitude: -73.9712,
          absolute_altitude_m: 0,
          battery_percentage: 0,
          flight_mode: 'manual',
          is_online: false,
          timestamp: Date.now() - 3600000, // 1 hour ago
        },
      ];
    }
  },

  // Post telemetry data (for testing)
  async postTelemetry(telemetryData) {
    try {
      const response = await api.post('/telemetry/', telemetryData);
      return response.data;
    } catch (error) {
      console.error('Failed to post telemetry:', error);
      throw error;
    }
  },
};

export default apiService;