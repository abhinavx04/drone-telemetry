import React, { useState, useEffect } from 'react';
import axios from 'axios';
import DroneCard from './DroneCard';

const Dashboard = () => {
  const [drones, setDrones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Replace with your actual API endpoint to get all drones
    const fetchDrones = async () => {
      try {
        // For now, we'll use a placeholder. Replace this URL with your actual backend endpoint.
        // Example: 'http://<your-vps-ip>:8000/api/v1/drones'
        // Since we don't have that endpoint yet, I'll mock the data based on your design.
        const mockData = [
          { id: 'DRONE-001', status: 'online', battery: 80, mode: 'MANUAL', location: '40.7072, -74.0040', lastSeen: 'Now' },
          { id: 'DRONE-002', status: 'emergency', battery: 0, mode: 'RTH', location: '40.7589, -73.9851', lastSeen: '8m ago' },
          { id: 'DRONE-003', status: 'online', battery: 100, mode: 'ATTI', location: 'N/A', lastSeen: '12m ago' },
          { id: 'DRONE-004', status: 'offline', battery: 0, mode: 'MANUAL', location: 'N/A', lastSeen: '1h ago' },
        ];
        
        // This simulates a network request
        await new Promise(resolve => setTimeout(resolve, 500));

        setDrones(mockData);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch drone data.');
        setLoading(false);
      }
    };

    fetchDrones();
  }, []);

  // Filter drones based on status for the top overview cards
  const onlineCount = drones.filter(d => d.status === 'online').length;
  const offlineCount = drones.filter(d => d.status === 'offline').length;
  const emergencyCount = drones.filter(d => d.status === 'emergency').length;

  return (
    <div>
      <header className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white">System Status</h1>
          <p className="text-gray-400">Real-time drone fleet monitoring</p>
        </div>
        <button className="px-4 py-2 bg-gray-700 rounded-lg hover:bg-gray-600">Refresh</button>
      </header>

      {/* System Health Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-[#161b22] p-4 rounded-lg border border-gray-700">
          <p className="text-gray-400">Total Drones</p>
          <p className="text-2xl font-bold text-white">{drones.length}</p>
        </div>
        <div className="bg-[#161b22] p-4 rounded-lg border border-green-500">
          <p className="text-gray-400">Online</p>
          <p className="text-2xl font-bold text-green-400">{onlineCount}</p>
        </div>
        <div className="bg-[#161b22] p-4 rounded-lg border border-gray-700">
          <p className="text-gray-400">Offline</p>
          <p className="text-2xl font-bold text-white">{offlineCount}</p>
        </div>
        <div className="bg-[#161b22] p-4 rounded-lg border border-red-500">
          <p className="text-gray-400">Emergencies</p>
          <p className="text-2xl font-bold text-red-400">{emergencyCount}</p>
        </div>
      </div>

      {/* Active Drones Section */}
      <h2 className="text-2xl font-bold text-white mb-4">Active Drones ({onlineCount + emergencyCount})</h2>
      
      {loading && <p>Loading drones...</p>}
      {error && <p className="text-red-500">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {drones.map(drone => (
          <DroneCard key={drone.id} drone={drone} />
        ))}
      </div>
    </div>
  );
};

export default Dashboard;