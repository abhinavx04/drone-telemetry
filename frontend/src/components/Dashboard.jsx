import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FaSync, 
  FaExpand, 
  FaCompress, 
  FaChartLine, 
  FaMap, 
  FaBell,
  FaServer
} from 'react-icons/fa';
import DroneCard from './DroneCard';
import DroneMap from './DroneMap';
import DetailedDroneView from './DetailedDroneView';
import SystemMetrics from './SystemMetrics';
import AlertsPanel from './AlertsPanel';
import { TelemetryChart, MultiTelemetryChart } from './TelemetryChart';
import useRealTimeData, { useSelectedDrone } from '../hooks/useRealTimeData';
import { getDroneStatus } from '../utils/droneUtils';

const Dashboard = () => {
  const { drones, loading, error, isConnected, refresh } = useRealTimeData(5000);
  const { selectedDrone, selectDrone, clearSelection } = useSelectedDrone();
  const [view, setView] = useState('overview'); // 'overview', 'map', 'analytics', 'system'
  const [showDetailedView, setShowDetailedView] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const [isAlertsMinimized, setIsAlertsMinimized] = useState(true);

  // Process drones to add status information
  const processedDrones = drones.map(drone => ({
    ...drone,
    status: getDroneStatus(drone)
  }));

  // Filter drones based on status for the top overview cards
  const onlineCount = processedDrones.filter(d => d.status === 'online').length;
  const offlineCount = processedDrones.filter(d => d.status === 'offline').length;
  const emergencyCount = processedDrones.filter(d => d.status === 'emergency').length;

  const handleDroneSelect = (drone) => {
    selectDrone(drone);
    setShowDetailedView(true);
  };

  const handleRefresh = () => {
    refresh();
  };

  const viewOptions = [
    { id: 'overview', label: 'Overview', icon: <FaServer /> },
    { id: 'map', label: 'Map View', icon: <FaMap /> },
    { id: 'analytics', label: 'Analytics', icon: <FaChartLine /> },
    { id: 'system', label: 'System', icon: <FaServer /> },
  ];

  const StatCard = ({ title, value, color, icon, description }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`bg-gray-800/50 backdrop-blur-sm p-6 rounded-lg border border-gray-700/50 hover:border-${color}-500/50 transition-all duration-300`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm font-medium">{title}</p>
          <p className={`text-3xl font-bold text-${color}-400 mt-1`}>{value}</p>
          {description && (
            <p className="text-gray-500 text-xs mt-1">{description}</p>
          )}
        </div>
        <div className={`text-2xl text-${color}-400 opacity-60`}>
          {icon}
        </div>
      </div>
    </motion.div>
  );

  return (
    <div className="relative min-h-screen">
      {/* Header */}
      <motion.header 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex justify-between items-center mb-8"
      >
        <div>
          <h1 className="text-4xl font-bold text-white bg-gradient-to-r from-blue-400 via-purple-500 to-green-400 bg-clip-text text-transparent">
            Mission Control
          </h1>
          <p className="text-gray-400 mt-1">
            Real-time drone fleet monitoring • 
            <span className={`ml-2 ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </p>
        </div>
        <div className="flex items-center space-x-3">
          {/* View Toggle */}
          <div className="flex bg-gray-800/50 rounded-lg p-1 border border-gray-700/50">
            {viewOptions.map((option) => (
              <button
                key={option.id}
                onClick={() => setView(option.id)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  view === option.id
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
                }`}
              >
                {option.icon}
                <span className="hidden sm:inline">{option.label}</span>
              </button>
            ))}
          </div>

          {/* Action Buttons */}
          <button
            onClick={() => setIsAlertsMinimized(!isAlertsMinimized)}
            className="p-3 bg-gray-800/50 border border-gray-700/50 rounded-lg hover:bg-gray-700/50 transition-colors relative"
          >
            <FaBell className="text-white" />
            {emergencyCount > 0 && (
              <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center">
                <span className="text-white text-xs font-bold">{emergencyCount}</span>
              </div>
            )}
          </button>
          
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg transition-colors font-semibold"
          >
            <FaSync className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </motion.header>

      {/* System Health Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Total Drones"
          value={processedDrones.length}
          color="blue"
          icon={<FaServer />}
          description="Fleet size"
        />
        <StatCard
          title="Online"
          value={onlineCount}
          color="green"
          icon={<FaServer />}
          description="Active drones"
        />
        <StatCard
          title="Offline"
          value={offlineCount}
          color="gray"
          icon={<FaServer />}
          description="Inactive drones"
        />
        <StatCard
          title="Alerts"
          value={emergencyCount}
          color="red"
          icon={<FaBell />}
          description="Critical issues"
        />
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Main View */}
        <div className={`${showDetailedView ? 'col-span-8' : 'col-span-12'} space-y-6`}>
          
          {view === 'overview' && (
            <>
              {/* Active Drones Section */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.2 }}
              >
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-2xl font-bold text-white">
                    Active Fleet ({onlineCount + emergencyCount})
                  </h2>
                  <div className="flex items-center space-x-4 text-sm text-gray-400">
                    <div className="flex items-center">
                      <div className="w-3 h-3 rounded-full bg-green-500 mr-2"></div>
                      <span>Operational</span>
                    </div>
                    <div className="flex items-center">
                      <div className="w-3 h-3 rounded-full bg-yellow-500 mr-2"></div>
                      <span>Warning</span>
                    </div>
                    <div className="flex items-center">
                      <div className="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
                      <span>Critical</span>
                    </div>
                  </div>
                </div>
                
                {loading && (
                  <div className="flex items-center justify-center p-8">
                    <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                    <span className="ml-3 text-gray-400">Loading drone data...</span>
                  </div>
                )}
                
                {error && (
                  <div className="p-6 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-red-400 font-semibold">Error: {error}</p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  <AnimatePresence>
                    {processedDrones.map((drone, index) => (
                      <DroneCard
                        key={drone.drone_id}
                        drone={drone}
                        onClick={handleDroneSelect}
                        isSelected={selectedDrone?.drone_id === drone.drone_id}
                        index={index}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              </motion.div>
            </>
          )}

          {view === 'map' && (
            <DroneMap
              drones={processedDrones}
              selectedDroneId={selectedDrone?.drone_id}
              onDroneSelect={handleDroneSelect}
            />
          )}

          {view === 'analytics' && (
            <div className="space-y-6">
              {selectedDrone ? (
                <>
                  <MultiTelemetryChart droneId={selectedDrone.drone_id} />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <TelemetryChart droneId={selectedDrone.drone_id} type="battery" />
                    <TelemetryChart droneId={selectedDrone.drone_id} type="altitude" />
                  </div>
                </>
              ) : (
                <div className="text-center p-12 bg-gray-800/50 rounded-lg border border-gray-700/50">
                  <FaChartLine className="text-4xl text-gray-500 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-white mb-2">No Drone Selected</h3>
                  <p className="text-gray-400">Select a drone to view its analytics</p>
                </div>
              )}
            </div>
          )}

          {view === 'system' && (
            <SystemMetrics drones={processedDrones} />
          )}
        </div>

        {/* Right Panel - Detailed View */}
        <AnimatePresence>
          {showDetailedView && selectedDrone && (
            <motion.div
              initial={{ opacity: 0, x: 300 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 300 }}
              transition={{ duration: 0.3 }}
              className="col-span-4"
            >
              <DetailedDroneView
                drone={selectedDrone}
                onClose={() => {
                  setShowDetailedView(false);
                  clearSelection();
                }}
                onExpand={() => setView('analytics')}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Alerts Panel */}
      <AlertsPanel
        drones={processedDrones}
        isMinimized={isAlertsMinimized}
        onToggleMinimize={() => setIsAlertsMinimized(!isAlertsMinimized)}
      />
    </div>
  );
};

export default Dashboard;