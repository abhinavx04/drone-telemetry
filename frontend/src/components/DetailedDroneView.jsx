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
  FaTimes,
  FaExpand
} from 'react-icons/fa';
import { formatTimestamp, formatCoordinates, formatAltitude, getBatteryStyle } from '../utils/droneUtils';
import { TelemetryChart } from './TelemetryChart';

const DetailedDroneView = ({ drone, onClose, onExpand }) => {
  if (!drone) return null;

  const batteryStyle = getBatteryStyle(drone.battery_percentage || 0);
  
  const getBatteryIcon = () => {
    const level = drone.battery_percentage || 0;
    if (level > 70) return <FaBatteryFull className={batteryStyle.color} />;
    if (level > 20) return <FaBatteryHalf className={batteryStyle.color} />;
    return <FaBatteryEmpty className={batteryStyle.color} />;
  };

  const getStatusInfo = () => {
    if (!drone.is_online) {
      return { status: 'OFFLINE', color: 'text-gray-500', bg: 'bg-gray-500/10' };
    }
    if (drone.battery_percentage <= 10) {
      return { status: 'CRITICAL', color: 'text-red-500', bg: 'bg-red-500/10' };
    }
    if (drone.battery_percentage <= 20) {
      return { status: 'WARNING', color: 'text-yellow-500', bg: 'bg-yellow-500/10' };
    }
    return { status: 'ONLINE', color: 'text-green-500', bg: 'bg-green-500/10' };
  };

  const statusInfo = getStatusInfo();

  const telemetryData = [
    {
      label: 'Latitude',
      value: drone.latitude?.toFixed(6) || 'N/A',
      icon: <FaMapMarkerAlt className="text-blue-400" />
    },
    {
      label: 'Longitude', 
      value: drone.longitude?.toFixed(6) || 'N/A',
      icon: <FaMapMarkerAlt className="text-blue-400" />
    },
    {
      label: 'Altitude',
      value: formatAltitude(drone.absolute_altitude_m),
      icon: <FaPlaneDeparture className="text-purple-400" />
    },
    {
      label: 'Flight Mode',
      value: (drone.flight_mode || 'Unknown').toUpperCase(),
      icon: <FaPlaneDeparture className="text-indigo-400" />
    },
    {
      label: 'Last Update',
      value: formatTimestamp(drone.timestamp),
      icon: <FaExclamationTriangle className="text-gray-400" />
    },
    {
      label: 'Connection',
      value: drone.is_online ? 'CONNECTED' : 'DISCONNECTED',
      icon: <FaWifi className={drone.is_online ? 'text-green-400' : 'text-red-400'} />
    }
  ];

  return (
    <motion.div
      initial={{ opacity: 0, x: 300 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 300 }}
      transition={{ duration: 0.3 }}
      className="bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 overflow-hidden"
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-700/50 bg-gradient-to-r from-gray-800/80 to-gray-700/80">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="relative">
              <div className={`w-12 h-12 rounded-full ${statusInfo.bg} flex items-center justify-center border border-gray-600`}>
                <FaPlaneDeparture className={`text-xl ${statusInfo.color}`} />
              </div>
              {drone.is_online && (
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-gray-800"></div>
              )}
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{drone.drone_id}</h2>
              <p className={`text-sm font-semibold ${statusInfo.color}`}>
                {statusInfo.status}
              </p>
            </div>
          </div>
          <div className="flex space-x-2">
            {onExpand && (
              <button
                onClick={onExpand}
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
              >
                <FaExpand />
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
            >
              <FaTimes />
            </button>
          </div>
        </div>
      </div>

      {/* Battery Status */}
      <div className="p-4 border-b border-gray-700/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            {getBatteryIcon()}
            <span className="text-white font-semibold">Battery Status</span>
          </div>
          <span className={`text-lg font-bold ${batteryStyle.color}`}>
            {drone.battery_percentage || 0}%
          </span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-3">
          <motion.div
            className={`h-3 rounded-full ${
              drone.battery_percentage > 70 ? 'bg-green-500' :
              drone.battery_percentage > 40 ? 'bg-yellow-500' :
              drone.battery_percentage > 20 ? 'bg-orange-500' : 'bg-red-500'
            }`}
            initial={{ width: 0 }}
            animate={{ width: `${drone.battery_percentage || 0}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Telemetry Data Grid */}
      <div className="p-4 border-b border-gray-700/50">
        <h3 className="text-lg font-semibold text-white mb-3">Telemetry Data</h3>
        <div className="grid grid-cols-1 gap-3">
          {telemetryData.map((item, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05, duration: 0.2 }}
              className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg border border-gray-700/30"
            >
              <div className="flex items-center space-x-3">
                {item.icon}
                <span className="text-gray-300">{item.label}</span>
              </div>
              <span className="text-white font-mono text-sm">{item.value}</span>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Mini Charts */}
      <div className="p-4">
        <h3 className="text-lg font-semibold text-white mb-3">Recent Telemetry</h3>
        <div className="space-y-4">
          <TelemetryChart droneId={drone.drone_id} type="battery" height={120} />
          <TelemetryChart droneId={drone.drone_id} type="altitude" height={120} />
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-gray-700/50 bg-gray-800/30">
        <div className="flex space-x-2">
          <button className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-semibold">
            Track Drone
          </button>
          <button className="flex-1 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors font-semibold">
            Send Command
          </button>
        </div>
      </div>
    </motion.div>
  );
};

export default DetailedDroneView;