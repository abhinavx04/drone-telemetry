import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FaExclamationTriangle, 
  FaTimes, 
  FaBell, 
  FaBellSlash,
  FaExclamationCircle,
  FaInfoCircle,
  FaCheckCircle
} from 'react-icons/fa';
import { useAlerts } from '../hooks/useRealTimeData';
import { formatTimestamp } from '../utils/droneUtils';

const AlertsPanel = ({ drones = [], isMinimized = false, onToggleMinimize }) => {
  const { alerts, unreadCount, dismissAlert, clearAllAlerts } = useAlerts(drones);
  const [filter, setFilter] = useState('all'); // 'all', 'critical', 'warning', 'info'

  const getAlertIcon = (type) => {
    switch (type) {
      case 'critical':
        return <FaExclamationTriangle className="text-red-500" />;
      case 'error':
        return <FaExclamationCircle className="text-red-400" />;
      case 'warning':
        return <FaExclamationTriangle className="text-yellow-500" />;
      case 'info':
        return <FaInfoCircle className="text-blue-500" />;
      default:
        return <FaCheckCircle className="text-gray-500" />;
    }
  };

  const getAlertStyle = (type) => {
    switch (type) {
      case 'critical':
        return {
          bg: 'bg-red-500/10',
          border: 'border-red-500/30',
          text: 'text-red-400'
        };
      case 'error':
        return {
          bg: 'bg-red-500/10',
          border: 'border-red-400/30',
          text: 'text-red-300'
        };
      case 'warning':
        return {
          bg: 'bg-yellow-500/10',
          border: 'border-yellow-500/30',
          text: 'text-yellow-400'
        };
      case 'info':
        return {
          bg: 'bg-blue-500/10',
          border: 'border-blue-500/30',
          text: 'text-blue-400'
        };
      default:
        return {
          bg: 'bg-gray-500/10',
          border: 'border-gray-500/30',
          text: 'text-gray-400'
        };
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'all') return true;
    return alert.type === filter;
  });

  const filterOptions = [
    { value: 'all', label: 'All', count: alerts.length },
    { value: 'critical', label: 'Critical', count: alerts.filter(a => a.type === 'critical').length },
    { value: 'error', label: 'Error', count: alerts.filter(a => a.type === 'error').length },
    { value: 'warning', label: 'Warning', count: alerts.filter(a => a.type === 'warning').length },
    { value: 'info', label: 'Info', count: alerts.filter(a => a.type === 'info').length },
  ];

  if (isMinimized) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        className="fixed bottom-4 right-4 z-50"
      >
        <button
          onClick={onToggleMinimize}
          className="relative p-3 bg-gray-800 border border-gray-600 rounded-full shadow-lg hover:bg-gray-700 transition-colors"
        >
          <FaBell className="text-white text-xl" />
          {unreadCount > 0 && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center"
            >
              <span className="text-white text-xs font-bold">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            </motion.div>
          )}
        </button>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 300 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 300 }}
      transition={{ duration: 0.3 }}
      className="bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 overflow-hidden h-full flex flex-col"
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-700/50 bg-gradient-to-r from-gray-800/80 to-gray-700/80">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <FaBell className="text-xl text-yellow-400" />
            <div>
              <h3 className="text-lg font-bold text-white">System Alerts</h3>
              <p className="text-sm text-gray-400">
                {alerts.length} alert{alerts.length !== 1 ? 's' : ''} • {unreadCount} critical
              </p>
            </div>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={onToggleMinimize}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
              title="Minimize"
            >
              <FaBellSlash />
            </button>
            {alerts.length > 0 && (
              <button
                onClick={clearAllAlerts}
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
                title="Clear all"
              >
                <FaTimes />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="p-4 border-b border-gray-700/50">
        <div className="flex space-x-1 bg-gray-700/30 rounded-lg p-1">
          {filterOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => setFilter(option.value)}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                filter === option.value
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-600/50'
              }`}
            >
              {option.label}
              {option.count > 0 && (
                <span className={`ml-2 px-1.5 py-0.5 rounded-full text-xs ${
                  filter === option.value ? 'bg-white/20' : 'bg-gray-600'
                }`}>
                  {option.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Alerts List */}
      <div className="flex-1 overflow-y-auto">
        <AnimatePresence>
          {filteredAlerts.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="p-8 text-center"
            >
              <FaCheckCircle className="text-4xl text-green-500 mx-auto mb-4" />
              <h4 className="text-lg font-semibold text-white mb-2">All Clear!</h4>
              <p className="text-gray-400">
                {filter === 'all' 
                  ? 'No alerts at this time. Your drone fleet is operating normally.'
                  : `No ${filter} alerts found.`
                }
              </p>
            </motion.div>
          ) : (
            <div className="p-4 space-y-3">
              {filteredAlerts.map((alert, index) => {
                const style = getAlertStyle(alert.type);
                
                return (
                  <motion.div
                    key={alert.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -100 }}
                    transition={{ delay: index * 0.05, duration: 0.3 }}
                    className={`p-4 rounded-lg border ${style.bg} ${style.border}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3">
                        <div className="mt-0.5">
                          {getAlertIcon(alert.type)}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-semibold text-white text-sm">
                              {alert.droneId}
                            </span>
                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${style.bg} ${style.text}`}>
                              {alert.type.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-gray-300 text-sm mb-2">
                            {alert.message}
                          </p>
                          <p className="text-xs text-gray-400">
                            {formatTimestamp(alert.timestamp)}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => dismissAlert(alert.id)}
                        className="p-1 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded transition-colors"
                      >
                        <FaTimes className="w-3 h-3" />
                      </button>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      {alerts.length > 0 && (
        <div className="p-4 border-t border-gray-700/50 bg-gray-800/30">
          <div className="flex justify-between items-center text-sm text-gray-400">
            <span>
              Last updated: {new Date().toLocaleTimeString()}
            </span>
            <button
              onClick={clearAllAlerts}
              className="text-blue-400 hover:text-blue-300 transition-colors"
            >
              Clear All
            </button>
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default AlertsPanel;