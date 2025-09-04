import React from 'react';
import { motion } from 'framer-motion';
import { 
  FaServer, 
  FaDatabase, 
  FaWifi, 
  FaExclamationTriangle,
  FaCheckCircle,
  FaTimesCircle,
  FaClock
} from 'react-icons/fa';
import { useSystemHealth } from '../hooks/useRealTimeData';

const SystemMetrics = ({ drones = [] }) => {
  const { health, loading } = useSystemHealth();

  // Calculate fleet statistics
  const fleetStats = {
    total: drones.length,
    online: drones.filter(d => d.is_online).length,
    offline: drones.filter(d => !d.is_online).length,
    critical: drones.filter(d => d.battery_percentage <= 10).length,
    warning: drones.filter(d => d.battery_percentage <= 20 && d.battery_percentage > 10).length,
    avgBattery: drones.length > 0 ? 
      (drones.reduce((sum, d) => sum + (d.battery_percentage || 0), 0) / drones.length).toFixed(1) : 0,
    avgAltitude: drones.length > 0 ?
      (drones.reduce((sum, d) => sum + (d.absolute_altitude_m || 0), 0) / drones.length).toFixed(1) : 0,
  };

  const getHealthIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <FaCheckCircle className="text-green-500" />;
      case 'unhealthy':
        return <FaTimesCircle className="text-red-500" />;
      default:
        return <FaClock className="text-yellow-500" />;
    }
  };

  const getHealthStatus = (status) => {
    switch (status) {
      case 'healthy':
        return { text: 'OPERATIONAL', color: 'text-green-500', bg: 'bg-green-500/10' };
      case 'unhealthy':
        return { text: 'ERROR', color: 'text-red-500', bg: 'bg-red-500/10' };
      default:
        return { text: 'CHECKING', color: 'text-yellow-500', bg: 'bg-yellow-500/10' };
    }
  };

  const systemComponents = [
    {
      name: 'API Server',
      status: health.api,
      icon: <FaServer className="text-xl" />,
      description: 'FastAPI backend service'
    },
    {
      name: 'Database',
      status: health.database,
      icon: <FaDatabase className="text-xl" />,
      description: 'TimescaleDB connection'
    },
    {
      name: 'MQTT Broker',
      status: health.mqtt,
      icon: <FaWifi className="text-xl" />,
      description: 'Message broker service'
    },
  ];

  const fleetMetrics = [
    {
      label: 'Total Drones',
      value: fleetStats.total,
      icon: <FaServer className="text-blue-400" />,
      color: 'text-blue-400'
    },
    {
      label: 'Online',
      value: fleetStats.online,
      icon: <FaCheckCircle className="text-green-400" />,
      color: 'text-green-400'
    },
    {
      label: 'Offline',
      value: fleetStats.offline,
      icon: <FaTimesCircle className="text-gray-400" />,
      color: 'text-gray-400'
    },
    {
      label: 'Critical Alerts',
      value: fleetStats.critical,
      icon: <FaExclamationTriangle className="text-red-400" />,
      color: 'text-red-400'
    },
    {
      label: 'Avg Battery',
      value: `${fleetStats.avgBattery}%`,
      icon: <FaServer className="text-yellow-400" />,
      color: 'text-yellow-400'
    },
    {
      label: 'Avg Altitude',
      value: `${fleetStats.avgAltitude}m`,
      icon: <FaServer className="text-purple-400" />,
      color: 'text-purple-400'
    },
  ];

  return (
    <div className="space-y-6">
      {/* System Health */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 p-6"
      >
        <h3 className="text-xl font-bold text-white mb-4 flex items-center">
          <FaServer className="mr-3 text-blue-400" />
          System Health
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {systemComponents.map((component, index) => {
            const healthStatus = getHealthStatus(component.status);
            
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: index * 0.1, duration: 0.3 }}
                className={`p-4 rounded-lg border border-gray-600 ${healthStatus.bg}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    {component.icon}
                    <span className="font-semibold text-white">{component.name}</span>
                  </div>
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    getHealthIcon(component.status)
                  )}
                </div>
                <p className="text-xs text-gray-400 mb-2">{component.description}</p>
                <div className={`text-xs font-bold ${healthStatus.color}`}>
                  {healthStatus.text}
                </div>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* Fleet Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
        className="bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 p-6"
      >
        <h3 className="text-xl font-bold text-white mb-4 flex items-center">
          <FaDatabase className="mr-3 text-green-400" />
          Fleet Metrics
        </h3>
        
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {fleetMetrics.map((metric, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + index * 0.05, duration: 0.3 }}
              className="p-4 bg-gray-900/50 rounded-lg border border-gray-700/30 text-center"
            >
              <div className="flex justify-center mb-2">
                {metric.icon}
              </div>
              <div className={`text-2xl font-bold ${metric.color} mb-1`}>
                {metric.value}
              </div>
              <div className="text-xs text-gray-400">
                {metric.label}
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Real-time Status */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.4 }}
        className="bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 p-6"
      >
        <h3 className="text-xl font-bold text-white mb-4 flex items-center">
          <FaWifi className="mr-3 text-purple-400" />
          Real-time Status
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Fleet Status Distribution */}
          <div>
            <h4 className="text-lg font-semibold text-white mb-3">Fleet Status</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <span className="text-gray-300">Online</span>
                </div>
                <span className="text-white font-semibold">{fleetStats.online}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full bg-gray-500"></div>
                  <span className="text-gray-300">Offline</span>
                </div>
                <span className="text-white font-semibold">{fleetStats.offline}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <span className="text-gray-300">Critical</span>
                </div>
                <span className="text-white font-semibold">{fleetStats.critical}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <span className="text-gray-300">Warning</span>
                </div>
                <span className="text-white font-semibold">{fleetStats.warning}</span>
              </div>
            </div>
          </div>

          {/* Performance Metrics */}
          <div>
            <h4 className="text-lg font-semibold text-white mb-3">Performance</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Uptime</span>
                <span className="text-green-400 font-semibold">99.9%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Response Time</span>
                <span className="text-blue-400 font-semibold">45ms</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Data Rate</span>
                <span className="text-purple-400 font-semibold">2.4 KB/s</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Last Update</span>
                <span className="text-gray-400 font-mono text-sm">
                  {new Date().toLocaleTimeString()}
                </span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default SystemMetrics;