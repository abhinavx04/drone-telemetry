import React from 'react';
import { motion } from 'framer-motion';
import { 
  FaBatteryFull, 
  FaBatteryHalf, 
  FaBatteryEmpty, 
  FaMapMarkerAlt, 
  FaPlaneDeparture, 
  FaExclamationTriangle,
  FaWifi,
  FaArrowUp,
  FaTimes
} from 'react-icons/fa';
import { 
  getDroneStatus, 
  getStatusClasses, 
  formatTimestamp, 
  formatCoordinates, 
  formatAltitude, 
  formatFlightMode 
} from '../utils/droneUtils';

const DroneCard = ({ drone, onClick, isSelected = false, index = 0 }) => {
  // Convert backend data format to display format
  const droneData = {
    id: drone.drone_id || drone.id,
    battery: drone.battery_percentage || drone.battery || 0,
    mode: formatFlightMode(drone.flight_mode || drone.mode),
    location: formatCoordinates(drone.latitude, drone.longitude),
    lastSeen: formatTimestamp(drone.timestamp),
    altitude: drone.absolute_altitude_m || 0,
    isOnline: drone.is_online !== undefined ? drone.is_online : true,
    latitude: drone.latitude,
    longitude: drone.longitude,
  };

  const status = getDroneStatus(drone);
  const { border, text, bg, glow } = getStatusClasses(status);

  const BatteryIcon = ({ level }) => {
    if (level > 70) return <FaBatteryFull className="text-green-500" />;
    if (level > 20) return <FaBatteryHalf className="text-yellow-500" />;
    return <FaBatteryEmpty className="text-red-500" />;
  };

  const handleClick = () => {
    if (onClick) {
      onClick(drone);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className={`relative p-4 rounded-lg border cursor-pointer transition-all duration-300 hover:scale-105 backdrop-blur-sm ${border} ${bg} ${
        isSelected ? `ring-2 ring-blue-500 ${glow} shadow-lg` : 'hover:shadow-lg'
      }`}
      onClick={handleClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Status indicator pulse for online drones */}
      {droneData.isOnline && (
        <div className="absolute top-2 right-2">
          <div className="relative">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <div className="absolute inset-0 w-3 h-3 bg-green-500 rounded-full animate-ping opacity-75"></div>
          </div>
        </div>
      )}

      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center space-x-2">
          <h3 className="font-bold text-white text-lg">{droneData.id}</h3>
          {droneData.isOnline ? (
            <FaWifi className="text-green-400 text-sm" title="Connected" />
          ) : (
            <FaTimes className="text-red-400 text-sm" title="Disconnected" />
          )}
        </div>
        <span className={`text-xs font-semibold px-3 py-1 rounded-full ${bg} ${text} capitalize backdrop-blur-sm`}>
          {status}
        </span>
      </div>
      
      {/* Battery with visual bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="flex items-center text-sm text-gray-300">
            <BatteryIcon level={droneData.battery} />
            <span className="ml-2">Battery</span>
          </span>
          <span className="text-white font-semibold">{droneData.battery}%</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2">
          <motion.div
            className={`h-2 rounded-full ${
              droneData.battery > 70 ? 'bg-green-500' :
              droneData.battery > 40 ? 'bg-yellow-500' :
              droneData.battery > 20 ? 'bg-orange-500' : 'bg-red-500'
            }`}
            initial={{ width: 0 }}
            animate={{ width: `${droneData.battery}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        </div>
      </div>

      <div className="space-y-2 text-sm text-gray-300">
        <div className="flex items-center justify-between">
          <span className="flex items-center">
            <FaPlaneDeparture className="mr-2 text-indigo-400" />
            Mode
          </span>
          <span className="text-white font-medium">{droneData.mode}</span>
        </div>
        
        <div className="flex items-center justify-between">
          <span className="flex items-center">
            <FaArrowUp className="mr-2 text-purple-400" />
            Altitude
          </span>
          <span className="text-white font-medium">{formatAltitude(droneData.altitude)}</span>
        </div>
        
        <div className="flex items-center justify-between">
          <span className="flex items-center">
            <FaMapMarkerAlt className="mr-2 text-blue-400" />
            Location
          </span>
          <span className="text-white font-mono text-xs">{droneData.location}</span>
        </div>
        
        <div className="flex items-center justify-between">
          <span className="flex items-center">
            <FaExclamationTriangle className="mr-2 text-gray-400" />
            Last Seen
          </span>
          <span className="text-white font-medium">{droneData.lastSeen}</span>
        </div>
      </div>

      {/* Emergency status alert */}
      {status === 'emergency' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-3 p-2 bg-red-500/20 border border-red-500/30 rounded-md text-red-400 text-xs text-center font-semibold"
        >
          <FaExclamationTriangle className="inline mr-2" />
          Emergency Status Active
        </motion.div>
      )}

      {/* Low battery warning */}
      {droneData.battery <= 20 && droneData.battery > 10 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-3 p-2 bg-yellow-500/20 border border-yellow-500/30 rounded-md text-yellow-400 text-xs text-center font-semibold"
        >
          Low Battery Warning
        </motion.div>
      )}

      {/* Selected indicator */}
      {isSelected && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 rounded-lg pointer-events-none"
          style={{
            background: 'linear-gradient(45deg, transparent 49%, rgba(59, 130, 246, 0.1) 50%, transparent 51%)',
            backgroundSize: '8px 8px',
          }}
        />
      )}
    </motion.div>
  );
};

export default DroneCard;