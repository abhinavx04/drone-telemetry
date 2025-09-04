import React, { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

// Simple map component using basic HTML/CSS (Leaflet would require additional setup)
const DroneMap = ({ drones = [], selectedDroneId, onDroneSelect }) => {
  const mapRef = useRef(null);

  // NYC area bounds for demonstration
  const bounds = {
    north: 40.9176,
    south: 40.4774,
    east: -73.7004,
    west: -74.2591,
  };

  // Convert lat/lng to screen coordinates
  const coordsToPixels = (lat, lng, width, height) => {
    const x = ((lng - bounds.west) / (bounds.east - bounds.west)) * width;
    const y = ((bounds.north - lat) / (bounds.north - bounds.south)) * height;
    return { x, y };
  };

  const getStatusColor = (drone) => {
    if (!drone.is_online) return '#6b7280'; // gray
    if (drone.battery_percentage <= 10) return '#ef4444'; // red
    if (drone.battery_percentage <= 20) return '#f59e0b'; // yellow
    return '#10b981'; // green
  };

  const handleDroneClick = (drone) => {
    if (onDroneSelect) {
      onDroneSelect(drone);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 overflow-hidden"
    >
      <div className="p-4 border-b border-gray-700/50">
        <h3 className="text-lg font-semibold text-white mb-2">Drone Positions</h3>
        <div className="flex items-center space-x-4 text-sm text-gray-400">
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-green-500 mr-2"></div>
            <span>Online</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-yellow-500 mr-2"></div>
            <span>Low Battery</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
            <span>Critical</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-gray-500 mr-2"></div>
            <span>Offline</span>
          </div>
        </div>
      </div>
      
      <div 
        ref={mapRef}
        className="relative bg-gradient-to-br from-blue-900/20 via-gray-900 to-green-900/20 h-80 overflow-hidden"
        style={{
          backgroundImage: `
            radial-gradient(circle at 20% 80%, rgba(16, 185, 129, 0.1) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
            linear-gradient(135deg, transparent 0%, rgba(31, 41, 55, 0.8) 100%)
          `
        }}
      >
        {/* Grid overlay for futuristic look */}
        <div 
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `
              linear-gradient(rgba(99, 102, 241, 0.3) 1px, transparent 1px),
              linear-gradient(90deg, rgba(99, 102, 241, 0.3) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px'
          }}
        ></div>
        
        {/* Area outline */}
        <div className="absolute inset-4 border border-blue-500/30 rounded-lg">
          <div className="absolute top-2 left-2 text-xs text-blue-400 font-mono">
            NYC AREA
          </div>
        </div>
        
        {/* Drone markers */}
        {drones.map((drone, index) => {
          if (!drone.latitude || !drone.longitude) return null;
          
          const mapElement = mapRef.current;
          if (!mapElement) return null;
          
          const rect = mapElement.getBoundingClientRect();
          const { x, y } = coordsToPixels(
            drone.latitude, 
            drone.longitude, 
            rect.width || 320, 
            rect.height || 320
          );
          
          const isSelected = selectedDroneId === drone.drone_id;
          const statusColor = getStatusColor(drone);
          
          return (
            <motion.div
              key={drone.drone_id}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: index * 0.1, duration: 0.3 }}
              className={`absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10 ${
                isSelected ? 'z-20' : ''
              }`}
              style={{ left: x, top: y }}
              onClick={() => handleDroneClick(drone)}
            >
              {/* Pulse animation for online drones */}
              {drone.is_online && (
                <div 
                  className="absolute inset-0 rounded-full animate-ping"
                  style={{ backgroundColor: statusColor, opacity: 0.4 }}
                ></div>
              )}
              
              {/* Main drone marker */}
              <div 
                className={`w-4 h-4 rounded-full border-2 border-gray-900 relative ${
                  isSelected ? 'scale-125 ring-2 ring-white ring-opacity-60' : ''
                }`}
                style={{ backgroundColor: statusColor }}
              >
                {/* Drone icon */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-2 h-2 bg-gray-900 rounded-full"></div>
                </div>
              </div>
              
              {/* Drone label */}
              <div className={`absolute top-5 left-1/2 transform -translate-x-1/2 ${
                isSelected ? 'block' : 'hidden group-hover:block'
              }`}>
                <div className="bg-gray-900/90 text-white text-xs px-2 py-1 rounded border border-gray-600 whitespace-nowrap">
                  <div className="font-semibold">{drone.drone_id}</div>
                  <div className="text-gray-300">
                    {drone.battery_percentage}% • {drone.flight_mode}
                  </div>
                </div>
              </div>
              
              {/* Direction indicator for moving drones */}
              {drone.is_online && (
                <motion.div
                  className="absolute -top-1 -right-1 w-2 h-2"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                >
                  <div className="w-full h-full bg-white rounded-full opacity-60"></div>
                </motion.div>
              )}
            </motion.div>
          );
        })}
        
        {/* Scanning lines for futuristic effect */}
        <motion.div
          className="absolute inset-0 opacity-30"
          initial={{ background: 'linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.3) 50%, transparent 100%)' }}
          animate={{ 
            background: [
              'linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.3) 50%, transparent 100%)',
              'linear-gradient(90deg, transparent 100%, rgba(59, 130, 246, 0.3) 150%, transparent 200%)'
            ]
          }}
          transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
        />
      </div>
      
      {/* Map controls */}
      <div className="p-4 border-t border-gray-700/50 bg-gray-800/30">
        <div className="flex justify-between items-center text-sm text-gray-400">
          <div>
            {drones.length} drone{drones.length !== 1 ? 's' : ''} visible
          </div>
          <div className="flex space-x-2">
            <button className="px-2 py-1 bg-gray-700/50 rounded text-xs hover:bg-gray-600/50 transition-colors">
              Center
            </button>
            <button className="px-2 py-1 bg-gray-700/50 rounded text-xs hover:bg-gray-600/50 transition-colors">
              Track All
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default DroneMap;