import React from 'react';
import { motion } from 'framer-motion';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <div className="flex min-h-screen bg-gray-900">
      <Sidebar />
      <motion.main 
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
        className="flex-1 p-6 lg:p-8 overflow-hidden"
      >
        <Dashboard />
      </motion.main>
    </div>
  );
}

export default App;