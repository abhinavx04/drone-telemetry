import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { motion } from 'framer-motion';
import { generateMockTelemetryHistory } from '../utils/droneUtils';

const TelemetryChart = ({ droneId, type = 'battery', height = 200 }) => {
  // Generate mock data for demonstration
  const data = generateMockTelemetryHistory(droneId, 1);

  const formatXAxis = (tickItem) => {
    const date = new Date(tickItem);
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const getChartConfig = () => {
    switch (type) {
      case 'battery':
        return {
          dataKey: 'battery',
          stroke: '#10b981',
          fill: '#10b981',
          name: 'Battery %',
          unit: '%',
          domain: [0, 100]
        };
      case 'altitude':
        return {
          dataKey: 'altitude',
          stroke: '#3b82f6',
          fill: '#3b82f6',
          name: 'Altitude',
          unit: 'm',
          domain: [0, 'dataMax']
        };
      case 'speed':
        return {
          dataKey: 'speed',
          stroke: '#8b5cf6',
          fill: '#8b5cf6',
          name: 'Speed',
          unit: 'm/s',
          domain: [0, 'dataMax']
        };
      default:
        return {
          dataKey: 'battery',
          stroke: '#10b981',
          fill: '#10b981',
          name: 'Battery %',
          unit: '%',
          domain: [0, 100]
        };
    }
  };

  const config = getChartConfig();

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-lg">
          <p className="text-gray-300 text-sm">
            {formatXAxis(label)}
          </p>
          <p className="text-white font-semibold">
            <span style={{ color: config.stroke }}>●</span>
            {` ${config.name}: ${payload[0].value.toFixed(1)}${config.unit}`}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-4 border border-gray-700/50"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center">
          <span 
            className="w-3 h-3 rounded-full mr-2"
            style={{ backgroundColor: config.stroke }}
          ></span>
          {config.name} History
        </h3>
        <div className="text-sm text-gray-400">
          Last 1 hour
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id={`gradient-${type}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={config.stroke} stopOpacity={0.3}/>
              <stop offset="95%" stopColor={config.stroke} stopOpacity={0.05}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={formatXAxis}
            stroke="#9ca3af"
            fontSize={12}
            tickCount={6}
          />
          <YAxis 
            stroke="#9ca3af"
            fontSize={12}
            domain={config.domain}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey={config.dataKey}
            stroke={config.stroke}
            strokeWidth={2}
            fill={`url(#gradient-${type})`}
            dot={{ fill: config.stroke, strokeWidth: 2, r: 3 }}
            activeDot={{ r: 5, fill: config.stroke, stroke: '#1f2937', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  );
};

const MultiTelemetryChart = ({ droneId }) => {
  const data = generateMockTelemetryHistory(droneId, 2);

  const formatXAxis = (tickItem) => {
    const date = new Date(tickItem);
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-lg">
          <p className="text-gray-300 text-sm mb-2">
            {formatXAxis(label)}
          </p>
          {payload.map((entry, index) => (
            <p key={index} className="text-white text-sm">
              <span style={{ color: entry.color }}>●</span>
              {` ${entry.name}: ${entry.value.toFixed(1)}${entry.unit}`}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 }}
      className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-4 border border-gray-700/50"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">
          Multi-Parameter Telemetry
        </h3>
        <div className="flex space-x-4 text-sm">
          <div className="flex items-center">
            <span className="w-3 h-3 rounded-full bg-green-500 mr-2"></span>
            <span className="text-gray-400">Battery</span>
          </div>
          <div className="flex items-center">
            <span className="w-3 h-3 rounded-full bg-blue-500 mr-2"></span>
            <span className="text-gray-400">Altitude</span>
          </div>
          <div className="flex items-center">
            <span className="w-3 h-3 rounded-full bg-purple-500 mr-2"></span>
            <span className="text-gray-400">Speed</span>
          </div>
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={formatXAxis}
            stroke="#9ca3af"
            fontSize={12}
          />
          <YAxis 
            yAxisId="left"
            stroke="#9ca3af"
            fontSize={12}
            domain={[0, 100]}
          />
          <YAxis 
            yAxisId="right" 
            orientation="right"
            stroke="#9ca3af"
            fontSize={12}
            domain={[0, 'dataMax']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="battery"
            stroke="#10b981"
            strokeWidth={2}
            dot={false}
            name="Battery"
            unit="%"
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="altitude"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Altitude"
            unit="m"
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="speed"
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={false}
            name="Speed"
            unit="m/s"
          />
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  );
};

export { TelemetryChart, MultiTelemetryChart };
export default TelemetryChart;