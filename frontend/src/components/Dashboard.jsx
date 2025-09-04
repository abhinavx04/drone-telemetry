import React, { useState, useEffect } from 'react';
import axios from 'axios';
import DroneCard from './DroneCard';

// Use environment variable for API URL, with a sensible default for local development
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Dashboard = () => {
  const [drones, setDrones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDrones = async () => {
    // Don't set loading to true on subsequent fetches, to avoid UI flicker
    // setLoading(true); 
    
    try {
      const response = await axios.get(`${API_URL}/api/v1/drones`);
      
      // The backend now returns data that matches our TelemetryOut schema.
      // We can map this to the format expected by DroneCard.
      const transformedData = response.data.map(drone => ({
        id: drone.drone_id,
        status: drone.status || 'online', // Use real status if available, else default
        battery: drone.battery_level,
        mode: drone.flight_mode,
        location: `${parseFloat(drone.latitude).toFixed(4)}, ${parseFloat(drone.longitude).toFixed(4)}`,
        lastSeen: new Date(drone.timestamp * 1000).toLocaleTimeString(),
      }));

      setDrones(transformedData);
      setError(null); // Clear any previous errors
    } catch (err) {
      setError('Failed to fetch drone data. Is the backend service running?');
      console.error("Fetch error:", err);
    } finally {
      setLoading(false); // Only set loading false once
    }
  };

  useEffect(() => {
    fetchDrones(); // Fetch data on initial component mount
    const intervalId = setInterval(fetchDrones, 5000); // Set up polling to refresh data every 5 seconds

    return () => clearInterval(intervalId); // Cleanup interval on component unmount
  }, []);

  const onlineCount = drones.filter(d => d.status === 'online').length;
  // These will be 0 for now until we have status logic.
  const offlineCount = drones.filter(d => d.status === 'offline').length; 
  const emergencyCount = drones.filter(d => d.status === 'emergency').length;

  return (
    <div>
      <header className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white">System Status</h1>
          <p className="text-gray-400">Real-time drone fleet monitoring</p>
        </div>
        <button 
          onClick={fetchDrones} 
          disabled={loading}
          className="px-4 py-2 bg-gray-700 rounded-lg hover:bg-gray-600 disabled:opacity-50"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
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
      <h2 className="text-2xl font-bold text-white mb-4">Active Drones ({drones.length})</h2>
      
      {loading && drones.length === 0 && <p className="text-gray-400">Loading initial drone data...</p>}
      {error && <p className="text-red-500 font-semibold">{error}</p>}
      {!loading && !error && drones.length === 0 && <p className="text-gray-400">No active drones found. Start the simulation script.</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {drones.map(drone => (
          <DroneCard key={drone.id} drone={drone} />
        ))}
      </div>
    </div>
  );
};

export default Dashboard;