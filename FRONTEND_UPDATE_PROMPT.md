# ✅ FINAL PROMPT — Frontend Flight-Aware Drone Telemetry Dashboard

## 1. System Overview

Update the existing React frontend to support the new flight-aware telemetry platform backend. The frontend must display:
- **Flight History**: List and browse all flights per drone
- **Flight Details**: View comprehensive flight statistics and summary
- **Flight Path Visualization**: Interactive map showing flight trajectory
- **ULog Management**: Upload and download flight log files
- **Enhanced Drone Cards**: Display flight count and additional metadata

⚠️ **Strict backward compatibility** is mandatory. All existing functionality must continue to work unchanged.

---

## 2. Current Frontend State

### Tech Stack
- **React 19.1.1** with Vite
- **TailwindCSS** for styling
- **Axios** for HTTP requests
- **react-icons** for icons
- No routing library (currently single-page)
- No map library (needs to be added)

### Existing Components
- `App.jsx`: Main app wrapper with Sidebar + Dashboard
- `Dashboard.jsx`: Lists drones, displays system overview stats
- `DroneCard.jsx`: Displays individual drone status card
- `Sidebar.jsx`: Navigation sidebar

### Existing Data Flow
- `GET /api/v1/drones` → Dashboard displays drone list
- Polls every 5 seconds
- WebSocket support available at `/api/v1/drones/{id}/telemetry/stream` (not currently used)

---

## 3. Backend API Changes (Reference)

### Updated Endpoints

#### `GET /api/v1/drones`
**Response Schema Change:**
```typescript
{
  id: string;                    // Existing (e.g., "udp:14540")
  status: "online" | "stale" | "offline";  // Existing
  last_seen_ts: number | null;   // Existing
  battery_pct: number | null;    // Existing
  flight_mode: string | null;    // Existing
  position: {                     // Existing
    lat: number;
    lon: number;
    alt_m: number | null;
  } | null;
  // NEW OPTIONAL FIELDS (may be null):
  udp_port: number | null;        // NEW
  total_flights: number | null;   // NEW
  real_drone_id: string | null;   // NEW
}
```

### New Endpoints

#### `GET /api/v1/drones/{drone_id}/flights`
**Query Parameters:**
- `limit` (optional, default: 50, max: 200)
- `offset` (optional, default: 0)

**Response:**
```typescript
Array<{
  flight_id: string;
  drone_id: string;
  flight_count: number;           // Sequential flight number (1, 2, 3...)
  start_timestamp: number;        // Unix timestamp (seconds)
  end_timestamp: number | null;   // null = flight in progress
  duration_seconds: number | null;
  max_altitude_m: number | null;
  max_speed_mps: number | null;
  battery_start_pct: number | null;
  battery_end_pct: number | null;
  gps_issues_count: number;
  emergency_events_count: number;
  summary_data: object | null;    // JSON object with additional metrics
}>
```

#### `GET /api/v1/flights/{flight_id}`
**Response:** Same as single item from flights list

#### `GET /api/v1/flights/{flight_id}/summary`
**Response:** Same as flight details (alias endpoint)

#### `GET /api/v1/flights/{flight_id}/telemetry`
**Query Parameters:**
- `limit` (optional, default: 200, max: 500)
- `offset` (optional, default: 0)

**Response:**
```typescript
{
  flight_id: string;
  points: Array<{
    timestamp: number;
    latitude: number | null;
    longitude: number | null;
    altitude_m: number | null;
    battery_pct: number | null;
    flight_mode: string | null;
    ground_speed_mps: number | null;
    climb_rate_mps: number | null;
    heading_deg: number | null;
    gps_lost: boolean | null;
    is_emergency: boolean | null;
    ingest_timestamp: number | null;
  }>;
  total: number;                  // Total points available
  limit: number;
  offset: number;
}
```

#### `GET /api/v1/flights/{flight_id}/ulog`
**Response:**
```typescript
Array<{
  id: string;                     // ULog file ID
  flight_id: string | null;
  drone_id: string;
  original_filename: string;
  size_bytes: number;
  uploaded_at: number;            // Unix timestamp
  content_type: string | null;
}>
```

#### `POST /api/v1/flights/{flight_id}/ulog`
**Request:** `multipart/form-data` with `file` field
**Response:** Same as ULog object from list endpoint

---

## 4. Required Frontend Changes

### A. Dependency Additions

