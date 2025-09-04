import React from 'react';
import { FaBatteryFull, FaBatteryHalf, FaBatteryEmpty, FaMapMarkerAlt, FaPlaneDeparture, FaExclamationTriangle } from 'react-icons/fa';

const DroneCard = ({ drone }) => {
  const getStatusClasses = () => {
    switch (drone.status) {
      case 'online':
        return { border: 'border-green-500', text: 'text-green-500', bg: 'bg-green-500/10' };
      case 'offline':
        return { border: 'border-gray-600', text: 'text-gray-500', bg: 'bg-gray-500/10' };
      case 'emergency':
        return { border: 'border-red-500', text: 'text-red-500', bg: 'bg-red-500/10' };
      default:
        return { border: 'border-gray-700', text: 'text-gray-400', bg: 'bg-gray-700/10' };
    }
  };

  const { border, text, bg } = getStatusClasses();

  const BatteryIcon = ({ level }) => {
    if (level > 70) return <FaBatteryFull className="text-green-500" />;
    if (level > 20) return <FaBatteryHalf className="text-yellow-500" />;
    return <FaBatteryEmpty className="text-red-500" />;
  };

  return (
    <div className={`p-4 rounded-lg border ${border} ${bg}`}>
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-bold text-white">{drone.id}</h3>
        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${bg} ${text} capitalize`}>
          {drone.status}
        </span>
      </div>
      
      <div className="space-y-2 text-sm text-gray-300">
        <div className="flex items-center justify-between">
          <span className="flex items-center"><BatteryIcon level={drone.battery} /><p className="ml-2">Battery</p></span>
          <span>{drone.battery}%</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center"><FaPlaneDeparture className="mr-2" />Mode</span>
          <span>{drone.mode}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center"><FaMapMarkerAlt className="mr-2" />Location</span>
          <span>{drone.location}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center"><FaExclamationTriangle className="mr-2" />Last Seen</span>
          <span>{drone.lastSeen}</span>
        </div>
      </div>

      {drone.status === 'emergency' && (
        <div className="mt-3 p-2 bg-red-500/20 rounded-md text-red-400 text-xs text-center">
          Emergency Status Active
        </div>
      )}
    </div>
  );
};

export default DroneCard;