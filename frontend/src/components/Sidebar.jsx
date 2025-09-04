import React from 'react';
import { FiGrid, FiArchive } from 'react-icons/fi'; // Example icons

const Sidebar = () => {
  return (
    <div className="w-64 bg-[#161b22] border-r border-gray-700 p-4">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Astrox</h1>
        <p className="text-sm text-gray-400">Drone Pipeline</p>
      </div>
      <nav>
        <ul>
          <li>
            <a href="#" className="flex items-center p-3 bg-blue-600 rounded-lg text-white">
              <FiGrid className="mr-3" />
              Status
            </a>
          </li>
          <li className="mt-2">
            <a href="#" className="flex items-center p-3 hover:bg-gray-700 rounded-lg">
              <FiArchive className="mr-3" />
              Inventory
            </a>
          </li>
        </ul>
      </nav>
      <div className="absolute bottom-4">
        <p className="text-sm text-gray-400">System Status</p>
        <p className="text-sm text-green-400">Operational</p>
      </div>
    </div>
  );
};

export default Sidebar;