**Required NPM Packages:**
```json
{
  "react-router-dom": "^6.x",           // For routing/navigation
  "leaflet": "^1.9.4",                  // Map library
  "react-leaflet": "^4.2.1",            // React bindings for Leaflet
  "@react-leaflet/core": "^2.1.0"       // Core Leaflet React components
}
```

**Note:** Add Leaflet CSS in `index.html`:
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
```

---

### B. Component Structure

#### **New Components to Create:**

1. **`FlightHistory.jsx`**
   - Lists all flights for a selected drone
   - Pagination controls (prev/next, page size selector)
   - Clickable flight cards → navigate to flight details
   - Status badges: "In Progress" vs "Completed"
   - Display: Flight #, start time, duration, max altitude, max speed

2. **`FlightDetails.jsx`**
   - Comprehensive flight statistics display
   - Flight path map visualization (Leaflet)
   - Telemetry chart/graph (optional, can be simple for now)
   - ULog upload/download section
   - Back button to flight history

3. **`FlightMap.jsx`** (Reusable)
   - Leaflet map component
   - Draws flight path polyline from telemetry points
   - Markers for start/end points
   - Interactive: click points to see timestamp/altitude
   - Handles pagination: load more telemetry as user pans/zooms

4. **`ULogUploader.jsx`** (Reusable)
   - File input with drag-and-drop
   - Upload progress indicator
   - Error handling
   - List existing ULog files for flight

5. **`FlightCard.jsx`** (Reusable)
   - Compact card for flight list items
   - Shows: Flight #, date/time, duration, key metrics
   - Status indicator (in progress vs completed)
   - Click handler for navigation

---

### C. Routing & Navigation

**Install and Configure React Router:**

1. Update `App.jsx` to use `BrowserRouter`:
```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/drones/:droneId/flights" element={<FlightHistory />} />
            <Route path="/flights/:flightId" element={<FlightDetails />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
```

2. Update `Sidebar.jsx`:
   - Add navigation links
   - Highlight active route

3. Update `DroneCard.jsx`:
   - Add clickable "View Flights" button/link
   - Navigate to `/drones/{droneId}/flights`

---

### D. Data Fetching & State Management

**Create API Service Module (`src/services/api.js`):**

```javascript
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = {
  // Existing
  getDrones: () => axios.get(`${API_URL}/api/v1/drones`),
  
  // New
  getFlights: (droneId, limit = 50, offset = 0) =>
    axios.get(`${API_URL}/api/v1/drones/${droneId}/flights`, {
      params: { limit, offset }
    }),
  
  getFlight: (flightId) =>
    axios.get(`${API_URL}/api/v1/flights/${flightId}`),
  
  getFlightTelemetry: (flightId, limit = 200, offset = 0) =>
    axios.get(`${API_URL}/api/v1/flights/${flightId}/telemetry`, {
      params: { limit, offset }
    }),
  
  getFlightULogs: (flightId) =>
    axios.get(`${API_URL}/api/v1/flights/${flightId}/ulog`),
  
  uploadULog: (flightId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return axios.post(`${API_URL}/api/v1/flights/${flightId}/ulog`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  }
};
```

---

### E. Dashboard Updates (`Dashboard.jsx`)

**Changes Required:**

1. **Update Data Transformation:**
   - Handle new optional fields: `udp_port`, `total_flights`, `real_drone_id`
   - Map `battery_pct` correctly (field name may have changed)
   - Map `position.lat/lon` correctly (structure change)

2. **Enhanced DroneCard Data:**
   - Pass `total_flights` to DroneCard
   - Pass `udp_port` for display
   - Ensure `real_drone_id` is used if available, fallback to `id`

3. **Backward Compatibility:**
   - If `total_flights` is null/undefined, don't display flight count
   - Don't break if new fields are missing

---

### F. DroneCard Updates (`DroneCard.jsx`)

**New Features:**

1. **Flight Count Badge:**
   - Display "X flights" if `total_flights` is available
   - Styled badge (e.g., top-right corner)

2. **Navigation Link:**
   - "View Flight History" button/link
   - Navigate to `/drones/{droneId}/flights`
   - Disabled if `total_flights === 0` or null

3. **UDP Port Display:**
   - Show UDP port if available (e.g., "Port: 14540")
   - Small text, secondary information

4. **Backward Compatibility:**
   - All new elements must gracefully handle missing data
   - Don't render flight count if `total_flights` is null

---

### G. FlightHistory Component (`FlightHistory.jsx`)

**Requirements:**

1. **Route:** `/drones/:droneId/flights`

2. **Features:**
   - Fetch flights using `api.getFlights(droneId, limit, offset)`
   - Display pagination controls (prev/next, page size: 10/25/50)
   - Loading state while fetching
   - Error handling (404 if drone not found)
   - Empty state: "No flights recorded yet"

3. **Flight List:**
   - Use `FlightCard` component for each flight
   - Sort: Most recent first (backend handles this)
   - Status indicators:
     - "In Progress" badge if `end_timestamp === null`
     - "Completed" badge if `end_timestamp !== null`

4. **FlightCard Display:**
   - Flight #: `flight_count`
   - Date/Time: Format `start_timestamp` (e.g., "Jan 15, 2024 14:30")
   - Duration: Format `duration_seconds` (e.g., "12m 34s" or "In Progress")
   - Max Altitude: Display if available (e.g., "Max Alt: 125.5m")
   - Max Speed: Display if available (e.g., "Max Speed: 15.2 m/s")
   - Battery: Show start/end if available (e.g., "Battery: 95% → 78%")

5. **Navigation:**
   - Click flight card → navigate to `/flights/{flightId}`
   - Back button to Dashboard (`/`)

---

### H. FlightDetails Component (`FlightDetails.jsx`)

**Requirements:**

1. **Route:** `/flights/:flightId`

2. **Layout Sections:**

   **a. Flight Summary Header:**
   - Flight #, drone ID
   - Start/end timestamps (formatted)
   - Duration
   - Status (In Progress / Completed)
   - Back button to flight history

   **b. Key Metrics Grid:**
   - Max Altitude
   - Max Speed
   - Battery Start/End
   - GPS Issues Count
   - Emergency Events Count
   - Distance Traveled (calculate from telemetry points if available)

   **c. Flight Path Map:**
   - Full-screen or large map section
   - Use `FlightMap` component
   - Load telemetry points (handle pagination)
   - Start marker (green)
   - End marker (red, if flight completed)
   - Path polyline (color-coded by altitude or speed if desired)

   **d. Telemetry Table/Chart (Optional):**
   - Tabular view of telemetry points
   - Columns: Time, Lat, Lon, Alt, Speed, Battery, Mode
   - Virtualized/scrollable (for large datasets)
   - Export to CSV button (optional enhancement)

   **e. ULog Management:**
   - Use `ULogUploader` component
   - Display existing ULog files
   - Download links for uploaded files

3. **Data Fetching:**
   - Fetch flight details: `api.getFlight(flightId)`
   - Fetch telemetry: `api.getFlightTelemetry(flightId, limit, offset)`
   - Fetch ULogs: `api.getFlightULogs(flightId)`
   - Handle pagination for telemetry (load more as needed)

4. **Loading States:**
   - Skeleton loaders for map/telemetry
   - Progress indicators

5. **Error Handling:**
   - 404 if flight not found
   - Network errors
   - Empty telemetry (show message)

---

### I. FlightMap Component (`FlightMap.jsx`)

**Requirements:**

1. **Leaflet Integration:**
   - Import `MapContainer`, `TileLayer`, `Polyline`, `Marker`, `Popup` from `react-leaflet`
   - Use OpenStreetMap tiles (free, no API key)

2. **Props:**
   ```javascript
   {
     telemetryPoints: Array<{
       latitude: number;
       longitude: number;
       altitude_m: number | null;
       timestamp: number;
       battery_pct: number | null;
       ground_speed_mps: number | null;
     }>;
     startPosition: { lat: number; lon: number };
     endPosition: { lat: number; lon: number } | null;
     isLoading?: boolean;
     onLoadMore?: (offset: number) => void;  // For pagination
     hasMore?: boolean;
   }
   ```

3. **Features:**
   - Draw polyline connecting all telemetry points
   - Color-code polyline by altitude (gradient: blue=low, red=high)
   - Start marker: Green icon with "START" label
   - End marker: Red icon with "END" label (if `endPosition` provided)
   - Clickable path points: Show popup with timestamp, altitude, speed, battery
   - Auto-fit bounds to show entire flight path
   - Zoom controls, fullscreen toggle (optional)

4. **Pagination Handling:**
   - If `hasMore === true`, show "Load More" button
   - Call `onLoadMore(offset)` when clicked
   - Append new points to existing polyline

5. **Edge Cases:**
   - Handle flights with no telemetry points (show message)
   - Handle flights with only one point (show marker, no line)
   - Handle invalid/null coordinates (filter out)

---

### J. ULogUploader Component (`ULogUploader.jsx`)

**Requirements:**

1. **Props:**
   ```javascript
   {
     flightId: string;
     existingULogs: Array<ULogFile>;
     onUploadSuccess?: () => void;
   }
   ```

2. **Features:**
   - Drag-and-drop file input
   - File type validation (only `.ulg` files, or any file type if backend allows)
   - File size validation (max 100MB, or configurable)
   - Upload progress bar (use axios `onUploadProgress`)
   - Success/error notifications
   - List existing ULog files:
     - Display filename, size (formatted: "2.5 MB"), upload date
     - Download button (link to backend file endpoint, if available)
     - Delete button (optional, if backend supports)

3. **API Integration:**
   - Use `api.uploadULog(flightId, file)`
   - Refresh ULog list after successful upload
   - Call `onUploadSuccess()` callback if provided

---

### K. FlightCard Component (`FlightCard.jsx`)

**Requirements:**

1. **Props:**
   ```javascript
   {
     flight: {
       flight_id: string;
       flight_count: number;
       start_timestamp: number;
       end_timestamp: number | null;
       duration_seconds: number | null;
       max_altitude_m: number | null;
       max_speed_mps: number | null;
       battery_start_pct: number | null;
       battery_end_pct: number | null;
       gps_issues_count: number;
       emergency_events_count: number;
     };
     onClick?: (flightId: string) => void;
   }
   ```

2. **Display:**
   - Flight # badge (large, prominent)
   - Date/time: Format `start_timestamp` nicely
   - Duration: "12m 34s" or "In Progress" badge
   - Quick stats: Max alt, max speed (if available)
   - Battery: Start → End (if available)
   - Warning indicators: Show alert if `gps_issues_count > 0` or `emergency_events_count > 0`

3. **Styling:**
   - Hover effect (highlight on hover)
   - Clickable cursor
   - Border color: Green if completed, yellow if in progress

---

## 5. Styling & UX Requirements

### Design Consistency
- Use existing TailwindCSS theme (dark mode: `bg-[#161b22]`, etc.)
- Match existing card/badge styles
- Consistent spacing and typography

### Loading States
- Skeleton loaders for lists/tables
- Spinner for buttons/actions
- Progressive loading for maps (show partial path while loading more)

### Error States
- 404: "Flight not found" with back button
- Network errors: Retry button
- Empty states: Friendly messages with icons

### Responsive Design
- Mobile-friendly (stack components vertically)
- Map should be responsive (height: 400px on mobile, 600px on desktop)
- Pagination controls: Touch-friendly on mobile

---

## 6. Backward Compatibility Rules

### Critical Requirements

1. **Dashboard Must Work Without New Fields:**
   - If `total_flights === null`, don't show flight count
   - If `udp_port === null`, don't show UDP port
   - Don't break if `position` structure changes (handle gracefully)

2. **API Response Handling:**
   - All new fields are optional (may be null)
   - Always check for null/undefined before using
   - Provide sensible defaults or skip rendering

3. **Existing Functionality:**
   - Dashboard drone list must still work
   - WebSocket streaming (if implemented) must continue
   - All existing endpoints must continue to work

4. **Progressive Enhancement:**
   - Flight features are additive
   - If backend doesn't return flight data, gracefully degrade
   - Don't crash if flight endpoints return 404/500

---

## 7. Implementation Checklist

### Phase 1: Foundation
- [ ] Install routing library (`react-router-dom`)
- [ ] Install map library (`leaflet`, `react-leaflet`)
- [ ] Update `App.jsx` with routing
- [ ] Create API service module (`src/services/api.js`)
- [ ] Update `Dashboard.jsx` to handle new optional fields

### Phase 2: Navigation & Basic Components
- [ ] Update `Sidebar.jsx` with navigation links
- [ ] Update `DroneCard.jsx` with flight count and navigation
- [ ] Create `FlightCard.jsx` component
- [ ] Create `FlightHistory.jsx` component (basic list)

### Phase 3: Flight Details & Map
- [ ] Create `FlightDetails.jsx` component
- [ ] Create `FlightMap.jsx` component
- [ ] Integrate map into flight details
- [ ] Implement telemetry pagination

### Phase 4: ULog Management
- [ ] Create `ULogUploader.jsx` component
- [ ] Integrate into `FlightDetails.jsx`
- [ ] Implement file upload with progress

### Phase 5: Polish & Testing
- [ ] Error handling for all API calls
- [ ] Loading states for all components
- [ ] Empty states
- [ ] Responsive design testing
- [ ] Backward compatibility verification

---

## 8. Edge Cases to Handle

### Data Edge Cases
1. **Flight with no telemetry points:**
   - Show message: "No telemetry data available for this flight"
   - Don't render map, or show map with just start marker

2. **Flight in progress (`end_timestamp === null`):**
   - Show "In Progress" badge
   - Don't show end marker on map
   - Duration shows "In Progress" or elapsed time

3. **Flight with invalid coordinates:**
   - Filter out points where `latitude === null` or `longitude === null`
   - Handle gracefully in map rendering

4. **Large telemetry datasets (1000+ points):**
   - Implement pagination in map
   - Use virtual scrolling in telemetry table
   - Show "Loading more..." indicator

5. **ULog upload failures:**
   - Show error message
   - Allow retry
   - Validate file before upload

6. **Network failures:**
   - Retry mechanism (3 attempts)
   - Show offline indicator
   - Cache flight list (optional enhancement)

### UI Edge Cases
1. **Empty flight history:**
   - Show "No flights recorded yet" message
   - Provide link back to dashboard

2. **Loading states:**
   - Don't show blank screens
   - Show skeletons/spinners immediately

3. **Very long flight durations:**
   - Format nicely: "2h 34m 12s" or "1d 3h"
   - Don't overflow UI

---

## 9. Testing Requirements

### Manual Testing Checklist
- [ ] Dashboard displays drones correctly with new optional fields
- [ ] Click "View Flights" navigates to flight history
- [ ] Flight history pagination works
- [ ] Click flight card navigates to flight details
- [ ] Flight details map renders correctly
- [ ] Map pagination loads more telemetry
- [ ] ULog upload works with progress indicator
- [ ] ULog list displays correctly
- [ ] Back buttons navigate correctly
- [ ] Error states display properly
- [ ] Empty states display properly
- [ ] Mobile responsive design works
- [ ] Backward compatibility: Works if new fields are null

---

## 10. API Endpoint Reference

**Base URL:** `import.meta.env.VITE_API_URL || 'http://localhost:8000'`

**Endpoints:**
- `GET /api/v1/drones` - List drones (updated schema)
- `GET /api/v1/drones/{droneId}/flights?limit=50&offset=0` - List flights
- `GET /api/v1/flights/{flightId}` - Get flight details
- `GET /api/v1/flights/{flightId}/telemetry?limit=200&offset=0` - Get telemetry
- `GET /api/v1/flights/{flightId}/ulog` - List ULog files
- `POST /api/v1/flights/{flightId}/ulog` - Upload ULog (multipart/form-data)

---

## 11. Success Criteria

### Functional
- ✅ All flight history displays correctly
- ✅ Flight details show comprehensive information
- ✅ Map visualizes flight path accurately
- ✅ ULog upload/download works
- ✅ Navigation flows smoothly
- ✅ Pagination works correctly
- ✅ Error handling is robust
- ✅ Empty states are user-friendly

### Non-Functional
- ✅ Backward compatible with existing features
- ✅ Responsive on mobile and desktop
- ✅ Loading states prevent confusion
- ✅ Error messages are clear
- ✅ Code is maintainable and well-structured
- ✅ Performance acceptable (smooth map rendering, fast pagination)

---

## 12. Optional Enhancements (Future)

1. **Advanced Map Features:**
   - Heatmap overlay for altitude
   - Speed color-coding on path
   - 3D visualization (using libraries like `deck.gl`)

2. **Charts & Analytics:**
   - Altitude over time chart
   - Speed over time chart
   - Battery drain chart
   - GPS signal strength visualization

3. **Export/Sharing:**
   - Export flight path as GPX/KML
   - Export telemetry as CSV
   - Share flight link (deep linking)

4. **Real-time Updates:**
   - WebSocket for live flight updates
   - Auto-refresh for in-progress flights

5. **Search & Filtering:**
   - Search flights by date range
   - Filter by duration, altitude, etc.
   - Sort options

---

## END OF PROMPT

**⚠️ REMEMBER:**
- Maintain backward compatibility at all costs
- Handle null/undefined for all new fields
- Test edge cases thoroughly
- Provide clear error messages
- Keep existing functionality working

