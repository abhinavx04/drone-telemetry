import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  FiGrid, 
  FiArchive, 
  FiSettings, 
  FiUser, 
  FiHelpCircle,
  FiChevronLeft,
  FiChevronRight,
  FiActivity,
  FiRadio
} from 'react-icons/fi';

const Sidebar = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [activeItem, setActiveItem] = useState('status');

  const menuItems = [
    { id: 'status', label: 'Mission Control', icon: FiGrid, badge: null },
    { id: 'inventory', label: 'Fleet Manager', icon: FiArchive, badge: '4' },
    { id: 'analytics', label: 'Analytics', icon: FiActivity, badge: null },
    { id: 'telemetry', label: 'Live Telemetry', icon: FiRadio, badge: 'LIVE' },
    { id: 'settings', label: 'Settings', icon: FiSettings, badge: null },
    { id: 'profile', label: 'Profile', icon: FiUser, badge: null },
    { id: 'help', label: 'Help', icon: FiHelpCircle, badge: null },
  ];

  const handleItemClick = (itemId) => {
    setActiveItem(itemId);
  };

  return (
    <motion.div
      initial={{ width: 256 }}
      animate={{ width: isCollapsed ? 80 : 256 }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="bg-gray-800/50 backdrop-blur-sm border-r border-gray-700/50 relative flex flex-col h-screen"
    >
      {/* Header */}
      <div className="p-6 border-b border-gray-700/50">
        <motion.div
          initial={{ opacity: 1 }}
          animate={{ opacity: isCollapsed ? 0 : 1 }}
          transition={{ duration: 0.2 }}
          className="flex items-center space-x-3"
        >
          {!isCollapsed && (
            <>
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <FiRadio className="text-white text-xl" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white gradient-text">ASTROX</h1>
                <p className="text-sm text-gray-400">Drone Command</p>
              </div>
            </>
          )}
        </motion.div>
        
        {/* Collapse Toggle */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="absolute -right-3 top-8 w-6 h-6 bg-gray-700 border border-gray-600 rounded-full flex items-center justify-center hover:bg-gray-600 transition-colors"
        >
          {isCollapsed ? (
            <FiChevronRight className="text-white text-sm" />
          ) : (
            <FiChevronLeft className="text-white text-sm" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {menuItems.map((item, index) => {
            const isActive = activeItem === item.id;
            const IconComponent = item.icon;
            
            return (
              <motion.li
                key={item.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05, duration: 0.3 }}
              >
                <button
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full flex items-center p-3 rounded-lg transition-all duration-200 group relative ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-lg'
                      : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
                  }`}
                >
                  {/* Icon */}
                  <IconComponent className={`${isCollapsed ? 'text-xl' : 'text-lg'} ${isActive ? 'text-white' : ''}`} />
                  
                  {/* Label */}
                  {!isCollapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.1 }}
                      className="ml-3 font-medium"
                    >
                      {item.label}
                    </motion.span>
                  )}
                  
                  {/* Badge */}
                  {!isCollapsed && item.badge && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.2 }}
                      className={`ml-auto px-2 py-1 text-xs font-semibold rounded-full ${
                        item.badge === 'LIVE'
                          ? 'bg-red-500 text-white pulse-red'
                          : 'bg-gray-600 text-gray-200'
                      }`}
                    >
                      {item.badge}
                    </motion.span>
                  )}
                  
                  {/* Tooltip for collapsed state */}
                  {isCollapsed && (
                    <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-sm rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                      {item.label}
                      {item.badge && (
                        <span className={`ml-2 px-1 text-xs rounded ${
                          item.badge === 'LIVE' ? 'bg-red-500' : 'bg-gray-600'
                        }`}>
                          {item.badge}
                        </span>
                      )}
                    </div>
                  )}
                  
                  {/* Active indicator */}
                  {isActive && (
                    <motion.div
                      layoutId="activeIndicator"
                      className="absolute left-0 top-0 bottom-0 w-1 bg-white rounded-r"
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    />
                  )}
                </button>
              </motion.li>
            );
          })}
        </ul>
      </nav>

      {/* System Status */}
      <div className="p-4 border-t border-gray-700/50">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: isCollapsed ? 0 : 1 }}
          transition={{ duration: 0.2 }}
          className="space-y-3"
        >
          {!isCollapsed && (
            <>
              {/* Connection Status */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">System Status</span>
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full pulse-green"></div>
                  <span className="text-sm text-green-400 font-semibold">Operational</span>
                </div>
              </div>

              {/* Quick Stats */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-gray-700/30 p-2 rounded">
                  <div className="text-gray-400">Uptime</div>
                  <div className="text-white font-semibold">99.9%</div>
                </div>
                <div className="bg-gray-700/30 p-2 rounded">
                  <div className="text-gray-400">Latency</div>
                  <div className="text-white font-semibold">45ms</div>
                </div>
              </div>

              {/* Version Info */}
              <div className="text-xs text-gray-500 text-center">
                v2.1.0 • Build 2024.1
              </div>
            </>
          )}
        </motion.div>

        {/* Collapsed status indicator */}
        {isCollapsed && (
          <div className="flex justify-center">
            <div className="w-4 h-4 bg-green-500 rounded-full pulse-green"></div>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default Sidebar;